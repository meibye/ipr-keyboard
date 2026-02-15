# tests/

Pytest suite for `ipr-keyboard`.

## Test Inventory

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
- shared fixture module: `tests/conftest.py`

## Run

```bash
pytest
pytest --cov=ipr_keyboard --cov-report=term-missing
```

## Scope

- Unit tests for module behavior
- Integration tests for app loop and web flow
- Script-based E2E coverage is under `scripts/test_*.sh`
