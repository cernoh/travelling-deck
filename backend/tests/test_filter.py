"""Orientation filter unit tests (ADR 0001, 0002, 0008)."""

from __future__ import annotations

import math
import unittest

from sensors.filter import G, OrientationFilter

from .fakes import flat_accel, flat_gyro


class FilterBasicsTest(unittest.TestCase):
    def test_flat_reading_stays_flat(self):
        f = OrientationFilter()
        res = f.update(flat_accel(), flat_gyro(), dt=0.02, degraded=False)
        self.assertAlmostEqual(res.roll_deg, 0.0, places=2)
        self.assertAlmostEqual(res.pitch_deg, 0.0, places=2)
        self.assertGreater(res.confidence, 0.99)
        # Sustained flat readings keep the horizon level.
        for _ in range(100):
            res = f.update(flat_accel(), flat_gyro(), dt=0.02, degraded=False)
        self.assertAlmostEqual(res.roll_deg, 0.0, places=2)
        self.assertAlmostEqual(res.pitch_deg, 0.0, places=2)

    def test_gyro_propagation_tilts_up(self):
        f = OrientationFilter()
        # Constant rotation around the screen-x axis (pitch): 1 rad/s for 1 s.
        gyro = (1.0, 0.0, 0.0)
        for _ in range(50):
            f.update(flat_accel(), gyro, dt=0.02, degraded=False)
        roll, pitch = f.display_angles(f.up())
        # The horizon must have moved substantially from level.
        self.assertGreater(abs(pitch), 30.0)
        self.assertLess(abs(pitch), 70.0)
        # But pure pitch rotation must not rotate the horizon line itself.
        self.assertAlmostEqual(roll, 0.0, places=1)

    def test_accel_correction_converges(self):
        f = OrientationFilter()
        # Device tilted: gravity reading now mostly along x.
        tilted = (G * math.sin(math.radians(30)), 0.0, G * math.cos(math.radians(30)))
        for _ in range(300):  # ~6 s at 50 Hz
            f.update(tilted, flat_gyro(), dt=0.02, degraded=False)
        roll, pitch = f.display_angles(f.up())
        self.assertAlmostEqual(roll, 30.0, places=1)  # convention: roll = atan2(-ux, uy)

    def test_jump_rejected(self):
        f = OrientationFilter()
        # One absurd accelerometer reading (90 deg) must not be followed.
        big = (G, 0.0, 0.0)
        res = f.update(big, flat_gyro(), dt=0.02, degraded=False)
        self.assertTrue(res.jumped)
        self.assertLess(f.display_angles(f.up())[0], 20.0)


class DegradedModeTest(unittest.TestCase):
    def test_bounded_prediction_clamps(self):
        f = OrientationFilter()
        f.reset((0.0, 0.0, 1.0))
        f.begin_degraded()
        # 1 rad/s around y (below the erratic threshold) with heavy damping.
        gyro = (0.0, 1.0, 0.0)
        for _ in range(2000):
            f.update(flat_accel(), gyro, dt=0.02, degraded=True)
        angle = math.degrees(
            math.acos(
                max(-1.0, min(1.0, f.up()[0] * 0 + f.up()[1] * 0 + f.up()[2] * 1))
            )
        )
        # Drift from the trusted orientation stays within the bound.
        self.assertLessEqual(angle, math.degrees(f.DEGRADED_MAX_ANGLE) + 1e-6)

    def test_degraded_damping_slows_drift(self):
        f = OrientationFilter()
        # Same motion in normal vs degraded mode: degraded must drift far less.
        f_normal = OrientationFilter()
        gyro = (0.0, 1.0, 0.0)
        for _ in range(100):
            f.update(flat_accel(), gyro, dt=0.02, degraded=True)
            f_normal.update(flat_accel(), gyro, dt=0.02, degraded=False)
        d = f.display_angles(f.up())[1] + f.display_angles(f.up())[0]
        dn = f_normal.display_angles(f_normal.up())[1] + f_normal.display_angles(f_normal.up())[0]
        self.assertLess(abs(d), abs(dn))


class ConfidenceTest(unittest.TestCase):
    def test_confidence_drops_with_magnitude_deviation(self):
        f = OrientationFilter()
        noisy = (0.0, 0.0, 2.0 * G)  # 2x gravity -> linear acceleration
        res = f.update(noisy, flat_gyro(), dt=0.02, degraded=False)
        self.assertLess(res.confidence, 0.05)
        clean = f.update(flat_accel(), flat_gyro(), dt=0.02, degraded=False)
        self.assertGreater(clean.confidence, 0.99)

    def test_high_rate_lowers_confidence(self):
        f = OrientationFilter()
        res = f.update(flat_accel(), (3.0, 0.0, 0.0), dt=0.02, degraded=False)
        self.assertLess(res.confidence, 0.5)

    def test_erratic_detected_after_sustained_motion(self):
        f = OrientationFilter()
        gyro = (3.0, 0.0, 0.0)  # 172 deg/s, well above the 90 deg/s threshold
        erratic = None
        for i in range(2 * f.ERRATIC_STEPS + 20):
            res = f.update(flat_accel(), gyro, dt=0.02, degraded=False)
            if res.erratic:
                erratic = i
                break
        self.assertIsNotNone(erratic)
        self.assertGreaterEqual(erratic, f.ERRATIC_STEPS)

    def test_not_erratic_below_threshold(self):
        f = OrientationFilter()
        gyro = (0.5, 0.0, 0.0)  # ~29 deg/s
        for _ in range(3 * f.ERRATIC_STEPS):
            res = f.update(flat_accel(), gyro, dt=0.02, degraded=False)
            self.assertFalse(res.erratic)


if __name__ == "__main__":
    unittest.main()
