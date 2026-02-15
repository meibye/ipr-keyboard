# Testing Plan

Testing plan aligned to current code and script layout.

## 1. Unit and Integration (pytest)

Run all tests:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=ipr_keyboard --cov-report=term-missing
```

Current test layout:
- `tests/bluetooth/test_keyboard.py`
- `tests/config/test_manager.py`
- `tests/logging/test_logger.py`
- `tests/usb/test_detector.py`
- `tests/usb/test_usb_reader.py`
- `tests/usb/test_deleter.py`
- `tests/usb/test_mtp_sync.py`
- `tests/utils/test_helpers.py`
- `tests/web/test_server.py`
- `tests/web/test_config_api.py`
- `tests/web/test_logs_api.py`
- `tests/integration/test_usb_flow.py`
- `tests/integration/test_web_integration.py`
- `tests/integration/test_main.py`

## 2. Script-Level Validation

- Smoke: `./scripts/test_smoke.sh`
- Foreground E2E: `./scripts/test_e2e_demo.sh`
- Systemd E2E: `sudo ./scripts/test_e2e_systemd.sh`

## 3. Bluetooth Validation

- Pairing diagnostics: `sudo ./scripts/ble/diag_pairing.sh`
- Visibility diagnostics: `sudo ./scripts/ble/diag_bt_visibility.sh`
- Pairing interactive test: `sudo ./scripts/ble/test_pairing.sh ble`

## 4. Acceptance Criteria

- `pytest` passes
- `ipr_keyboard.service` healthy
- `bt_hid_ble.service` and `bt_hid_agent_unified.service` healthy
- `/health` endpoint returns `{ "status": "ok" }`
- End-to-end text path works via `bt_kb_send`
