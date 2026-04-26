# IPR Keyboard Web Dashboard API Contract

This document defines the backend API expected by the web dashboard.

The contract is intentionally small and stable.
The backend may have additional internal endpoints, but the frontend should depend only on the documented contract.

---

## General principles

- JSON for request and response bodies unless otherwise stated
- clear, stable, UI-oriented payloads
- backend translates technical state into user-facing state
- dangerous actions require explicit POST requests
- no frontend direct shell execution
- all timestamps should be ISO 8601

## Existing server baseline

The Flask server at `src/ipr_keyboard/web/server.py` currently serves non-prefixed routes
(`/`, `/health`, `/status`, `/logs/`, `/pairing/`, `/config/`).

New dashboard endpoints defined in this contract use the `/api/` prefix.
Existing routes should remain functional during migration.
When the dashboard implementation PR lands, the old routes can be deprecated incrementally.

---

## Base path

```text
/api
```

## Authentication

Current expected deployment is on a trusted local network.
No authentication is required by this initial contract.

If authentication is added later, it should be added in a backward-compatible and lightweight way.

## Common response conventions
### Success response

Use standard HTTP success status codes and a JSON body where relevant.

### Error response shape
```json
{
  "error": {
    "code": "invalid_request",
    "message": "The provided value is not valid."
  }
}
```

### Standard fields

Where relevant, responses may include:

timestamp
version
source

### Status endpoints
#### GET /api/status

Returns the complete dashboard state required for the Home screen.

Example response
```json
{
  "timestamp": "2026-04-17T14:22:09Z",
  "overall": {
    "state": "ready",
    "label": "Ready",
    "explanation": "Ready for use"
  },
  "bluetooth": {
    "state": "connected",
    "label": "Connected",
    "explanation": "Paired with Office-PC"
  },
  "pen": {
    "state": "ready",
    "label": "Ready",
    "explanation": "Scanner found"
  },
  "transmission": {
    "state": "idle",
    "label": "Idle",
    "explanation": "No active send"
  },
  "system": {
    "state": "healthy",
    "label": "Healthy",
    "explanation": "No current warnings"
  },
  "last_event": {
    "id": "evt_001",
    "timestamp": "2026-04-17T14:20:44Z",
    "category": "pen",
    "severity": "info",
    "summary": "Pen connected"
  }
}
```

#### GET /api/status/bluetooth

Returns Bluetooth state only.

Example response
```json
{
  "timestamp": "2026-04-17T14:22:09Z",
  "state": "connected",
  "label": "Connected",
  "explanation": "Paired with Office-PC",
  "host_name": "Office-PC"
}
```

#### GET /api/status/pen

Returns pen / scanner state only.

Example response
```json
{
  "timestamp": "2026-04-17T14:22:09Z",
  "state": "ready",
  "label": "Ready",
  "explanation": "Scanner found",
  "device_name": "IR Pen Scanner"
}
```

#### GET /api/status/transmission

Returns transmission state and current transfer metadata.
The state reflects live activity: it is updated by `BluetoothKeyboard.send_text()` (auto USB flow) and by the debug send-text / send-file endpoints (manual send).

Example response

```json
{
  "timestamp": "2026-04-17T14:22:09Z",
  "state": "sending",
  "label": "Sending",
  "explanation": "Sending to PC",
  "progress_percent": 68,
  "items_sent": 14,
  "retry_count": 1,
  "last_success_at": "2026-04-17T14:21:08Z"
}
```

#### GET /api/status/system

Returns overall system health data.

Example response

```json
{
  "timestamp": "2026-04-17T14:22:09Z",
  "state": "healthy",
  "label": "Healthy",
  "explanation": "No current warnings"
}
```

### Event endpoints
#### GET /api/events

Returns translated UI events.

#### Query parameters
- limit optional
- category optional
- severity optional
- since optional ISO 8601 timestamp

Example request
```json
GET /api/events?limit=50&category=bluetooth
```

Example response
```json
{
  "items": [
    {
      "id": "evt_1001",
      "timestamp": "2026-04-17T14:21:00Z",
      "category": "bluetooth",
      "severity": "info",
      "summary": "Bluetooth connected",
      "details": "The device is connected to Office-PC."
    },
    {
      "id": "evt_1002",
      "timestamp": "2026-04-17T14:22:10Z",
      "category": "bluetooth",
      "severity": "warning",
      "summary": "Bluetooth reconnecting",
      "details": "The device is trying to reconnect to the previous host."
    }
  ]
}
```

#### GET /api/events/latest

Returns the most recent translated event.

Example response
```json
{
  "id": "evt_1003",
  "timestamp": "2026-04-17T14:23:01Z",
  "category": "transmission",
  "severity": "info",
  "summary": "Transmission completed",
  "details": "The transfer to the PC completed successfully."
}
```

### Log endpoints
#### GET /api/logs/raw

Returns raw log lines for diagnostics.

This endpoint is for advanced use and should not be the default UI source for the Events page.

#### Query parameters
- limit optional
- since optional
- contains optional
- category optional if mapping exists

Example response
```json
{
  "items": [
    {
      "timestamp": "2026-04-17T14:22:09Z",
      "line": "bt_hid_ble_daemon: transmission retry scheduled"
    }
  ]
}
```

### Configuration endpoints
#### GET /api/config

Returns editable dashboard-related configuration.

Example response
```json
{
  "device_name": "IPR Pen Bridge",
  "ui_title": "IPR Pen Bridge",
  "bluetooth": {
    "auto_reconnect": true,
    "pairing_timeout_seconds": 120
  },
  "pen": {
    "auto_detect": true,
    "read_timeout_seconds": 10
  },
  "diagnostics": {
    "log_level": "INFO"
  }
}
```

POST /api/config

Updates editable configuration.

Example request
```json
{
  "ui_title": "IPR Pen Bridge",
  "bluetooth": {
    "auto_reconnect": true,
    "pairing_timeout_seconds": 120
  }
}
```

Example response
```json
{
  "ok": true,
  "message": "Configuration updated."
}
```

### Action endpoints
#### POST /api/actions/pairing

Requests Bluetooth pairing mode.

Example request
```json
{
  "enabled": true,
  "timeout_seconds": 120
}
```

Example response
```json
{
  "ok": true,
  "message": "Pairing mode enabled."
}
```

#### POST /api/actions/rescan-pen

Requests a pen / scanner rescan.

Example response
```json
{
  "ok": true,
  "message": "Pen rescan started."
}
```

#### POST /api/actions/reconnect-bluetooth

Requests a Bluetooth reconnect.

Example response
```json
{
  "ok": true,
  "message": "Bluetooth reconnect started."
}
```

#### POST /api/actions/reboot

Requests system reboot.

This endpoint must only perform the action after frontend confirmation.

Example request
```json
{
  "confirm": true
}
```

Example response
```json
{
  "ok": true,
  "message": "Reboot initiated."
}
```

#### POST /api/actions/shutdown

Requests system shutdown.

This endpoint must only perform the action after frontend confirmation.

Example request
```json
{
  "confirm": true
}
```

Example response
```json
{
  "ok": true,
  "message": "Shutdown initiated."
}
```

### Debug endpoints

All debug endpoints require an authenticated session. They are intended for diagnostics and manual control, not for normal dashboard operation.

#### GET /api/debug/services

Returns the status of each managed system service.

Managed services (in order):

| Technical name | Descriptive label |
|---|---|
| `systemd-udevd` | Device Manager |
| `dbus` | Message Bus |
| `bluetooth` | Bluetooth Core |
| `bt_hid_agent_unified` | Pen Detector |
| `bt_hid_ble` | BLE Keyboard |
| `ipr_keyboard` | Keyboard Service |

Example response
```json
{
  "services": [
    {
      "name": "bt_hid_ble",
      "label": "BLE Keyboard",
      "description": "BLE HID keyboard daemon (writes to FIFO)",
      "active": true,
      "enabled": true
    }
  ]
}
```

#### POST /api/debug/services/\<name\>/\<action\>

Performs a service management action.

- `name` must be one of the managed service names listed above.
- `action` must be one of: `start`, `stop`, `restart`.
- Unknown service name or action returns 400.

Example response
```json
{ "ok": true, "message": "Service bt_hid_ble restart succeeded." }
```

On failure
```json
{ "ok": false, "message": "Unit bt_hid_ble.service not found." }
```

#### POST /api/debug/send-text

Sends a text string to the PC via the BLE keyboard FIFO.
Updates the shared transmission state (`/api/status/transmission`) during the send.

Request body
```json
{ "text": "hello world", "nowait": false }
```

- `text`: required, non-empty string
- `nowait`: optional boolean, skips FIFO wait (default false)

Example response
```json
{ "ok": true, "message": "Text sent." }
```

#### POST /api/debug/send-file

Sends a file to the PC via the BLE keyboard FIFO.
Accepts `multipart/form-data` with a `file` field.
Updates the shared transmission state during the send.

Example response
```json
{ "ok": true, "message": "File sent." }
```

#### GET /api/debug/pen-files

Lists files in the configured pen folder (`IrisPenFolder` in config).
Returns up to 8 KB of content per file; larger files are truncated (indicated by `truncated: true`).

Example response
```json
{
  "folder": "/mnt/irispen",
  "files": [
    {
      "name": "note.txt",
      "path": "/mnt/irispen/note.txt",
      "size_bytes": 142,
      "modified_at": "2026-04-26T14:00:00Z",
      "content": "Hello world\n",
      "truncated": false
    }
  ]
}
```

### Realtime endpoint
#### GET /api/stream

Server-Sent Events endpoint for live dashboard updates.

Preferred event types:

- status_update
- event_added
- config_updated
- system_action

Example SSE event payload
```json
{
  "type": "status_update",
  "data": {
    "bluetooth": {
      "state": "connected",
      "label": "Connected",
      "explanation": "Paired with Office-PC"
    }
  }
}
```

Another example
```json
{
  "type": "event_added",
  "data": {
    "id": "evt_2001",
    "timestamp": "2026-04-17T14:23:10Z",
    "category": "transmission",
    "severity": "warning",
    "summary": "Transmission retry",
    "details": "The device is retrying the transfer."
  }
}
```

---

## Frontend expectations

The frontend should assume:

- /api/status is the primary source for Home screen state
- /api/events drives the Events page
- /api/stream pushes live changes
- /api/logs/raw is only for advanced detail views
- all visible labels from the backend are already translated into plain-language

## Backward compatibility

If the backend evolves, prefer:

- additive changes
- preserving current field names
- avoiding breaking changes without updating this document

## Implementation guidance

The backend may internally gather state from:

- Bluetooth service state
- device presence checks
- transfer pipeline state
- system service status
- application logs

However, those internal details should remain behind this UI-oriented contract.
