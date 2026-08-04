# Require Motion Sensors

The plugin will be completely unavailable on hardware or software without both an accelerometer and gyroscope. The pair is required to estimate gravity-dominant orientation and reject or bound motion-induced changes; a screen-fixed fallback or warning-based degraded mode would violate the Virtual Horizon’s real-world meaning and could imply a level estimate that does not exist.

If either required sensor fails while active, the plugin immediately disables the overlay and latches it off until the user manually re-enables it after the sensors recover.
