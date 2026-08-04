"""State machine tests (ADR 0007, 0011, 0012): transitions and fail-closed."""

from __future__ import annotations

import unittest

from sensors.state import (
    DEGRADED_CONF,
    DEGRADED_STEPS,
    RECOVERY_CONF,
    RECOVERY_STEPS,
    UNAVAILABLE_RECOVERY_STEPS,
    SensorPipeline,
    State,
)

from .fakes import FakeSource, flat_accel, flat_gyro, run


class FailClosedTest(unittest.TestCase):
    def test_no_sensors_is_unavailable(self):
        p = SensorPipeline(accel=None, gyro=None)
        self.assertIs(p.state, State.UNAVAILABLE)
        # Enabling must be refused (fail closed).
        snap = p.set_enabled(True)
        self.assertIs(p.state, State.UNAVAILABLE)
        self.assertFalse(snap["enabled"])

    def test_missing_gyro_is_unavailable(self):
        p = SensorPipeline(accel=FakeSource("accel", constant=flat_accel()), gyro=None)
        self.assertIs(p.state, State.UNAVAILABLE)

    def test_activation_refused_when_sensor_unreadable(self):
        accel = FakeSource("accel", constant=flat_accel(), fail_steps={1})
        gyro = FakeSource("gyro", constant=flat_gyro())
        p = SensorPipeline(accel=accel, gyro=gyro)
        self.assertIs(p.state, State.UNAVAILABLE)  # probe read failed
        self.assertIs(p.state, State.UNAVAILABLE)

    def test_unavailable_recovers_when_sensors_return(self):
        accel = FakeSource("accel", constant=flat_accel(), fail_steps={1})
        gyro = FakeSource("gyro", constant=flat_gyro(), fail_steps={1})
        p = SensorPipeline(accel=accel, gyro=gyro)
        self.assertIs(p.state, State.UNAVAILABLE)
        run(p, UNAVAILABLE_RECOVERY_STEPS)
        self.assertIs(p.state, State.READY)


class ReadyActiveTest(unittest.TestCase):
    def _pipeline(self):
        accel = FakeSource("accel", constant=flat_accel())
        gyro = FakeSource("gyro", constant=flat_gyro())
        return SensorPipeline(accel=accel, gyro=gyro)

    def test_ready_when_disabled(self):
        p = self._pipeline()
        self.assertIs(p.state, State.READY)
        self.assertFalse(p.settings.enabled)  # default off (ADR 0007)

    def test_enable_activates_and_disable_returns_to_ready(self):
        p = self._pipeline()
        snap = p.set_enabled(True)
        self.assertIs(p.state, State.ACTIVE)
        self.assertTrue(snap["enabled"])
        snap = p.set_enabled(False)
        self.assertIs(p.state, State.READY)
        self.assertFalse(snap["enabled"])

    def test_enabled_pipeline_activates_on_first_step(self):
        p = self._pipeline()
        p.set_enabled(True)
        p.set_enabled(False)
        p.set_enabled(True)
        self.assertIs(p.state, State.ACTIVE)

    def test_enable_clears_safety_latch(self):
        p = self._pipeline()
        p.set_enabled(True)
        self.assertIs(p.state, State.ACTIVE)
        p._safety("erratic_motion", 1.0)
        self.assertIs(p.state, State.SAFETY_DISABLED)
        snap = p.set_enabled(True)
        self.assertIs(p.state, State.ACTIVE)
        self.assertIsNone(snap["safety"])


class SafetyLatchesTest(unittest.TestCase):
    def _active_pipeline(self):
        accel = FakeSource("accel", constant=flat_accel())
        gyro = FakeSource("gyro", constant=flat_gyro())
        p = SensorPipeline(accel=accel, gyro=gyro)
        p.set_enabled(True)
        self.assertIs(p.state, State.ACTIVE)
        return p

    def test_sensor_failure_while_active_latches(self):
        p = self._active_pipeline()
        p.accel = FakeSource("accel", constant=flat_accel(), fail_steps={1})
        run(p, 1)
        self.assertIs(p.state, State.SAFETY_DISABLED)
        self.assertEqual(p.safety_reason, "sensor_failure:accelerometer")
        self.assertFalse(p.settings.enabled)

    def test_latch_persists_despite_recovered_sensors(self):
        p = self._active_pipeline()
        p.accel = FakeSource("accel", constant=flat_accel(), fail_steps={1})
        run(p, 1)
        self.assertIs(p.state, State.SAFETY_DISABLED)
        # Sensors recover: the latch must NOT auto-clear (ADR 0011).
        p.accel = FakeSource("accel", constant=flat_accel())
        run(p, 200)
        self.assertIs(p.state, State.SAFETY_DISABLED)
        self.assertIsNotNone(p.safety_reason)

    def test_erratic_motion_while_active_latches(self):
        p = self._active_pipeline()
        p.gyro = FakeSource("gyro", constant=(3.0, 0.0, 0.0))  # 172 deg/s
        run(p, 2 * 50 + 20)
        self.assertIs(p.state, State.SAFETY_DISABLED)
        self.assertEqual(p.safety_reason, "erratic_motion")

    def test_sensor_loss_in_ready_is_not_latched(self):
        p = self._active_pipeline()
        p.set_enabled(False)
        self.assertIs(p.state, State.READY)
        p.accel = FakeSource("accel", constant=flat_accel(), fail_steps={1})
        run(p, 1)
        # Not active -> no overlay to disable -> just unavailable.
        self.assertIs(p.state, State.UNAVAILABLE)
        self.assertIsNone(p.safety_reason)


class DegradedRecoveryTest(unittest.TestCase):
    def test_noisy_readings_enter_degraded_and_recover(self):
        accel = FakeSource("accel", constant=flat_accel())
        gyro = FakeSource("gyro", constant=flat_gyro())
        p = SensorPipeline(accel=accel, gyro=gyro)
        p.set_enabled(True)

        # Noisy accelerometer: sustained linear acceleration (2g on z).
        p.accel = FakeSource("accel", constant=(0.0, 0.0, 2.0 * 9.80665))
        run(p, DEGRADED_STEPS + 10)
        self.assertIs(p.state, State.DEGRADED)

        # Sensors recover (and are both still present): sustained confidence
        # must return tracking to Active automatically (ADR 0002).
        p.accel = FakeSource("accel", constant=flat_accel())
        run(p, RECOVERY_STEPS + 10)
        self.assertIs(p.state, State.ACTIVE)

    def test_short_noise_burst_does_not_enter_degraded(self):
        accel = FakeSource("accel", constant=flat_accel())
        gyro = FakeSource("gyro", constant=flat_gyro())
        p = SensorPipeline(accel=accel, gyro=gyro)
        p.set_enabled(True)
        p.accel = FakeSource("accel", constant=(0.0, 0.0, 2.0 * 9.80665))
        run(p, DEGRADED_STEPS // 2)  # shorter than the sustained window
        self.assertIs(p.state, State.ACTIVE)


class SnapshotTest(unittest.TestCase):
    def test_snapshot_shape(self):
        accel = FakeSource("accel", constant=flat_accel())
        gyro = FakeSource("gyro", constant=flat_gyro())
        p = SensorPipeline(accel=accel, gyro=gyro)
        snap = p.snapshot()
        self.assertEqual(snap["state"], State.READY.value)
        self.assertIn("orientation", snap)
        self.assertIn("confidence", snap)
        self.assertTrue(snap["sensors"]["accelerometer"]["present"])
        self.assertTrue(snap["sensors"]["gyroscope"]["present"])

    def test_diagnostics_reports_reason_after_latch(self):
        p = SensorPipeline(
            accel=FakeSource("accel", constant=flat_accel()),
            gyro=FakeSource("gyro", constant=flat_gyro()),
        )
        p.set_enabled(True)
        p._safety("erratic_motion", 42.0)
        diag = p.diagnostics()
        self.assertEqual(diag["state"], State.SAFETY_DISABLED.value)
        self.assertEqual(diag["safety"]["reason"], "erratic_motion")
        self.assertGreater(diag["metrics"]["safety_events"], 0)
        self.assertIn("thresholds", diag)
        self.assertTrue(any("safety:" in e["event"] for e in diag["events"]))


if __name__ == "__main__":
    unittest.main()
