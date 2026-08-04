# Disable on Erratic Horizon Motion

The plugin will always provide manual disable through Decky and the configured shortcut, and it will automatically disable the overlay when the virtual horizon moves beyond a fixed erratic-motion threshold. This protects users from objective sensor or rendering failures without attempting to diagnose subjective kinetosis. Once triggered, the safety disable remains latched until the user manually re-enables the plugin.

The plugin will send a brief Decky notification explaining the safety disable and keep detailed sensor diagnostics available on demand in the plugin panel.

The initial threshold is fixed for safety and consistency; it may be tuned later using measured sensor and user-report data, but it is not user-adjustable.

## Considered Options

Automatic retry after a cooldown was rejected because it could silently reintroduce unstable motion. A retry prompt was rejected because the safest behavior is to remain off until explicit user action. User-adjustable thresholds were rejected because users may select unsafe values before the behavior is understood. Silent disable was rejected because users need to know why the overlay stopped, while persistent diagnostic detail would clutter gameplay.
