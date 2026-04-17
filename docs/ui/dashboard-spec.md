# IPR Keyboard Web Dashboard Specification

## Purpose

The Raspberry Pi hosts a local web UI for monitoring and controlling the IPR keyboard / pen bridge device.

The web UI must allow a user to:

- understand the current state at a glance
- see whether Bluetooth is connected to the PC
- see whether the pen / scanner is attached and ready
- see whether a read or transmission is in progress
- review recent activity and logs
- change basic configuration
- safely reboot or shut down the device

The UI must be simple enough for a non-technical user standing near the device.

---

## Product goals

### Primary goals

- Provide an appliance-like dashboard rather than a technical admin interface.
- Make the status understandable mostly through images, icons, color, and short labels.
- Keep the implementation lightweight enough for Raspberry Pi Zero 2 W.
- Preserve the current Python-based backend approach where practical.
- Support desktop and mobile browsers on the local network.

### Secondary goals

- Make support and troubleshooting easier through translated event messages.
- Keep the design extensible for future screens and diagnostics.
- Allow an AI coding agent to implement and extend the UI from this specification.

### Non-goals

- No heavy server-side rendered web stack unless clearly justified.
- No cloud dependency at runtime.
- No complex user account or role system.
- No requirement for internet access.

---

## Target hardware and runtime constraints

### Hardware

- Raspberry Pi Zero 2 W
- Headless operation
- Limited CPU and memory
- Browser clients are on the same local network

### Constraints

- Low memory use
- Low CPU use
- Fast page load
- Small bundle sizes
- Minimal runtime dependencies
- SVG assets preferred over large raster image files

---

## Recommended architecture

### Existing baseline

The Flask server at `src/ipr_keyboard/web/server.py` is the starting point for the dashboard.
HTML templates live in `src/ipr_keyboard/web/templates/`.
SVG assets and other static files should go in `src/ipr_keyboard/web/static/`.

All implementation work should evolve this server rather than replacing it.

### Preferred solution

- Backend: Python with Flask (already in place)
- Frontend: vanilla HTML/CSS/JS served as static files — no build step
- Static serving: Flask development, nginx in production
- Realtime updates: Server-Sent Events preferred, lightweight polling as fallback

### Architecture principles

- Keep the backend authoritative for all device state.
- Keep the frontend mostly presentational and state-driven.
- Avoid introducing a full SSR runtime such as a persistent Next.js server.
- Prefer incremental evolution of the current web implementation.
- New dashboard API endpoints must use the `/api/` prefix as defined in the API contract.

### Why this approach

This project already has a Python-based device backend and a Flask server with templates. The best path is to keep Flask as the control layer and improve the UI incrementally, without introducing a large new runtime stack or a front-end build pipeline.

---

## Frontend strategy

### Recommended frontend style

- image-first
- icon-heavy
- touch-friendly
- responsive
- minimal text
- clear state colors
- large cards and action areas

### Visual language

The UI should rely on:

- large status cards
- SVG illustrations
- short state labels
- event icons
- simple color cues
- clear warning and danger zones

### User-facing wording

All visible text should be plain-language and non-technical.

Use:

- “Bluetooth connected”
- “Pen ready”
- “Transmission failed”
- “Restart device”

Avoid:

- “HID service resolved”
- “GATT reconnect in progress”
- “scanner state transition timeout”

Technical details belong behind an expandable details area.

---

## Main screens

### 1. Home

Purpose: the default view that answers “is the device ready?”

Must show:

- overall system state
- Bluetooth state
- pen/scanner state
- transmission state
- system health state
- last significant event
- quick link to activity and settings

Key behavior:

- state updates automatically
- top-level messages are short
- the screen is visually scannable from a distance

### 2. Connections

Purpose: show connection chain and readiness.

Must show:

- PC / Bluetooth connection state
- Raspberry Pi bridge state
- pen/scanner presence
- simple visual path from pen to Pi to PC
- pairing / reconnect / rescan actions where relevant

### 3. Activity

Purpose: show live or recent transfer activity.

Must show:

- current transfer state
- progress if transfer is active
- retry state
- last successful transfer
- recent transfer-related events

### 4. Events

Purpose: user-friendly troubleshooting.

Must show:

- translated event timeline
- filtering by subsystem
- severity markers
- optional access to raw logs

Translated events should be the default view.
Raw logs must be secondary.

### 5. Settings

Purpose: configuration and protected actions.

Must show:

- device information
- Bluetooth settings
- pen/scanner settings
- diagnostics settings
- reboot and shutdown actions

Dangerous actions must be visually separated and require confirmation.

---

## Design rules

### Rule 1: show state immediately

A user must be able to answer these questions within a few seconds:

- is the device ready?
- is Bluetooth connected?
- is the pen attached?
- is data currently being sent?
- is anything wrong?

### Rule 2: use image + label together

Do not rely only on color.
Do not rely only on text.

Each important state should use:

- icon or illustration
- text label
- color
- optional short explanation

### Rule 3: keep text short

Use one short label plus one short explanation.

Example:

- Label: `Connected`
- Explanation: `Paired with Office-PC`

### Rule 4: separate normal use and diagnostics

The main screens should stay simple.
Technical detail should be placed behind:

- “Show details”
- “Show raw logs”
- expandable error detail areas

### Rule 5: protect dangerous actions

Reboot and shutdown must require confirmation.
The UI must explain what happens after shutdown.

---

## Navigation

### Main navigation items

- Home
- Connections
- Activity
- Events
- Settings

### Navigation behavior

- Simple top nav on desktop
- Simple bottom nav or hamburger nav on smaller screens
- Current screen clearly highlighted

---

## Realtime behavior

### Required live-updating state

- Bluetooth state
- pen presence / readiness
- transmission state
- current operation
- latest event

### Update transport

Preferred order:

1. Server-Sent Events
2. WebSocket
3. lightweight polling if needed

The update mechanism must remain lightweight and robust on the Pi.

---

## Backend responsibilities

The backend owns:

- state collection
- event generation
- configuration persistence
- action execution
- translation from raw technical state to user-facing state

The frontend should not infer critical hardware state on its own.

---

## Event translation

Raw and technical device events must be converted to human-readable UI events.

Example mappings:

- `bt_connected=true` -> `Bluetooth connected`
- `bt_connected=false` -> `Bluetooth disconnected`
- `pen_present=true` -> `Pen attached`
- `tx_state=sending` -> `Transmission in progress`
- `tx_state=failed` -> `Transmission failed`

Where possible, include:

- time
- subsystem
- severity
- plain-language summary
- optional technical detail

---

## Configuration scope

The UI should support only a focused set of configuration options.

### Candidate settings

- device name shown in UI
- Bluetooth pairing mode enable/disable
- pairing timeout
- auto reconnect enable/disable
- pen/scanner auto detect enable/disable
- log verbosity
- diagnostics export

Avoid exposing low-level settings unless truly needed.

---

## Power actions

### Reboot

Must require confirmation.

### Shutdown

Must require confirmation and warn that manual power action may be needed to start again.

---

## Asset strategy

### Asset folder

Store all SVG assets in `src/ipr_keyboard/web/static/`.
Use predictable naming: `icon-bt-connected.svg`, `icon-pen-ready.svg`, `device-flow.svg`, etc.

### Preferred asset format

- SVG for illustrations and icons

### Needed asset categories

- pen / scanner illustration
- Raspberry Pi device illustration
- PC illustration
- transfer arrows / path illustration
- Bluetooth state icons
- warning / error / success badges

### Style

- simple
- flat
- readable at small and large sizes
- limited palette
- no unnecessary detail

---

## Accessibility and readability

The UI should remain understandable under:

- small screens
- older monitors
- quick glance usage
- imperfect lighting

Prefer:

- large targets
- readable contrast
- limited dense text
- visible state boundaries

---

## Testing expectations

The implementation should support:

- local manual browser testing
- API endpoint testing
- basic frontend smoke testing where practical
- visual verification of state changes

At minimum, the PR should document how the feature was tested.

---

## Documentation expectations

Any implementation PR should update:

- deployment instructions if new frontend assets or serving behavior are added
- configuration notes if new settings are introduced
- architecture notes if the serving model changes

---

## Future extensions

Possible later additions:

- diagnostics export page
- software update status
- onboarding / pairing wizard
- multi-device support
- richer mobile layout
- status LED explanation page matching physical LEDs