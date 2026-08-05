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

## Install

Install Decky Loader on the Steam Deck before you install this plugin.

1. Download or clone this repository on the Steam Deck.
2. Open a terminal in the repository directory.
3. Build the frontend:

   ```sh
   cd frontend
   npm ci
   npm run build
   ```

4. Copy the repository directory to the Decky plugin directory:

   ```sh
   sudo mkdir -p /home/deck/homebrew/plugins/travelling-deck
   sudo cp -r . /home/deck/homebrew/plugins/travelling-deck/
   ```

5. Restart Decky Loader from its settings menu.
6. Open the Decky menu and select Travelling Deck.
7. Read the health notice, then enable the plugin when both sensors show as available.

The current package is a development prototype. Decky overlay visibility above arbitrary games is not guaranteed. Remove the directory to uninstall the plugin:

```sh
sudo rm -rf /home/deck/homebrew/plugins/travelling-deck
```

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
