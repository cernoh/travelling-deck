"""Decky backend entry point (plugin bridge).

Wires the pure-Python ``sensors`` package to the Decky runtime: discovers
Linux IIO accelerometer/gyroscope sources, runs the sensor pipeline in a
daemon thread, and exposes the RPC methods below to the frontend bridge.

RPC contract (callable from the Decky frontend via ``callPluginMethod``):

``get_state`` () -> snapshot dict
    ``state``: one of ``unavailable|ready|active|degraded|safety_disabled``
    ``enabled``: bool (default off, ADR 0007)
    ``orientation``: ``{"roll_deg": float, "pitch_deg": float}``
    ``confidence``: float 0..1
    ``degraded``: bool
    ``sensors``: ``{"accelerometer": {...}, "gyroscope": {...}}``
    ``safety``: ``{"reason": str, "ts": float} | None``
    The frontend should render a Decky notification when ``safety`` appears
    (or its ``ts`` changes) and never show persistent diagnostics over
    gameplay (ADR 0011).

``set_enabled`` (enabled: bool) -> snapshot dict
    Manual enable/disable.  Enable is refused (state stays ``unavailable``)
    while either sensor is missing/unreadable (fail closed, ADR 0012).
    Calling this always clears the safety latch: re-enabling is an explicit
    user action (ADR 0011).

``get_diagnostics`` () -> diagnostics dict
    Sensor identity + sample health, filter state, metrics counters, recent
    events, and the fixed thresholds.  Rendered only in the plugin panel.

``set_notice_acknowledged`` (ack: bool) -> snapshot dict
    Persists the one-time kinetosis notice acknowledgement (ADR 0010).

``get_settings`` () -> ``{"enabled": bool, "notice_acknowledged": bool}``

Startup: if either sensor is missing the pipeline stays ``unavailable`` and
``set_enabled`` cannot activate (ADR 0012).  Overlay visibility over
arbitrary fullscreen content is NOT guaranteed by this backend (see
.planning/IMPLEMENTATION.md - conditional, must be verified per game mode).
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from sensors.adapters import discover
from sensors.settings import Settings
from sensors.state import SensorPipeline

log = logging.getLogger("virtual-horizon")

RATE_HZ = 50.0  # backend sample cadence
STEP_DELAY = 1.0 / RATE_HZ


def _settings_path() -> Path:
    """Persist settings under the Decky plugin dir when running on Deck."""
    try:
        import decky_plugin

        return Path(decky_plugin.PLUGIN_DIR) / "settings.json"
    except Exception:  # pragma: no cover - not importable off-Deck
        return Path("settings.json")


def _build_pipeline() -> SensorPipeline:
    found = discover()
    log.info("sensor discovery: %s", found["devices"])
    return SensorPipeline(
        accel=found["accel"],
        gyro=found["gyro"],
        settings=Settings(_settings_path()),
    )


class Plugin:
    """Decky plugin class; the loader instantiates and calls the ``_*`` hooks."""

    async def _main(self) -> None:
        log.info("virtual-horizon backend starting")
        self._pipeline = _build_pipeline()
        self._running = True
        threading.Thread(target=self._loop, name="sensor-pipeline", daemon=True).start()

    async def _unload(self) -> None:
        self._running = False

    def _loop(self) -> None:
        while self._running:
            try:
                self._pipeline.step()
            except Exception:
                log.exception("pipeline step failed")
            time.sleep(STEP_DELAY)

    # -- RPC methods --------------------------------------------------------

    def _frontend_state(self) -> dict:
        raw = self._pipeline.snapshot()
        sensors = raw["sensors"]
        horizon = None
        if raw["state"] in {"active", "degraded"}:
            horizon = {
                "roll": max(-1.0, min(1.0, raw["orientation"]["roll_deg"] / 45.0)),
                "pitch": max(-1.0, min(1.0, raw["orientation"]["pitch_deg"] / 45.0)),
                "confidence": raw["confidence"],
                "degraded": raw["degraded"],
                "timestamp": int(time.time() * 1000),
            }
        return {
            "enabled": raw["enabled"],
            "status": raw["state"],
            "sensors": {
                "accelerometer": {"present": sensors["accelerometer"].get("present", False), "readable": "last_error" not in sensors["accelerometer"]},
                "gyroscope": {"present": sensors["gyroscope"].get("present", False), "readable": "last_error" not in sensors["gyroscope"]},
            },
            "safety_latch": raw["state"] == "safety_disabled",
            "disable_reason": (raw["safety"] or {}).get("reason") if raw["safety"] else None,
            "notice_acknowledged": self._pipeline.settings.notice_acknowledged,
            "report_consent": self._pipeline.settings.report_consent,
            "horizon": horizon,
        }

    async def get_state(self) -> dict:
        return self._frontend_state()

    async def set_enabled(self, enabled: bool | dict) -> dict:
        if isinstance(enabled, dict):
            enabled = enabled.get("enabled", False)
        self._pipeline.set_enabled(bool(enabled))
        return self._frontend_state()

    async def get_diagnostics(self) -> dict:
        return self._pipeline.diagnostics()

    async def acknowledge_notice(self) -> dict:
        self._pipeline.settings.set_notice_acknowledged(True)
        return self._frontend_state()

    async def set_report_consent(self, consent: bool | dict) -> dict:
        if isinstance(consent, dict):
            consent = consent.get("consent", False)
        self._pipeline.settings.set_report_consent(bool(consent))
        return self._frontend_state()

    async def submit_comfort_report(self, report: dict) -> dict:
        if not self._pipeline.settings.report_consent:
            return {"submitted": False, "error": "report consent is required"}
        try:
            before = int(report["rating_before"])
            after = int(report["rating_after"])
        except (KeyError, TypeError, ValueError):
            return {"submitted": False, "error": "ratings are required"}
        if not 1 <= before <= 5 or not 1 <= after <= 5:
            return {"submitted": False, "error": "ratings must be between 1 and 5"}
        comment = str(report.get("comment", ""))[:500]
        self._pipeline.settings.record_report({"rating_before": before, "rating_after": after, "comment": comment, "timestamp": int(time.time())})
        return {"submitted": True}
