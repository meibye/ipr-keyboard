# IPR Keyboard Web Dashboard User State Model

This document defines the UI-facing state model.

The backend is responsible for mapping raw technical state into the user-facing state values described here.

---

## State model principles

- UI states must be stable and limited in number.
- UI states must be understandable by non-technical users.
- Raw device or daemon details should not be exposed directly as top-level states.
- Every top-level state should map to:
  - a short label
  - a visual style
  - an icon or illustration state
  - an optional short explanation

---

## Global overall state

The UI should calculate an overall state from subsystem states.

### Allowed values

- `ready`
- `busy`
- `warning`
- `error`
- `offline`

### Intended meaning

#### `ready`
The device is ready for normal use.

#### `busy`
The device is currently performing an active operation such as reading or sending.

#### `warning`
The device is functioning but something needs attention or is degraded.

#### `error`
A user-relevant failure is present.

#### `offline`
The backend state is unavailable or the service is not reachable.

### Suggested display mapping

| State   | Label   | Tone    |
|---------|---------|---------|
| ready   | Ready   | success |
| busy    | Busy    | info    |
| warning | Warning | warning |
| error   | Error   | danger  |
| offline | Offline | muted   |

---

## Bluetooth state

### Allowed values

- `waiting`
- `pairing`
- `connected`
- `reconnecting`
- `error`

### Meaning

#### `waiting`
Bluetooth is not currently connected and the device is waiting.

#### `pairing`
The device is in pairing mode.

#### `connected`
Bluetooth is connected to a host.

#### `reconnecting`
Bluetooth was previously connected and is attempting to reconnect.

#### `error`
Bluetooth is in a user-relevant error state.

### Display mapping

| State        | Label        | Tone    | Suggested icon state |
|--------------|--------------|---------|----------------------|
| waiting      | Waiting      | muted   | bt-muted             |
| pairing      | Pairing      | info    | bt-search            |
| connected    | Connected    | success | bt-active            |
| reconnecting | Reconnecting | info    | bt-pulse             |
| error        | Error        | danger  | bt-warning           |

### Example explanations

- `Waiting for paired PC`
- `Ready to pair`
- `Paired with Office-PC`
- `Trying to reconnect`
- `Bluetooth needs attention`

---

## Pen / scanner state

### Allowed values

- `missing`
- `detecting`
- `ready`
- `reading`
- `error`

### Meaning

#### `missing`
No pen / scanner is detected.

#### `detecting`
The system is attempting to discover or validate the pen / scanner.

#### `ready`
The pen / scanner is detected and ready.

#### `reading`
A read is in progress.

#### `error`
The pen / scanner is in a failure state relevant to the user.

### Display mapping

| State     | Label        | Tone    | Suggested icon state |
|-----------|--------------|---------|----------------------|
| missing   | Not detected | muted   | pen-off              |
| detecting | Detecting    | info    | pen-search           |
| ready     | Ready        | success | pen-ready            |
| reading   | Reading      | info    | pen-active           |
| error     | Error        | danger  | pen-warning          |

### Example explanations

- `Attach the pen / scanner`
- `Searching for device`
- `Scanner found`
- `Reading in progress`
- `Pen needs attention`

---

## Transmission state

### Allowed values

- `idle`
- `preparing`
- `sending`
- `retrying`
- `success`
- `failed`

### Meaning

#### `idle`
No active transmission is happening.

#### `preparing`
The system is preparing data for transmission.

#### `sending`
A transmission is in progress. Set by `BluetoothKeyboard.send_text()` (automatic USB-pen flow) or by the debug send-text / send-file endpoints (manual send).

#### `retrying`
A transmission retry is underway.

#### `success`
The most recent transmission completed successfully.

#### `failed`
The current or most recent transmission failed.

### Display mapping

| State     | Label     | Tone    | Suggested icon state |
|-----------|-----------|---------|----------------------|
| idle      | Idle      | muted   | tx-idle              |
| preparing | Preparing | info    | tx-prep              |
| sending   | Sending   | info    | tx-active            |
| retrying  | Retrying  | warning | tx-retry             |
| success   | Sent      | success | tx-ok                |
| failed    | Failed    | danger  | tx-fail              |

### Example explanations

- `No active send`
- `Preparing data`
- `Sending to PC`
- `Retry in progress`
- `Last send successful`
- `Last send failed`

---

## System state

### Allowed values

- `healthy`
- `busy`
- `warning`
- `error`
- `rebooting`
- `shutting_down`

### Meaning

#### `healthy`
The system is operating normally.

#### `busy`
The system is active but not in a problem state.

#### `warning`
The system is running with a non-fatal issue.

#### `error`
The system has a user-relevant failure.

#### `rebooting`
A reboot has been initiated.

#### `shutting_down`
A shutdown has been initiated.

### Display mapping

| State         | Label         | Tone    | Suggested icon state |
|---------------|---------------|---------|----------------------|
| healthy       | Healthy       | success | sys-ok               |
| busy          | Working       | info    | sys-busy             |
| warning       | Warning       | warning | sys-warn             |
| error         | Error         | danger  | sys-fail             |
| rebooting     | Rebooting     | warning | sys-reboot           |
| shutting_down | Shutting down | danger  | sys-power            |

---

## Event severity

### Allowed values

- `info`
- `warning`
- `error`

### Display mapping

| Severity | Icon | Intended use |
|----------|------|--------------|
| info     | ✓ or i | normal notable event |
| warning  | !    | degraded or retry state |
| error    | ×    | failure or urgent attention |

---

## Event categories

### Allowed values

- `bluetooth`
- `pen`
- `transmission`
- `system`
- `config`

These values are used for filtering on the Events page.

---

## Event model

### Event fields

Each UI event should support:

- `id`
- `timestamp`
- `category`
- `severity`
- `summary`
- `details`
- `raw_reference` optional

### Example

```json
{
  "id": "evt_001",
  "timestamp": "2026-04-17T14:22:09Z",
  "category": "transmission",
  "severity": "warning",
  "summary": "Transmission retry",
  "details": "The device is retrying the send to the PC."
}
```

---

## UI card model

Each status card should support:

- title
- state
- label
- explanation
- icon
- last_updated
- actions

### Example
```json
{
  "title": "Bluetooth",
  "state": "connected",
  "label": "Connected",
  "explanation": "Paired with Office-PC",
  "icon": "bt-active",
  "last_updated": "2026-04-17T14:22:09Z",
  "actions": []
}
```
---

## Raw-to-UI mapping guidance


The backend should translate technical device state into stable UI state.

### Examples

```
| Raw input                  | UI output                  |
|----------------------------|----------------------------|
| bt_connected=true          | Bluetooth = connected      |
| bt_pairing=true            | Bluetooth = pairing        |
| pen_present=false          | Pen = missing              |
| scan_in_progress=true      | Pen = reading              |
| tx_state=idle              | Transmission = idle        |
| tx_state=sending           | Transmission = sending     |
| tx_retry_count>0 and active| Transmission = retrying    |
| system_action=rebooting    | System = rebooting         |
```

### Mapping priority

If several raw signals conflict, prefer the more user-relevant state.

Example:

- if Bluetooth is connected but transmission is retrying, 
the transmission card should show retrying 
while Bluetooth still shows connected.

### Overall state calculation guidance

Suggested priority:

1. if backend unreachable -> offline
2. if any subsystem is error or failed -> error
3. if any subsystem is warning or retrying -> warning
4. if any subsystem is actively working -> busy
5. otherwise -> ready

### Empty and unknown states

If the backend cannot determine a specific subsystem state, use an explicit fallback rather than leaving the UI blank.

Suggested fallback labels:

- Unknown
- Status unavailable

Avoid showing empty cards.

### Confirmation-required actions

The following user actions must require confirmation:

- reboot
- shutdown
- reset pairing or disconnect host if such actions are added later

## UX note

The state model should remain compact.
Do not expose new UI states unless they are clearly distinct and useful to the end user.