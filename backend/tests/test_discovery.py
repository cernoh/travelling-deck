"""IIO discovery and adapter tests (ADR 0012) using a fake sysfs layout."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sensors.adapters import G, IioSensor, discover


def make_device(tmp: Path, name: str, files: dict) -> Path:
    dev = tmp / name
    dev.mkdir()
    (dev / "name").write_text("testdev\n")
    for rel, value in files.items():
        (dev / rel).write_text(str(value))
    return dev


ACCEL_RAW = {"in_accel_x_raw": 100, "in_accel_y_raw": 0, "in_accel_z_raw": 981}
ACCEL_SCALE = 0.00980665  # m/s^2 per LSB -> 100 LSB = ~1 g on x


class DiscoveryTest(unittest.TestCase):
    def test_finds_accel_and_gyro(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_device(root, "iio:device0", ACCEL_RAW | {"in_accel_scale": ACCEL_SCALE})
            make_device(
                root,
                "iio:device1",
                {"in_anglvel_x_raw": 100, "in_anglvel_y_raw": 0, "in_anglvel_z_raw": 0,
                 "in_anglvel_scale": 0.001},
            )
            found = discover(root)
            self.assertIsNotNone(found["accel"])
            self.assertIsNotNone(found["gyro"])
            self.assertEqual(len(found["devices"]), 2)

    def test_missing_root_yields_nothing(self):
        found = discover("/nonexistent/iio")
        self.assertIsNone(found["accel"])
        self.assertIsNone(found["gyro"])

    def test_only_accel_present(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_device(root, "iio:device0", ACCEL_RAW | {"in_accel_scale": ACCEL_SCALE})
            found = discover(root)
            self.assertIsNotNone(found["accel"])
            self.assertIsNone(found["gyro"])  # fail closed without gyro

    def test_gyro_alias_in_gyro_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_device(
                root,
                "iio:device0",
                {"in_gyro_x_raw": 1, "in_gyro_y_raw": 1, "in_gyro_z_raw": 1,
                 "in_gyro_scale": 0.001},
            )
            found = discover(root)
            self.assertIsNotNone(found["gyro"])

    def test_incomplete_axis_set_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            make_device(root, "iio:device0", {"in_accel_x_raw": 1, "in_accel_y_raw": 1})
            found = discover(root)
            self.assertIsNone(found["accel"])
            self.assertEqual(found["devices"], [])


class IioSensorTest(unittest.TestCase):
    def test_read_scales_raw(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dev = make_device(root, "iio:device0", ACCEL_RAW | {"in_accel_scale": ACCEL_SCALE})
            sensor = IioSensor.probe(dev)
            self.assertIsNotNone(sensor)
            x, y, z = sensor.read()
            self.assertAlmostEqual(x, G, places=4)
            self.assertAlmostEqual(z, G * 0.981 / 0.01, places=2)  # 981 LSB * scale

    def test_read_returns_none_on_missing_raw(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dev = make_device(
                root, "iio:device0", {"in_accel_x_raw": 1, "in_accel_y_raw": 1,
                                     "in_accel_z_raw": 1}
            )
            sensor = IioSensor.probe(dev)
            self.assertIsNotNone(sensor)
            (dev / "in_accel_z_raw").unlink()
            self.assertIsNone(sensor.read())  # unreadable -> None -> fail closed

    def test_missing_scale_defaults_to_one(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dev = make_device(root, "iio:device0", ACCEL_RAW)
            sensor = IioSensor.probe(dev)
            x, _, _ = sensor.read()
            self.assertEqual(x, 100.0)


if __name__ == "__main__":
    unittest.main()
