# Use a Transparent Overlay Layer

The reference will render in a transparent full-screen layer above gameplay while passing all input through to the game. This avoids game-specific frame injection and preserves normal controls, with compatibility limited to whether Decky can place the layer above each target display mode.

## Considered Options

Compositing into each game’s rendered frame was rejected because it requires game-specific integration and increases compatibility cost. A compatibility-selected dual approach was deferred until target-platform constraints are measured.
