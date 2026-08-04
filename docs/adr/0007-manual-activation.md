# Require Manual Activation

The plugin will use a manual toggle and default to off. This prevents unexpected visual changes, battery use, or gameplay interference when the user has not chosen travel-comfort assistance. Users can also configure an optional controller shortcut to toggle the overlay quickly during gameplay; the chosen combination is reserved globally because reliable conflict detection is unavailable. The shortcut toggles on release after a 500 ms hold to reduce accidental activation while remaining quick to use.

## Considered Options

Automatic always-on activation was rejected because it changes gameplay without explicit user intent. A Decky-only toggle was rejected because it is too slow for an emergency disable. Requiring a non-conflicting combination was rejected because the plugin cannot reliably detect conflicts. Immediate activation on button-down was rejected because it can trigger accidentally while the combination is being pressed. Per-game profiles were deferred until the core behavior and compatibility are validated.
