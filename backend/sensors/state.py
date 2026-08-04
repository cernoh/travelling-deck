"""Backend state machine and sample pipeline (ADR 0007, 0011, 0012).

States::

    Unavailable -> Ready -> Active <-> Degraded
                      ^          |   |
                      |          v   v
                      +---- SafetyDisabled (latched)

- ``Unavailable``: one or both sensors missing/unreadable.  Activation is
  refused (fail closed).
- ``Ready``: both sensors valid, overlay not active (user disabled).
- ``Active``: tracking the virtual horizon.
- ``Degraded``: sensors present but confidence is low; the horizon holds the
  last trusted orientation with bounded, heavily damped prediction and
  recovers automatically after sustained confidence (ADR 0002).
- ``SafetyDisabled``: latched on sensor failure or erratic motion while
  active.  Only an explicit user re-enable exits it (ADR 0011, 0012).

``SensorPipeline.step()`` advances everything by one sample and is driven by
the caller (a thread in ``backend/main.py``, a loop in tests) - no I/O, no
threads here, fully testable without Deck hardware.
"""

from __future__ import annotations

import enum
import time
from collections import deque
from typing import Optional

from .adapters import SampleSource, Vector3
from .filter import OrientationFilter
from .settings import Settings

# Fixed state-machine thresholds (ADR 0011: not user-adjustable).
DEGRADED_CONF = 0.5          # smoothed confidence below this...
DEGRADED_STEPS = 25          # ...for this many steps -> Degraded (~0.5 s)
RECOVERY_CONF = 0.75         # smoothed confidence above this...
RECOVERY_STEPS = 60          # ...for this many steps -> Active (~1.2 s)
UNAVAILABLE_RECOVERY_STEPS = 10  # both sensors OK this long -> Ready


class State(str, enum.Enum):
    UNAVAILABLE = "unavailable"
    READY = "ready"
    ACTIVE = "active"
    DEGRADED = "degraded"
    SAFETY_DISABLED = "safety_disabled"


class SensorPipeline:
    """Owns sensor sources, filter, state, safety latch, and metrics."""

    def __init__(
        self,
        accel: Optional[SampleSource] = None,
        gyro: Optional[SampleSource] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.accel = accel
        self.gyro = gyro
        self.settings = settings or Settings()
        self.filter = OrientationFilter()

        self.state = State.UNAVAILABLE
        self.safety_reason: Optional[str] = None
        self.safety_ts: Optional[float] = None

        self._degraded_streak = 0
        self._recovery_streak = 0
        self._unavailable_streak = 0
        self._last_step: Optional[float] = None

        # Per-source health for diagnostics (readable/samples/last_error).
        self.sensor_stats = {
            "accel": {"samples": 0, "last_error": None},
            "gyro": {"samples": 0, "last_error": None},
        }
        self._last_wall: Optional[float] = None  # wall clock of last sample

        # Bounded diagnostics (metrics counters + recent events).
        self.metrics = {
            "samples": 0,
            "read_failures": 0,
            "degraded_steps": 0,
            "jump_rejections": 0,
            "erratic_events": 0,
            "safety_events": 0,
            "state_entries": {s.value: 0 for s in State},
        }
        self.events: deque = deque(maxlen=20)

        self._validate_sensors()
        if self.settings.enabled and self.state is State.READY:
            self._enter_active()

    # -- public API --------------------------------------------------------

    def step(self, now: Optional[float] = None) -> None:
        """Advance one sample: read both sensors and update state."""
        now = now if now is not None else time.monotonic()
        dt = 0.0 if self._last_step is None else max(0.0, now - self._last_step)
        self._last_step = now

        accel = None if self.accel is None else self.accel.read()
        gyro = None if self.gyro is None else self.gyro.read()
        self._record_read("accel", accel)
        self._record_read("gyro", gyro)
        self._last_wall = time.time()

        if accel is None or gyro is None:
            self._handle_read_failure(accel, gyro, now)
            return

        self.metrics["samples"] += 1

        if self.state in (State.ACTIVE, State.DEGRADED):
            degraded = self.state is State.DEGRADED
            res = self.filter.update(accel, gyro, dt, degraded=degraded)
            self.metrics["jump_rejections"] += 1 if res.jumped else 0
            if res.erratic:
                self._safety("erratic_motion", now)
                return
            self._update_confidence_state(res)
        elif self.state is State.READY:
            if self.settings.enabled:
                self._enter_active()
        elif self.state is State.UNAVAILABLE:
            self._unavailable_streak += 1
            if self._unavailable_streak >= UNAVAILABLE_RECOVERY_STEPS:
                self._enter(State.READY)
                self._unavailable_streak = 0

    def set_enabled(self, enabled: bool) -> dict:
        """Manual enable/disable (ADR 0007).  Explicit user action clears the
        safety latch; enabling is refused while sensors are unavailable, and
        ``enabled`` is only persisted when activation actually succeeds (fail
        closed, ADR 0012)."""
        self._clear_safety_latch()
        if not enabled:
            self.settings.set_enabled(False)
            if self.state in (State.ACTIVE, State.DEGRADED):
                self._enter(State.READY)
            return self.snapshot()
        # Enabling: fail closed unless both sensors are readable right now.
        if not self._sensors_ok():
            self.settings.set_enabled(False)
            self._enter(State.UNAVAILABLE)
            return self.snapshot()
        self.settings.set_enabled(True)
        if self.state is not State.ACTIVE:
            self._enter_active()
        return self.snapshot()
    def snapshot(self) -> dict:
        """Render-state snapshot for the frontend bridge (get_state)."""
        roll, pitch = self.filter.display_angles(self.filter.up())
        return {
            "state": self.state.value,
            "enabled": self.settings.enabled,
            "orientation": {"roll_deg": roll, "pitch_deg": pitch},
            "confidence": self.filter._smoothed_confidence,  # noqa: SLF001
            "degraded": self.state is State.DEGRADED,
            "sensors": {
                "accelerometer": self._source_info(self.accel),
                "gyroscope": self._source_info(self.gyro),
            },
            "safety": (
                {"reason": self.safety_reason, "ts": self.safety_ts}
                if self.safety_reason
                else None
            ),
        }

    def diagnostics(self) -> dict:
        """On-demand diagnostics (ADR 0010, 0011)."""
        res = self.snapshot()
        res["metrics"] = dict(self.metrics)
        res["filter"] = {
            "steps": self.filter.steps,
            "jump_rejections": self.filter.jump_rejections,
            "up": list(self.filter.up()),
            "trusted_up": list(self.filter.trusted_up),
            "smoothed_rate_deg_s": round(
                self.filter._smoothed_rate * 180.0 / 3.141592653589793, 2
            ),
        }
        res["thresholds"] = {
            "degraded_confidence": DEGRADED_CONF,
            "recovery_confidence": RECOVERY_CONF,
            "erratic_rate_deg_s": round(
                OrientationFilter.ERRATIC_RATE * 180.0 / 3.141592653589793, 1
            ),
            "degraded_max_angle_deg": round(
                OrientationFilter.DEGRADED_MAX_ANGLE * 180.0 / 3.141592653589793, 1
            ),
        }
        res["events"] = list(self.events)
        return res

    # -- internals ---------------------------------------------------------

    def _sensors_ok(self) -> bool:
        """Probe both sources (never short-circuit) and record health."""
        if self.accel is None or self.gyro is None:
            return False
        a = self.accel.read()
        g = self.gyro.read()
        self._record_read("accel", a)
        self._record_read("gyro", g)
        return a is not None and g is not None

    def _record_read(self, which: str, value: Optional[Vector3]) -> None:
        stat = self.sensor_stats[which]
        if value is None:
            stat["last_error"] = "read_failed"
        else:
            stat["samples"] += 1
            stat["last_error"] = None

    @staticmethod
    def _source_info(source: Optional[SampleSource]) -> dict:
        if source is None:
            return {"present": False}
        return {"present": True, "name": source.name, "kind": source.kind}

    def _validate_sensors(self) -> None:
        if self._sensors_ok():
            self._enter(State.READY)
        else:
            self._enter(State.UNAVAILABLE)

    def _enter(self, state: State) -> None:
        self.state = state
        self.metrics["state_entries"][state.value] += 1
        self.events.append({"ts": time.monotonic(), "event": f"state:{state.value}"})

    def _enter_active(self) -> None:
        # (Re)start tracking from the current accel reading so the horizon
        # does not jump from a stale attitude.
        reading = self.accel.read() if self.accel is not None else None
        if reading is not None:
            self.filter.reset(reading)
        self._degraded_streak = 0
        self._recovery_streak = 0
        self._enter(State.ACTIVE)

    def _handle_read_failure(
        self,
        accel: Optional[Vector3],
        gyro: Optional[Vector3],
        now: float,
    ) -> None:
        self.metrics["read_failures"] += 1
        if self.state in (State.ACTIVE, State.DEGRADED):
            missing = []
            if accel is None:
                missing.append("accelerometer")
            if gyro is None:
                missing.append("gyroscope")
            self._safety("sensor_failure:" + ",".join(missing), now)
        elif self.state is State.READY:
            # Not active: no overlay to disable, just drop to unavailable.
            self._enter(State.UNAVAILABLE)
            self._unavailable_streak = 0

    def _update_confidence_state(self, res) -> None:
        if self.state is State.ACTIVE:
            if res.smoothed_confidence < DEGRADED_CONF:
                self._degraded_streak += 1
                if self._degraded_streak >= DEGRADED_STEPS:
                    self.filter.begin_degraded()
                    self._enter(State.DEGRADED)
            else:
                self._degraded_streak = 0
        elif self.state is State.DEGRADED:
            self.metrics["degraded_steps"] += 1
            if res.smoothed_confidence > RECOVERY_CONF:
                self._recovery_streak += 1
                if self._recovery_streak >= RECOVERY_STEPS:
                    self._enter(State.ACTIVE)
            else:
                self._recovery_streak = 0

    def _safety(self, reason: str, now: float) -> None:
        """Latch off the overlay (ADR 0011): persist, record, never auto-retry."""
        self.safety_reason = reason
        self.safety_ts = now
        self.settings.set_enabled(False)
        self.metrics["safety_events"] += 1
        if reason == "erratic_motion":
            self.metrics["erratic_events"] += 1
        self.events.append({"ts": now, "event": f"safety:{reason}"})
        self._enter(State.SAFETY_DISABLED)

    def _clear_safety_latch(self) -> None:
        if self.state is State.SAFETY_DISABLED:
            self.safety_reason = None
            self.safety_ts = None
