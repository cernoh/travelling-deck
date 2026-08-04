G = 9.80665

"""Sensor source adapters (ADR 0012).

The pipeline talks to two :class:`SampleSource` objects (accelerometer and
gyroscope) through a two-field protocol, so hardware access stays swappable:

- :class:`IioSensor` reads a Linux IIO device node (sysfs raw + scale files).
- Tests and offline tools inject their own sources (see ``backend/tests``).

Units are SI throughout: acceleration in m/s^2, angular velocity in rad/s.
Values are returned in a canonical frame (x = screen right, y = screen up,
z = out of screen); real devices that disagree need an axis-remapping wrapper
validated on the target Deck.

ponytail: prototype adapter - reads the sysfs ``*_raw`` files at the caller's
cadence instead of using IIO's buffered/triggered interface.  Revisit on real
hardware if read rate or timestamp jitter matters.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol, Tuple

Vector3 = Tuple[float, float, float]

# Standard IIO ABI prefixes.
_ACCEL_PREFIXES = ("in_accel",)
_GYRO_PREFIXES = ("in_anglvel", "in_gyro")


class SampleSource(Protocol):
    """A source of one 3-axis reading, or ``None`` when unreadable.

    The pipeline timestamps readings itself (``time.monotonic()``).
    """

    name: str
    kind: str  # "accel" or "gyro"

    def read(self) -> Optional[Vector3]: ...


class IioSensor:
    """Reads one Linux IIO device's raw + scale files (sysfs ABI).

    Accelerometers expose ``in_accel_{x,y,z}_raw`` / ``in_accel_scale``;
    gyroscopes expose ``in_anglvel_{x,y,z}_raw`` (some drivers use
    ``in_gyro_*_raw``) / ``in_anglvel_scale``.  Units follow the IIO ABI:
    m/s^2 and rad/s.
    """

    def __init__(self, name: str, kind: str, prefix: str, device_dir: Path):
        self.name = name
        self.kind = kind
        self._prefix = prefix
        self._dev = device_dir
        self._raw_files = [device_dir / f"{prefix}_{axis}_raw" for axis in "xyz"]
        self._scale = self._read_scale(device_dir / f"{prefix}_scale")

    @classmethod
    def probe(cls, device_dir: Path) -> Optional["IioSensor"]:
        """Build an :class:`IioSensor` for *device_dir* if it exposes a
        complete x/y/z axis set for one sensor kind, else ``None``."""
        for kind, prefixes in (
            ("accel", _ACCEL_PREFIXES),
            ("gyro", _GYRO_PREFIXES),
        ):
            for prefix in prefixes:
                if all((device_dir / f"{prefix}_{a}_raw").is_file() for a in "xyz"):
                    name = cls._device_name(device_dir) or f"{prefix}@{device_dir.name}"
                    return cls(name, kind, prefix, device_dir)
        return None

    @staticmethod
    def _device_name(device_dir: Path) -> Optional[str]:
        try:
            return (device_dir / "name").read_text().strip()
        except OSError:
            return None

    @staticmethod
    def _read_scale(path: Path) -> float:
        # ponytail: default scale 1.0 when absent; IIO scale files are static.
        try:
            return float(path.read_text().strip())
        except (OSError, ValueError):
            return 1.0

    def read(self) -> Optional[Vector3]:
        """Latest ``(x, y, z)`` in SI units, or ``None`` on any read error."""
        values = []
        for path in self._raw_files:
            try:
                values.append(float(path.read_text().strip()))
            except (OSError, ValueError):
                return None
        return tuple(v * self._scale for v in values)  # type: ignore[return-value]


def discover(iio_root: str | Path = "/sys/bus/iio/devices") -> dict:
    """Locate one accelerometer and one gyroscope among IIO device dirs.

    Returns ``{"accel": IioSensor|None, "gyro": IioSensor|None,
    "devices": [str, ...]}``.  ``devices`` lists every recognized sensor for
    diagnostics.  The caller must validate by reading a sample (both sources
    must produce one) before treating the pair as available.
    """
    root = Path(iio_root)
    accel: Optional[IioSensor] = None
    gyro: Optional[IioSensor] = None
    devices: list[str] = []
    if not root.is_dir():
        return {"accel": None, "gyro": None, "devices": devices}
    for entry in sorted(root.glob("iio:device*")):
        dev = IioSensor.probe(entry)
        if dev is None:
            continue
        devices.append(f"{dev.name} ({dev.kind})")
        if dev.kind == "accel" and accel is None:
            accel = dev
        elif dev.kind == "gyro" and gyro is None:
            gyro = dev
    return {"accel": accel, "gyro": gyro, "devices": devices}
