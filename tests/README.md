# Tests
## Remote Device Access via SSH MCP Server

For all test execution, diagnostics, and command management on Raspberry Pi or Windows PC, use the SSH MCP server as defined in `.vscode/mcp.json`.

**Example:**
- To run tests remotely:
  - Use the `ipr-rpi-dev-ssh` or `ipr-pc-dev-ssh` profile.
  - Execute via MCP server (see Copilot agent or VS Code integration).

**Typical usage:**
```json
{
  "cmdString": "pytest"
}
```
See `.vscode/mcp.json` for server details and allowed commands.

**Do not use direct SSH or SCP.** All remote actions should be performed via the MCP server for consistency and auditability.

---


This directory contains the comprehensive test suite for the ipr-keyboard project using pytest. The tests mirror the source structure and follow project conventions for isolation, fixtures, and coverage. End-to-end and systemd tests are provided in the scripts directory.


## Test Coverage

Current test coverage: **94%** (137 tests)


## Testing Levels

The testing strategy follows three levels:

| Level | Description | Tools | Coverage |
|-------|-------------|-------|----------|
| **Unit Tests** | Test individual functions/classes in isolation | pytest, mocks | `tests/` directory |
| **Component Tests** | Test modules with mocked external dependencies | pytest, fixtures | `tests/integration/` |
| **End-to-End Tests** | Test full system on real hardware | Shell scripts | `scripts/test_*.sh` |


## Test Structure

Tests are organized to mirror the source code structure and use pytest conventions:

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── bluetooth/
│   └── test_keyboard.py     # Bluetooth keyboard unit tests (14 tests)
├── config/
│   └── test_manager.py      # Configuration manager unit tests (14 tests)
├── logging/
│   └── test_logger.py       # Logger unit tests (6 tests)
├── usb/
│   ├── test_detector.py     # File detection tests (11 tests)
│   ├── test_usb_reader.py   # File reading tests (11 tests)
│   ├── test_deleter.py      # File deletion tests (13 tests)
│   └── test_mtp_sync.py     # MTP sync tests (11 tests)
├── utils/
│   └── test_helpers.py      # Helper utilities tests (9 tests)
├── web/
│   ├── test_server.py       # Flask app tests (6 tests)
│   ├── test_config_api.py   # Config API tests (8 tests)
│   └── test_logs_api.py     # Logs API tests (8 tests)
└── integration/
    ├── test_usb_flow.py     # USB integration tests (7 tests)
    ├── test_web_integration.py  # Web API integration tests (6 tests)
    └── test_main.py         # Main module integration tests (5 tests)
```


## Running Tests

### Run all tests

```bash
pytest
```

### Run tests with coverage

```bash
pytest --cov=ipr_keyboard
pytest --cov=ipr_keyboard --cov-report=term-missing  # Show missing lines
pytest --cov=ipr_keyboard --cov-report=html          # Generate HTML report
```

### Run specific test module

```bash
pytest tests/config/
pytest tests/bluetooth/test_keyboard.py
pytest tests/usb/ -v  # Verbose output
```


## Test Categories

### Unit Tests

#### Bluetooth Tests (`bluetooth/`)
- `test_keyboard.py` - Tests for BluetoothKeyboard class:
  - send_text success/failure scenarios
  - is_available helper detection
  - Error handling (FileNotFoundError, CalledProcessError)
  - Unicode and multiline text handling

#### Configuration Tests (`config/`)
- `test_manager.py` - Tests for AppConfig and ConfigManager:
  - Default values and validation
  - JSON serialization/deserialization
  - Singleton pattern and thread safety
  - Config persistence and reload
  - Keyboard backend normalization

#### Logging Tests (`logging/`)
- `test_logger.py` - Tests for logger:
  - Logger creation and singleton pattern
  - File and console handlers
  - Log file rotation
  - Directory creation

#### USB Tests (`usb/`)
- `test_detector.py` - File detection and monitoring
- `test_usb_reader.py` - File reading with size limits
- `test_deleter.py` - File and folder deletion
- `test_mtp_sync.py` - MTP sync tests

#### Utility Tests (`utils/`)
- `test_helpers.py` - Path resolution and JSON operations

#### Web Tests (`web/`)
- `test_server.py` - Flask app factory and health check
- `test_config_api.py` - Configuration REST API
- `test_logs_api.py` - Log viewing API


### Integration Tests

- **USB Flow (`integration/test_usb_flow.py`)**: Complete file detection → read → delete workflow, multiple file processing, UTF-8 content handling
- **Web Integration (`integration/test_web_integration.py`)**: Config round-trip operations, log entries after operations, error handling
- **Main Module (`integration/test_main.py`)**: Application startup, USB/BT loop with mocks, Bluetooth unavailable handling
- **Backend Service Integration**: E2E/systemd tests in `scripts/` may require enabling/disabling backend services (`bt_hid_uinput.service`, `bt_hid_ble.service`) via systemctl or scripts. See `scripts/ble/ble_switch_backend.sh` and `scripts/ble/ble_install_helper.sh` for backend management.


## Fixtures (conftest.py)

Common fixtures for all tests:

- `temp_config` - Temporary config file with ConfigManager reset
- `temp_log_dir` - Temporary log directory with logger reset
- `mock_bt_helper` - Mock for Bluetooth subprocess calls
- `flask_client` - Flask test client with temp config
- `usb_folder` - Temporary USB folder
- `sample_text_files` - Pre-created test files
- `reset_config_manager` - Singleton reset fixture

## External Interface Testing

### Bluetooth (mocked in tests)
- Tests mock `subprocess.run` to simulate helper behavior
- For actual Bluetooth testing: `./scripts/test_bluetooth.sh`

### USB (temporary directories)
- Tests use `tmp_path` fixture for isolation
- For actual USB testing: `./scripts/usb_setup_mount.sh`

### Web API (Flask test client)
- Tests use Flask's built-in test client
- For manual API testing:
  ```bash
  ./scripts/dev_run_app.sh
  curl http://localhost:8080/health
  curl http://localhost:8080/config/
  ```


## End-to-End Testing (Scripts)

For full system and systemd testing on a Raspberry Pi, use the provided scripts:

```bash
# Smoke test (component checks)
./scripts/test_smoke.sh

# Full E2E demo (foreground mode)
./scripts/test_e2e_demo.sh

# Systemd service E2E test
sudo ./scripts/test_e2e_systemd.sh

# Manual Bluetooth keyboard test
./scripts/test_bluetooth.sh "Test string æøå"
```


## Writing Tests

Tests follow pytest conventions:
- Test files are named `test_*.py`
- Test functions are named `test_*`
- Use fixtures for common setup/teardown
- Keep tests isolated and independent
- Use `monkeypatch` for mocking

### Example Test

```python
def test_example(temp_config, usb_folder):
    """Test description.
    
    Verifies that...
    """
    # Arrange
    test_file = usb_folder / "test.txt"
    test_file.write_text("content")
    
    # Act
    result = some_function(test_file)
    
    # Assert
    assert result == expected
```


## Dependencies

Test dependencies are defined in `pyproject.toml` under `[project.optional-dependencies]`:
- pytest
- pytest-cov (for coverage reports)

Install with:
```bash
pip install -e ".[dev]"
```


## See Also

- [TESTING_PLAN.md](../TESTING_PLAN.md) - Detailed testing strategy
- [scripts/README.md](../scripts/README.md) - Script documentation
