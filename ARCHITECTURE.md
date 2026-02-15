# ARCHITECTURE

Current-state architecture baseline for `ipr-keyboard` (audited 2026-02-15).

## 1. System Intent

Bridge IrisPen-produced text files to host keystrokes using a Raspberry Pi BLE HID stack.

## 2. Runtime Topology

```text
IrisPen folder (config.json -> IrisPenFolder)
    -> src/ipr_keyboard/usb/detector.py
    -> src/ipr_keyboard/usb/reader.py
    -> src/ipr_keyboard/bluetooth/keyboard.py
    -> /usr/local/bin/bt_kb_send
    -> /run/ipr_bt_keyboard_fifo
    -> bt_hid_ble.service (bt_hid_ble_daemon.py)
    -> host receives HID input
```

In parallel, `src/ipr_keyboard/web/server.py` serves Flask APIs and status endpoints.

## 3. Source Module Map

### Core (Current)

- `src/ipr_keyboard/main.py`
- `src/ipr_keyboard/config/manager.py`
- `src/ipr_keyboard/config/web.py`
- `src/ipr_keyboard/logging/logger.py`
- `src/ipr_keyboard/logging/web.py`
- `src/ipr_keyboard/usb/*`
- `src/ipr_keyboard/bluetooth/keyboard.py`
- `src/ipr_keyboard/web/server.py`

### Support (Current)

- `scripts/service/bin/bt_hid_ble_daemon.py`
- `scripts/service/bin/bt_hid_agent_unified.py`
- `scripts/service/svc/*.service`
- `scripts/ble/bt_kb_send.sh`

## 4. Service Architecture

### Current Services

- `ipr_keyboard.service`
- `bt_hid_agent_unified.service`
- `bt_hid_ble.service`
- `ipr-provision.service`

### Not Shipped as Current Units

- `bt_hid_uinput.service`
- `ipr_backend_manager.service`
- `bt_hid_daemon.service`

If these are referenced in scripts/docs, treat as legacy compatibility paths until explicitly reintroduced.

## 5. Configuration Boundaries

### App Config (`config.json`)

Defined by `AppConfig` in `src/ipr_keyboard/config/manager.py`:
- `IrisPenFolder`
- `DeleteFiles`
- `Logging`
- `MaxFileSize`
- `LogPort`

### System Config

- `/opt/ipr_common.env` for service/env behavior
- `/etc/default/bt_hid_agent_unified` managed by `scripts/lib/bt_agent_unified_env.sh`

## 6. Legacy and Deprecated Patterns

### Legacy Patterns (still present, not canonical)

1. `uinput` backend assumptions in diagnostics/tests (`bt_hid_uinput.service` branches).
2. References to `KeyboardBackend` synchronization between app config and `/etc/ipr-keyboard/backend`.
3. `/pairing/activate-ble` route calling `ipr_backend_manager.service` in `src/ipr_keyboard/web/pairing_routes.py`.
4. Duplicated disable script: `scripts/service/svc_disable_all_services.sh`.
5. Prompt file mirroring under `scripts/docs/copilot/*`.

### Deprecated Patterns

1. Treating backend manager service (`ipr_backend_manager.service`) as a guaranteed platform primitive in this repo state.
2. Treating `ble_install_helper.sh` as service installer; it installs helper dependencies + `bt_kb_send`, while service installation is handled by `scripts/service/svc_install_bt_gatt_hid.sh`.

## 7. Architectural Alignment Skill

Required policy text for agent instructions:

"When asked to 'clean' the repo, compare every module against ARCHITECTURE.md. If a module implements a pattern marked as 'Deprecated' or 'Legacy' in the architecture doc, even if it is still being called, flag it as Architectural Dead Code and propose a refactor or removal."

## 8. Decision Rule for Cleanup Work

Before extending any module:
1. Check if the module aligns to a `Current` pattern in this file.
2. If it aligns to `Legacy` or `Deprecated`, stop and propose migration/removal first.
