"""Test doubles: deterministic sensor sources for off-device testing."""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

from sensors.adapters import Vector3

G = 9.80665


class FakeSource:
    """Replays a scripted ``(x, y, z)`` sequence.

    ``constant`` repeats forever; otherwise the sequence is consumed and
    ``None`` (sensor loss) is returned once exhausted.  ``fail_after`` stops
    returning values after that many reads.  Recorded per-step failures can
    be injected with ``fail_steps`` (a set of read indices, 1-based).
    """

    def __init__(
        self,
        kind: str,
        name: str = "fake",
        constant: Optional[Vector3] = None,
        sequence: Optional[Sequence[Vector3]] = None,
        fail_steps: Optional[set] = None,
    ) -> None:
        self.kind = kind
        self.name = name
        self._constant = constant
        self._sequence = list(sequence) if sequence else []
        self._fail_steps = fail_steps or set()
        self.reads = 0

    def read(self) -> Optional[Vector3]:
        self.reads += 1
        if self.reads in self._fail_steps:
            return None
        if self._constant is not None:
            return self._constant
        if self.reads <= len(self._sequence):
            return self._sequence[self.reads - 1]
        return None

    def reset(self) -> None:
        self.reads = 0


def flat_accel() -> Vector3:
    """At-rest accelerometer reading (screen up): +1g on z."""
    return (0.0, 0.0, G)


def flat_gyro() -> Vector3:
    return (0.0, 0.0, 0.0)


def run(pipeline, n: int, dt: float = 0.02, now0: float = 0.0) -> None:
    """Advance the pipeline ``n`` steps at a fixed cadence."""
    for i in range(n):
        pipeline.step(now0 + (i + 1) * dt)
