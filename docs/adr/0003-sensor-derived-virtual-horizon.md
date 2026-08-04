# Use a Sensor-Derived Virtual Horizon

The plugin will use device-sensor orientation to anchor the virtual horizon to the user’s real-world level, rather than a screen-fixed overlay. This follows the Kinestop-style experience the user wants and keeps the reference meaningful during travel, despite the added challenge of filtering acceleration and sensor uncertainty.

## Considered Options

A screen-fixed reference was rejected because it does not represent real-world level orientation; it only stays fixed relative to the display.
