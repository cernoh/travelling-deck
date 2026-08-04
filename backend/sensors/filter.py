"""Gravity-dominant orientation estimation (ADR 0001, 0002, 0003, 0008).

The filter tracks the world "up" direction expressed in device coordinates
(a unit vector).  Per sample it:

1. propagates ``up`` with the gyroscope (``up += omega x up * dt``);
2. blends toward the accelerometer-measured up with a complementary gain,
   rejecting single-sample implausible jumps outright (a persistent deviation
   is trusted again after a sustained window, ADR 0001/0008);
3. in degraded mode, applies a heavy gyro damping and clamps the total
   deviation from the last trusted orientation (bounded prediction, ADR 0002);
4. scores confidence from accelerometer-magnitude deviation and smoothed
   angular rate, and flags erratic motion for the state machine (ADR 0011).

Rotations around the screen normal (z, device "bank" as seen by the user) do
not move ``up`` and are deliberately ignored: the virtual horizon is anchored
to the world and must not recenter with the viewing angle (ADR 0008).

All thresholds below are fixed, per ADR 0011 (tunable later only from data).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

G = 9.80665  # standard gravity, m/s^2


@dataclass(frozen=True)
class FilterResult:
    """Per-step outcome consumed by the state machine."""

    confidence: float          # 0..1, this sample
    smoothed_confidence: float  # 0..1, EMA
    rate: float                # |omega|, rad/s (smoothed)
    erratic: bool              # sustained violent motion -> safety latch
    jumped: bool               # an implausible accel jump was rejected
    up: tuple[float, float, float]
    roll_deg: float
    pitch_deg: float


def _mag(v: tuple[float, float, float]) -> float:
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _norm(v: tuple[float, float, float]) -> tuple[float, float, float] | None:
    m = _mag(v)
    if m < 1e-9:
        return None
    return (v[0] / m, v[1] / m, v[2] / m)


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _angle(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
    return math.acos(max(-1.0, min(1.0, d)))


class OrientationFilter:
    """Complementary filter over the device-frame world-up vector.

    All public constants are fixed safety/behavior thresholds.
    """

    # Complementary gains: fraction of the accel correction applied per step.
    ACCEL_GAIN = 0.05           # normal tracking
    DEGRADED_ACCEL_GAIN = 0.005  # degraded: barely trust the accelerometer
    DEGRADED_GYRO_GAIN = 0.1    # degraded: heavy damping of gyro propagation

    # Jump rejection: a single sample deviating more than this from the
    # current up is ignored.  If the same direction persists (a real attitude
    # change, e.g. the Deck placed on a slope), it is trusted again after
    # TRUST_STEPS consecutive samples (ADR 0001, 0008).
    JUMP_MAX_ANGLE = math.radians(20.0)
    TRUST_STEPS = 100  # ~2 s at 50 Hz

    # Bounded prediction: total deviation from the last trusted orientation.
    DEGRADED_MAX_ANGLE = math.radians(20.0)

    # Erratic motion: smoothed |omega| above this, sustained, trips safety.
    ERRATIC_RATE = math.radians(90.0)  # deg/s
    ERRATIC_STEPS = 50                 # ~1 s at 50 Hz

    # Confidence scoring.
    CONF_DEV_SCALE = 0.35  # accel magnitude deviation that zeroes confidence
    CONF_SMOOTH = 0.05     # EMA alpha for smoothed confidence
    RATE_SMOOTH = 0.2      # EMA alpha for smoothed rate

    def __init__(self) -> None:
        self._up: tuple[float, float, float] = (0.0, 0.0, 1.0)
        self.trusted_up: tuple[float, float, float] = self._up
        self._smoothed_confidence = 1.0
        self._smoothed_rate = 0.0
        self._erratic_streak = 0
        self._jump_streak = 0
        self.jump_rejections = 0
        self.steps = 0

    # -- lifecycle ---------------------------------------------------------

    def reset(self, up: tuple[float, float, float]) -> None:
        """(Re)start tracking from *up* (e.g. the current accel reading)."""
        self._up = up
        self.trusted_up = up
        self._smoothed_confidence = 1.0
        self._smoothed_rate = 0.0
        self._erratic_streak = 0
        self._jump_streak = 0
        self.steps = 0

    def begin_degraded(self) -> None:
        """Freeze the trusted reference when degraded tracking starts."""
        self.trusted_up = self._up

    def up(self) -> tuple[float, float, float]:
        return self._up

    # -- filtering ---------------------------------------------------------

    def update(
        self,
        accel: tuple[float, float, float],
        gyro: tuple[float, float, float],
        dt: float,
        degraded: bool,
    ) -> FilterResult:
        """Advance the filter by one sample.  *dt* is seconds since last step."""
        self.steps += 1
        accel_up = _norm(accel)

        # Gyro propagation (ignores the omega component along up -> no z-spin).
        u = self._up
        if dt > 0.0:
            w = gyro
            if degraded:
                w = tuple(c * self.DEGRADED_GYRO_GAIN for c in w)
            prop = _norm(
                (
                    u[0] + _cross(w, u)[0] * dt,
                    u[1] + _cross(w, u)[1] * dt,
                    u[2] + _cross(w, u)[2] * dt,
                )
            )
            if prop is not None:
                u = prop

        # Accelerometer correction.  A single sample deviating implausibly far
        # from the current up is rejected outright (it does not even receive
        # the damped gain); a persistent deviation is trusted after TRUST_STEPS.
        jumped = False
        if accel_up is not None and _angle(accel_up, u) > self.JUMP_MAX_ANGLE:
            self._jump_streak += 1
            jumped = True
            self.jump_rejections += 1
            if self._jump_streak < self.TRUST_STEPS:
                accel_up = None  # keep u untouched this step
            else:
                self._jump_streak = 0  # sustained real change: trust again
        elif accel_up is not None:
            self._jump_streak = 0

        if accel_up is not None:
            gain = self.DEGRADED_ACCEL_GAIN if degraded else self.ACCEL_GAIN
            candidate = _norm(
                (
                    u[0] + (accel_up[0] - u[0]) * gain,
                    u[1] + (accel_up[1] - u[1]) * gain,
                    u[2] + (accel_up[2] - u[2]) * gain,
                )
            )
            if candidate is not None:
                u = candidate

        # Bounded prediction: never stray past the trusted reference in
        # degraded mode (ADR 0002) - clamp at the boundary.
        if degraded and _angle(u, self.trusted_up) > self.DEGRADED_MAX_ANGLE:
            u = self._clamp_to_trusted(u)
        self._up = u

        # Confidence from accelerometer magnitude deviation...
        mag = _mag(accel)
        dev = abs(mag / G - 1.0) if mag > 0.0 else 1.0
        confidence = max(0.0, 1.0 - dev / self.CONF_DEV_SCALE)
        # ...further reduced by violent motion.
        rate = _mag(gyro)
        confidence *= max(0.0, 1.0 - rate / self.ERRATIC_RATE)

        self._smoothed_confidence += self.CONF_SMOOTH * (
            confidence - self._smoothed_confidence
        )
        self._smoothed_rate += self.RATE_SMOOTH * (rate - self._smoothed_rate)

        # Erratic motion: sustained smoothed angular rate above threshold.
        self._erratic_streak = (
            self._erratic_streak + 1
            if self._smoothed_rate > self.ERRATIC_RATE
            else 0
        )
        erratic = self._erratic_streak >= self.ERRATIC_STEPS

        roll, pitch = self.display_angles(u)
        return FilterResult(
            confidence=confidence,
            smoothed_confidence=self._smoothed_confidence,
            rate=self._smoothed_rate,
            erratic=erratic,
            jumped=jumped,
            up=u,
            roll_deg=roll,
            pitch_deg=pitch,
        )

    # -- helpers -----------------------------------------------------------

    def _clamp_to_trusted(self, u: tuple[float, float, float]):
        # Slerp toward the trusted up until the angle budget is exhausted.
        cos_a = (
            self.trusted_up[0] * u[0]
            + self.trusted_up[1] * u[1]
            + self.trusted_up[2] * u[2]
        )
        cos_a = max(-1.0, min(1.0, cos_a))
        a = math.acos(cos_a)
        if a < 1e-9:
            return self.trusted_up
        t = self.DEGRADED_MAX_ANGLE / a
        s = math.sin(a)
        return (
            (math.sin((1.0 - t) * a) * self.trusted_up[0] + math.sin(t * a) * u[0]) / s,
            (math.sin((1.0 - t) * a) * self.trusted_up[1] + math.sin(t * a) * u[1]) / s,
            (math.sin((1.0 - t) * a) * self.trusted_up[2] + math.sin(t * a) * u[2]) / s,
        )

    @staticmethod
    def display_angles(
        up: tuple[float, float, float],
    ) -> tuple[float, float]:
        """Map the tracked up vector to display parameters.

        ``roll_deg``: horizon line rotation on screen (0 = level; a line, so
        normalized to (-90, 90]).  ``pitch_deg``: horizon vertical offset
        (0 = centered; positive = horizon shifts down as the device tilts
        back).  Sign conventions are validated on hardware; the frontend may
        flip either if the physical mounting differs.
        """
        ux, uy, uz = up
        roll = 0.0
        if ux * ux + uy * uy > 1e-9:
            roll = math.degrees(math.atan2(-ux, uy))
            if roll > 90.0:
                roll -= 180.0
            elif roll <= -90.0:
                roll += 180.0
        pitch = math.degrees(math.atan2(-uy, uz))
        return roll, pitch
