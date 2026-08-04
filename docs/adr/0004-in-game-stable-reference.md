# Display the Reference Over Gameplay

The stable visual reference will appear as a full-screen overlay over the running game and adapt automatically to the active display surface. A full-screen layer avoids resolution, orientation, and display-mode alignment failures while keeping the reference available during gameplay.

## Considered Options

Displaying the reference only in the plugin panel was rejected because it disappears during gameplay. Fixed coordinates and per-game calibration were rejected because they can misalign across display modes and interrupt fluid travel use. User-selectable placement was deferred to avoid adding configuration before the core comfort behavior is validated.
