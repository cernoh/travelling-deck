# Filter Transient Motion

The virtual horizon will use gravity-dominant sensor data with bounded, heavily damped adaptation and reject implausible or vehicle-induced orientation changes instead of following raw readings. This trades immediate sensor response for a less disorienting reference during acceleration, braking, and sustained turns, the primary use case.
