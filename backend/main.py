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

    async def get_state(self) -> dict:
        return self._pipeline.snapshot()

    async def set_enabled(self, enabled: bool) -> dict:
        return self._pipeline.set_enabled(bool(enabled))

    async def get_diagnostics(self) -> dict:
        return self._pipeline.diagnostics()

    async def set_notice_acknowledged(self, ack: bool) -> dict:
        self._pipeline.settings.set_notice_acknowledged(bool(ack))
        return self._pipeline.snapshot()

    async def get_settings(self) -> dict:
        return {
            "enabled": self._pipeline.settings.enabled,
            "notice_acknowledged": self._pipeline.settings.notice_acknowledged,
        }
