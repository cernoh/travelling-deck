# Bound Degraded-Sensor Prediction

When sensor confidence drops while both required sensors remain available, the plugin will hold the last trusted virtual horizon while allowing only bounded, damped prediction of vehicle movement. This aims to reduce visible discontinuities without presenting unconstrained guesses as reliable orientation.

The degraded-sensor status will be available on demand rather than persistently displayed, keeping the experience fluid while retaining diagnostics for users who need them. If either required sensor fails, the separate sensor-failure decision applies: immediate latched disable. When noisy readings recover, normal tracking resumes automatically only after the plugin confirms sustained sensor confidence.

## Considered Options

Unbounded prediction was rejected because invented motion can create a moving reference and worsen disorientation. Freeze-only behavior was rejected because a completely static reference may expose abrupt degradation and feel disconnected from travel motion. A persistent status indicator was rejected because it would add visual clutter during normal use. Treating noisy readings as hardware failure was rejected because bounded prediction can safely distinguish degraded confidence from missing sensors. Requiring manual recovery after confidence returns was rejected because it would make transient noise unnecessarily disruptive.
