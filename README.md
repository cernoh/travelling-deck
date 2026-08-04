# Travelling Deck

Travelling Deck is a Decky plugin for Steam Deck. It shows a Virtual Horizon to help reduce kinetosis during travel.

The plugin does not promise to prevent motion sickness. It is not a medical product.

## Status

This repository contains a backend and a Decky panel prototype.

The backend reads an accelerometer and a gyroscope through Linux IIO interfaces. It fails closed when either sensor is missing or unreadable.

The filter uses gravity-dominant estimation, jump rejection, smoothing, bounded degraded prediction, and sustained-confidence recovery.

The safety fallback disables the plugin after sensor loss or erratic motion. The plugin stays disabled until the user enables it again.

The panel provides:

- Manual enable and disable.
- Sensor availability and diagnostics.
- The one-time health notice.
- An opt-in comfort report form.
- A transparent, pointer-transparent Artificial Horizon prototype.

Decky does not document an always-on-top compositor layer for every game mode. The prototype does not claim support for arbitrary fullscreen games. Test the target Deck, game, display mode, input focus, and gamescope path before release.

## Development

Enter the Nix development shell:

```sh
nix develop
```

Run the backend tests:

```sh
PYTHONPATH=backend:. python -m unittest discover -s backend/tests -t .
```

Run the frontend tests and type check:

```sh
cd frontend
node --test --experimental-strip-types src/horizon.test.ts
npm ci
npm exec -- tsc --noEmit
```

Run the Nix checks:

```sh
nix flake check
```

## Project layout

- `backend/`: Decky Python entry point, sensor adapters, filter, state machine, and tests.
- `frontend/`: Decky React panel and Artificial Horizon prototype.
- `plugin.json`: Decky plugin metadata.
- `flake.nix`: Nix development shell and metadata check.
- `docs/adr/`: Product and safety decisions.
- `.planning/IMPLEMENTATION.md`: Platform limits and implementation gates.

## Hardware and platform limits

The sensor axis mapping and units require validation on real Steam Deck hardware.

The plugin requires both an accelerometer and a gyroscope. A screen-fixed fallback is not safe because it does not represent the Virtual Horizon.

Comfort reports stay local in this version. Network submission requires a separate privacy and endpoint decision.
