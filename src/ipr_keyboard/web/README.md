# src/ipr_keyboard/web/

Flask web layer for the IPR Pen Bridge dashboard and legacy status/config/log/pairing endpoints.

## Files

- `server.py`: app factory, root endpoint, and legacy HTML endpoints
- `api.py`: `/api/` Blueprint — dashboard JSON API (see docs/ui/api-contract.md)
- `pairing_routes.py`: legacy pairing wizard routes
- `templates/dashboard.html`: image-first SPA dashboard (primary UI)
- `templates/index.html`: legacy index page (kept for compatibility)
- `templates/status.html`: legacy status page
- `templates/config.html`: legacy configuration page
- `templates/logs.html`, `templates/logs_select.html`: legacy log viewers
- `templates/pairing.html`, `templates/pairing_wizard.html`: legacy pairing UI
- `static/`: SVG icons and device illustration assets

## Endpoints Registered by `create_app()`

### Dashboard API (`/api/` prefix)

- `GET /api/status` — full dashboard state (Home screen)
- `GET /api/status/bluetooth` — Bluetooth sub-state
- `GET /api/status/pen` — Pen / scanner sub-state
- `GET /api/status/transmission` — Transmission sub-state
- `GET /api/status/system` — System health sub-state
- `GET /api/events` — translated UI event list (filterable)
- `GET /api/events/latest` — most recent event
- `GET /api/logs/raw` — raw log lines for diagnostics
- `GET /api/config` — dashboard-scoped configuration
- `POST /api/config` — update configuration
- `POST /api/actions/pairing` — enable/disable Bluetooth pairing mode
- `POST /api/actions/rescan-pen` — request pen rescan
- `POST /api/actions/reconnect-bluetooth` — request Bluetooth reconnect
- `POST /api/actions/reboot` — reboot device (requires `{"confirm": true}`)
- `POST /api/actions/shutdown` — shut down device (requires `{"confirm": true}`)
- `GET /api/stream` — Server-Sent Events for live dashboard updates

### Legacy HTML endpoints

- `GET /` — dashboard SPA (dashboard.html)
- `GET /health` — JSON health check
- `GET /status` — HTML system status page
- `GET /config/`, `POST /config/` — HTML configuration page
- `GET /logs/` — HTML log viewer
- `GET /pairing/`, `POST /pairing/` — HTML pairing page

## Static Assets (`static/`)

SVG icons for dashboard state display:

- `icon-bt-connected.svg`, `icon-bt-waiting.svg` — Bluetooth state icons
- `icon-pen-ready.svg`, `icon-pen-missing.svg` — Pen state icons
- `icon-tx-idle.svg`, `icon-tx-active.svg` — Transmission state icons
- `icon-system-ok.svg`, `icon-system-warning.svg` — System health icons
- `device-flow.svg` — Pen → Pi → PC connection flow illustration

## Implementation Notes

- `/api/status` reads `bluetoothctl` and `systemctl` output and translates to user-facing state.
- Reboot and shutdown actions require an explicit `{"confirm": true}` JSON body.
- Events are stored in an in-memory circular buffer (max 200 events, reset on restart).
- The SSE `/api/stream` endpoint pushes new events and periodic heartbeat pings.
- Pairing routes and the power actions execute privileged shell/systemctl calls.
