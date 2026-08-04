# Decky feasibility and implementation plan

Research date: 2026-08-04. Scope: ADRs `0001–0008`, `0010–0013` and `CONTEXT.md`.

## Conclusion

Decky is sufficient for a plugin panel, persistent Python backend, settings storage, notifications, and ordinary Decky UI. It is **not sufficient to guarantee the central ADR promise**: a transparent, always-on-top, input-transparent layer over every game/display mode. Decky renders its frontend in Steam's web UI/overlay context; the public plugin APIs do not expose a compositor surface, gamescope layer, or input-routing contract for arbitrary fullscreen games. Treat overlay support as conditional and verify it on a curated compatibility matrix before claiming support.

Motion-sensor access is also conditional: a Decky backend can read Linux device interfaces if SteamOS exposes the IMU to the plugin process, but Decky does not provide a portable accelerometer/gyroscope API. The plugin must discover and validate both devices at runtime and be unavailable otherwise.

## Requirement matrix

| ADR requirement | Decky support | Implementation / limitation |
|---|---|---|
| Panel, settings, manual enable/disable (`0007`, `0011`) | **Confirmed** | Build a normal Decky frontend with `@decky/ui`; call backend methods through the generated plugin bridge. Persist enabled state and shortcut settings in the Python backend. Default off. |
| Decky notification on automatic disable (`0011`) | **Confirmed for Decky UI context** | Use the loader/frontend notification facility exposed by the Decky frontend library. Keep the message short; latch the disabled state in the backend. Verify notification behavior while a game is active. |
| On-demand diagnostics and health notice (`0002`, `0010`, `0011`) | **Confirmed** | Render diagnostics and the one-time kinetosis notice in the plugin panel. Store acknowledgement in backend settings; never place persistent diagnostic text over gameplay. |
| Transparent full-screen overlay over gameplay (`0004`, `0005`) | **Unverified / major platform gap** | Decky plugin UI is a Steam client/web surface, not a documented arbitrary gamescope compositor layer. Do not assume a React panel remains above Vulkan, Proton, exclusive fullscreen, or game-mode surfaces. A prototype must test the exact Decky overlay mechanism on each target mode. If it cannot remain above gameplay, the ADR cannot be implemented with Decky alone; a separate SteamOS/gamescope compositor extension or game-specific injection would be required, both outside the current Decky contract. |
| Input passes through to the game (`0005`) | **Unverified** | No public Decky API guarantees click/key/controller input pass-through from a custom always-on-top surface. The overlay must be tested for focus, controller routing, Steam button/menu behavior, and text input. Never ship assuming CSS `pointer-events:none` solves compositor/input focus. |
| Automatic display/surface adaptation (`0004`) | **Conditional** | A frontend can observe viewport dimensions/orientation, but this does not prove visibility over the game surface. Use normalized coordinates and redraw on resize; validate gamescope scaling, rotation, HDR, fullscreen, Proton, and Vulkan separately. |
| Accelerometer + gyroscope (`0012`) | **Conditional** | Implement discovery in the Python backend using the SteamOS/Linux interfaces actually present on the target Deck (normally IIO/HID device nodes or sysfs). Do not hard-code one device path. Require one valid accelerometer and one valid gyroscope; if either is absent/unreadable, expose an unavailable state and do not activate. If either fails while active, immediately latch disable. Decky itself supplies no sensor abstraction. |
| Gravity-dominant virtual horizon (`0003`, `0008`) | **Conditional, implementable in backend** | Read synchronized accelerometer and gyroscope samples, timestamp them, and estimate orientation in backend code. Keep the virtual horizon device-relative/world-level; do not silently recenter during degraded confidence. The frontend should receive only the latest render state, not own sensor timing. |
| Filtering and bounded adaptation (`0001`, `0002`) | **Implementable in backend** | Maintain last trusted orientation, confidence, and timestamps. Reject implausible jumps; use gyroscope propagation for short gaps; apply gravity-consistent corrections with a strict angular-rate/angle cap and heavy damping. During degraded readings freeze by default and allow only tiny bounded corrections. Resume normal tracking only after sustained confidence. |
| Erratic-motion safety fallback (`0011`) | **Implementable** | Backend owns the fixed threshold and state machine. On threshold breach or sensor failure: disable overlay, latch off, persist reason/time, and emit one Decky notification. Re-enable requires explicit Decky action or configured shortcut. Diagnostics expose the reason on demand. |
| Editable global shortcut, 500 ms release hold (`0007`) | **Unverified / likely requires integration outside public Decky APIs** | Decky panel controls can store a preferred combination, but public Decky plugin documentation does not guarantee a plugin-wide global controller shortcut while a game has focus, conflict detection, or release-time 500 ms handling. First investigate an official Decky input/hotkey API on the target loader version. If absent, implement the shortcut in a privileged SteamOS helper that receives input events, with explicit conflict risks; otherwise retain Decky-only disable and revise the ADR. |
| Unavailable without both sensors (`0012`) | **Implementable** | Runtime capability probe gates activation and panel controls. Show “unsupported: accelerometer/gyroscope unavailable” instead of a screen-fixed fallback. |
| Opt-in anonymous comfort reports (`0013`) | **Implementable, backend/network work required** | Add explicit opt-in UI and send only the agreed minimal before/after rating plus optional comment. Make submission optional and failure non-blocking. Use an HTTPS endpoint with a documented data-minimization/privacy policy; Decky does not provide an anonymous reporting service. Do not collect reports until consent is recorded. |
| Technical metrics and early user reports launch gate (`0010`) | **Implementable as product process** | Record local technical metrics (horizon stability, lag, confidence, safety disables) with bounded retention and an export/diagnostic view. Combine those results with opt-in reports in a release checklist. Decky cannot validate overlay compatibility or comfort automatically. |
| Curated compatibility expansion (`0006`) | **Required** | Start with verified games/modes. Test native/Vulkan, Proton/DX, borderless/fullscreen, gamescope scaling, suspend/resume, performance/battery impact, controller focus, and safety disable. Expand only from evidence. |

## Proposed architecture

1. **Decky frontend:** settings, enable/disable, shortcut configuration, one-time notice, diagnostics, sensor capability state, report consent/submission. Keep gameplay rendering separate until an actual above-game surface is proven.
2. **Decky Python backend:** sensor discovery/read loop, timestamping, orientation estimator, confidence/filter state machine, safety latch, metrics, settings, and RPC methods. Backend is authoritative for activation and disable reasons.
3. **Overlay prototype:** build the smallest transparent horizon surface first. Demonstrate (a) above-game visibility, (b) zero input capture, (c) correct resize/orientation, and (d) no unacceptable frame-time/battery impact across the compatibility matrix. This is a go/no-go gate, not an assumed Decky feature.
4. **Sensor adapter:** enumerate supported Linux/IIO/HID sources; map units and axes through a device-specific adapter; fail closed if both required streams are not present. Log device identity and sample health only in diagnostics.
5. **State transitions:** `Unavailable` → `Ready` → `Active` → `Degraded` → `Active`, with `SafetyDisabled` latched from `Active`/`Degraded`. Sensor loss always enters `SafetyDisabled`; noisy-but-present readings may enter `Degraded` and recover after sustained confidence.

## Primary sources

- Decky Loader source: https://github.com/SteamDeckHomebrew/decky-loader
- Decky plugin template (frontend/backend layout, bridge, distribution constraints): https://github.com/SteamDeckHomebrew/decky-plugin-template
- Decky frontend library: https://github.com/SteamDeckHomebrew/decky-frontend-lib
- Decky plugin-development wiki: https://wiki.deckbrew.xyz/en/user-guide/home#plugin-development
- Decky loader API type definitions: https://github.com/SteamDeckHomebrew/loader-api
- Linux IIO subsystem documentation (sensor interfaces): https://www.kernel.org/doc/html/latest/driver-api/iio/index.html
- Linux IIO userspace ABI: https://www.kernel.org/doc/html/latest/userspace-api/iio/index.html
- Linux HID Steam driver source (Deck controller/device integration reference): https://github.com/torvalds/linux/blob/master/drivers/hid/hid-steam.c

## Decision / next gate

Proceed with a Decky plugin panel and backend sensor prototype, but **do not claim that the ADR set is fully realizable by Decky yet**. The first implementation gate is an on-device overlay spike. If Decky cannot provide a compositor layer above the tested game surfaces and true input pass-through, either (1) add a separately supported SteamOS/gamescope component and document that dependency, or (2) revise ADR `0005`/`0004` before building the rest of the product around an unavailable surface.
