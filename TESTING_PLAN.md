# IPR-Keyboard Testing Plan

This document provides a detailed stepwise plan for testing each component of the ipr-keyboard project, including unit tests and component tests for external interfaces.

## Overview

The ipr-keyboard project bridges an IrisPen USB scanner to a paired device via Bluetooth HID keyboard emulation. Testing is organized into three layers:

1. **Unit Tests**: Test individual functions and classes in isolation
2. **Component Tests**: Test modules working together with mocked external dependencies
3. **Integration/E2E Tests**: Test the full system (available via scripts)

## Test Structure

Tests are organized to mirror the source code structure:

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── bluetooth/
│   └── test_keyboard.py     # Bluetooth keyboard unit tests
├── config/
│   └── test_manager.py      # Configuration manager unit tests
├── logging/
│   └── test_logger.py       # Logger unit tests
├── usb/
│   ├── test_detector.py     # File detection unit tests
│   ├── test_reader.py       # File reading unit tests
│   ├── test_deleter.py      # File deletion unit tests
│   └── test_mtp_sync.py     # MTP sync unit tests
├── web/
│   ├── test_server.py       # Flask app factory tests
│   ├── test_config_api.py   # Config API endpoint tests
│   └── test_logs_api.py     # Logs API endpoint tests
├── utils/
│   └── test_helpers.py      # Helper utilities tests
└── integration/
    ├── test_usb_flow.py     # USB file handling integration
    ├── test_web_integration.py  # Web API integration
    └── test_main.py         # Main module integration
```

---

## Unit Tests

### 1. Bluetooth Module (`src/ipr_keyboard/bluetooth/`)

#### Test File: `tests/bluetooth/test_keyboard.py`

**BluetoothKeyboard Class Tests:**

| Test Case | Description | Coverage Target |
|-----------|-------------|-----------------|
| `test_send_text_success` | Send text successfully via helper script | Basic functionality |
| `test_send_text_empty` | Handle empty text input (should skip) | Edge case |
| `test_send_text_helper_not_found` | Handle FileNotFoundError from helper | Error handling |
| `test_send_text_helper_error` | Handle CalledProcessError from helper | Error handling |
| `test_is_available_true` | Check helper availability when present | Helper detection |
| `test_is_available_false` | Check helper unavailability | Helper detection |

**External Interface Considerations:**
- The Bluetooth helper script (`/usr/local/bin/bt_kb_send`) is a system dependency
- Tests should mock `subprocess.run` to avoid requiring the actual helper
- Use `scripts/test_bluetooth.sh` for manual/interactive Bluetooth testing

---

### 2. Configuration Module (`src/ipr_keyboard/config/`)

#### Test File: `tests/config/test_manager.py`

**AppConfig Class Tests:**

| Test Case | Description | Coverage Target |
|-----------|-------------|-----------------|
| `test_appconfig_defaults` | Verify default configuration values | Default values |
| `test_appconfig_from_dict` | Create config from dictionary | Deserialization |
| `test_appconfig_from_dict_partial` | Handle partial config dict | Edge case |
| `test_appconfig_to_dict` | Convert config to dictionary | Serialization |
| `test_appconfig_keyboard_backend_normalization` | Normalize invalid backend values | Validation |

**ConfigManager Class Tests:**

| Test Case | Description | Coverage Target |
|-----------|-------------|-----------------|
| `test_config_load_and_update` | Load and update configuration | Basic functionality |
| `test_config_singleton` | Verify singleton pattern | Design pattern |
| `test_config_thread_safety` | Test concurrent access | Thread safety |
| `test_config_reload` | Reload config from disk | File sync |
| `test_config_missing_file` | Handle missing config file | Error handling |
| `test_config_persistence` | Verify changes persist to disk | Persistence |

---

### 3. USB Module (`src/ipr_keyboard/usb/`)

#### Test File: `tests/usb/test_detector.py`

| Test Case | Description | Coverage Target |
|-----------|-------------|-----------------|
| `test_list_files` | List files sorted by mtime | Basic functionality |
| `test_list_files_empty_folder` | Handle empty folder | Edge case |
| `test_list_files_nonexistent_folder` | Handle missing folder | Error handling |
| `test_newest_file` | Get newest file by mtime | Basic functionality |
| `test_newest_file_empty` | Handle no files | Edge case |
| `test_wait_for_new_file` | Poll for new file (with timeout) | Async polling |

#### Test File: `tests/usb/test_reader.py`

| Test Case | Description | Coverage Target |
|-----------|-------------|-----------------|
| `test_read_file` | Read file contents | Basic functionality |
| `test_read_file_nonexistent` | Handle missing file | Error handling |
| `test_read_file_not_file` | Handle directory path | Error handling |
| `test_read_file_too_large` | Handle oversized files | Size limit |
| `test_read_newest` | Read newest file in folder | Combined functionality |
| `test_read_file_encoding` | Handle UTF-8 with errors | Character encoding |

#### Test File: `tests/usb/test_deleter.py`

| Test Case | Description | Coverage Target |
|-----------|-------------|-----------------|
| `test_delete_file` | Delete single file | Basic functionality |
| `test_delete_file_nonexistent` | Delete missing file (no error) | Edge case |
| `test_delete_file_error` | Handle permission errors | Error handling |
| `test_delete_all` | Delete all files in folder | Batch operation |
| `test_delete_all_empty` | Handle empty folder | Edge case |
| `test_delete_newest` | Delete newest file | Combined functionality |

#### Test File: `tests/usb/test_mtp_sync.py`

| Test Case | Description | Coverage Target |
|-----------|-------------|-----------------|
| `test_sync_mtp_to_cache` | Sync files to cache | Basic functionality |
| `test_sync_skip_unchanged` | Skip unchanged files | Optimization |
| `test_sync_delete_source` | Delete source after sync | Cleanup option |
| `test_sync_nested_directories` | Handle subdirectories | Structure handling |
| `test_iter_text_files` | Filter .txt files only | File filtering |

**External Interface Considerations:**
- USB/MTP mounts are system dependencies
- Use temporary directories for testing
- Use `scripts/usb_setup_mount.sh` for actual mount setup

---

### 4. Logging Module (`src/ipr_keyboard/logging/`)

#### Test File: `tests/logging/test_logger.py`

| Test Case | Description | Coverage Target |
|-----------|-------------|-----------------|
| `test_get_logger` | Create logger instance | Basic functionality |
| `test_logger_singleton` | Verify logger is reused | Singleton pattern |
| `test_logger_writes_to_file` | Log messages written to file | File output |
| `test_log_path` | Get log file path | Path resolution |
| `test_logger_rotation` | File rotation on size limit | Log rotation |
| `test_logger_console_output` | Console handler active | Console output |

---

### 5. Web Module (`src/ipr_keyboard/web/`)

#### Test File: `tests/web/test_server.py`

| Test Case | Description | Coverage Target |
|-----------|-------------|-----------------|
| `test_create_app` | Create Flask application | Factory pattern |
| `test_health_endpoint` | /health returns ok | Health check |
| `test_blueprints_registered` | Config and logs blueprints | Blueprint setup |

#### Test File: `tests/web/test_config_api.py`

| Test Case | Description | Coverage Target |
|-----------|-------------|-----------------|
| `test_get_config` | GET /config/ returns config | Read operation |
| `test_update_config` | POST /config/ updates values | Write operation |
| `test_update_config_partial` | Partial updates work | Partial update |
| `test_update_config_invalid` | Invalid keys ignored | Input validation |
| `test_get_backends` | GET /config/backends | Backend info |

#### Test File: `tests/web/test_logs_api.py`

| Test Case | Description | Coverage Target |
|-----------|-------------|-----------------|
| `test_get_log_whole` | GET /logs/ returns full log | Full log |
| `test_get_log_whole_missing` | Handle missing log file | Edge case |
| `test_get_log_tail` | GET /logs/tail returns N lines | Tail operation |
| `test_get_log_tail_custom_lines` | Custom line count | Parameter handling |
| `test_get_log_tail_invalid_param` | Invalid lines param | Input validation |

**External Interface Considerations:**
- Use Flask's test client for API testing
- Mock configuration and log files for isolation

---

### 6. Utilities Module (`src/ipr_keyboard/utils/`)

#### Test File: `tests/utils/test_helpers.py`

| Test Case | Description | Coverage Target |
|-----------|-------------|-----------------|
| `test_project_root` | Resolve project root path | Path resolution |
| `test_config_path` | Get config.json path | Config path |
| `test_load_json` | Load JSON file | File reading |
| `test_load_json_missing` | Handle missing file | Error handling |
| `test_save_json` | Save JSON file | File writing |
| `test_save_json_creates_dirs` | Create parent dirs | Directory creation |

---

## Component/Integration Tests

### 1. USB Flow Integration (`tests/integration/test_usb_flow.py`)

Tests the complete USB file handling flow:

| Test Case | Description |
|-----------|-------------|
| `test_file_detection_and_read` | Detect new file → Read content |
| `test_file_detection_and_delete` | Detect → Read → Delete workflow |
| `test_multiple_files_processing` | Process multiple files in order |
| `test_file_size_limit` | Reject oversized files |

### 2. Web API Integration (`tests/integration/test_web_integration.py`)

Tests the complete web API:

| Test Case | Description |
|-----------|-------------|
| `test_config_round_trip` | Get → Update → Get config |
| `test_logs_after_operations` | Log entries appear after operations |
| `test_health_check` | Health endpoint availability |

### 3. Main Module (`tests/integration/test_main.py`)

Tests the main application entry point:

| Test Case | Description |
|-----------|-------------|
| `test_main_initialization` | Application starts correctly |
| `test_web_server_thread` | Web server starts in thread |
| `test_usb_bt_loop_mocked` | USB→BT loop with mocks |

---

## External Interface Testing

### Bluetooth Connection Testing

**Unit Tests** (mocked):
- Mock `subprocess.run` to simulate helper script
- Test success/failure scenarios without actual Bluetooth

**Manual/Interactive Testing** (using scripts):
```bash
# Test Bluetooth HID daemon
./scripts/test_bluetooth.sh "Test string"

# Switch keyboard backend
sudo ./scripts/ble_switch_backend.sh
```

### USB Connection Testing

**Unit Tests** (mocked):
- Use `tmp_path` fixture for temporary directories
- Simulate file creation, modification, and deletion

**Manual/Interactive Testing** (using scripts):
```bash
# Set up IrisPen mount
sudo ./scripts/usb_setup_mount.sh /dev/sda1

# Mount MTP device
sudo ./scripts/usb_mount_mtp.sh

# Sync files from MTP
./scripts/usb_sync_cache.sh
```

### Web API Testing

**Unit Tests**:
- Use Flask test client
- Mock configuration and log files

**Manual/Interactive Testing**:
```bash
# Start dev server
./scripts/dev_run_app.sh

# Test endpoints
curl http://localhost:8080/health
curl http://localhost:8080/config/
curl http://localhost:8080/logs/tail?lines=50
```

---



## Manual Testing Procedures

### Prerequisites

Before performing manual tests, ensure the following prerequisites are met:

1. **Raspberry Pi Setup**
    - Raspberry Pi is running Raspberry Pi OS or compatible Linux distribution.
    - All system updates are applied.
    - The `ipr-keyboard` project and all dependencies are installed according to the documentation.
    - Python virtual environment is set up and activated if running in development mode.

2. **Bluetooth Pairing (as Keyboard)**
    - The Raspberry Pi must be configured to act as a Bluetooth HID keyboard.
    - The Bluetooth helper (`/usr/local/bin/bt_kb_send`) and daemon (`bt_hid_daemon.service`) are installed and running.
    - To pair the target device (PC, tablet, etc.) with the Pi as a keyboard:
      1. Make the Raspberry Pi discoverable:
          ```bash
          bluetoothctl
          [bluetoothctl]> discoverable on
          [bluetoothctl]> pairable on
          [bluetoothctl]> agent NoInputNoOutput
          [bluetoothctl]> default-agent
          ```
      2. On the target device, search for new Bluetooth devices. The Pi should appear as a keyboard (e.g., "IPR Keyboard" or "Raspberry Pi Keyboard").
      3. Initiate pairing from the target device. With "NoInputNoOutput" agent, pairing happens automatically using "Just Works" - no PIN or passkey entry required.
      4. After successful pairing, ensure the device is connected as a keyboard (check in `bluetoothctl` with `info <device-mac>` or via the desktop Bluetooth UI).
      5. If using a headless Pi, you may need to SSH in and use `bluetoothctl` exclusively.
    - Only one device can typically be paired as a keyboard at a time.

3. **USB/IrisPen Setup**
    - The IrisPen or USB stick is available and can be mounted on the Pi.
    - For MTP devices, ensure `mtp-tools` or equivalent is installed.
    - The mount point (default: `/mnt/irispen`) is configured in `config.json`.

4. **Network Access (for Web API)**
    - The Pi and the test client (PC, phone, etc.) are on the same network.
    - Firewall allows access to the configured web API port (default: 8080).

5. **Log Directory**
    - The `logs/` directory exists and is writable by the application.

6. **Service/Development Mode**
    - The application is running either as a systemd service or in development mode using `./scripts/dev_run_app.sh`.

---

The following manual test steps are required to verify correct operation of the Bluetooth, USB, Web, and Logging functionality. These steps should be performed on a fully set up Raspberry Pi with all dependencies installed and the system configured as described above.

### 1. Bluetooth Functionality

**Goal:** Verify that text can be sent from the Pi to a paired device via Bluetooth HID keyboard emulation.

**Steps:**
1. Ensure the target device (PC, tablet, etc.) is paired and connected to the Raspberry Pi as a Bluetooth keyboard.
2. On the Pi, run:
    ```bash
    ./scripts/test_bluetooth.sh "Hello Bluetooth Test ÆØÅ"
    ```
3. Focus a text input field on the paired device (e.g., Notepad, browser, terminal).
4. Observe that the test string appears as keyboard input on the paired device.
5. If nothing appears, check:
    - The status of the Bluetooth daemon: `sudo systemctl status bt_hid_daemon.service`
    - That `/usr/local/bin/bt_kb_send` exists and is executable
    - The Pi is still paired and connected as a keyboard
    - Logs for errors: `sudo journalctl -u bt_hid_daemon.service -f`

### 2. USB Functionality

**Goal:** Verify that the system detects, reads, and (optionally) deletes new files from the IrisPen USB or MTP device.

**Steps:**
1. Connect the IrisPen or USB stick to the Pi and ensure it is mounted at the configured path (default: `/mnt/irispen`).
2. If using MTP, mount with:
    ```bash
    sudo ./scripts/usb_mount_mtp.sh
    ./scripts/usb_sync_cache.sh
    ```
3. Use the IrisPen to scan text, or manually create a `.txt` file in the mount folder.
4. Observe that the file is detected, read, and (if configured) deleted by the application.
5. Check logs for file detection and processing events.
6. To test file deletion, set `DeleteFiles: true` in `config.json` or via the web API.

### 3. Web API Functionality

**Goal:** Verify that the web API is accessible and provides configuration, logs, and health endpoints.

**Steps:**
1. Start the application (as a service or with `./scripts/dev_run_app.sh`).
2. From another device on the same network, open a browser and visit:
    - `http://<pi-ip>:8080/health` (should return `{ "status": "ok" }`)
    - `http://<pi-ip>:8080/config/` (should return current config as JSON)
    - `http://<pi-ip>:8080/logs/tail?lines=50` (should show recent log entries)
3. Use `curl` to POST a config update:
    ```bash
    curl -X POST http://<pi-ip>:8080/config/ -H "Content-Type: application/json" -d '{"DeleteFiles": false}'
    ```
4. Confirm the change is reflected in subsequent GET requests.
5. Test error handling by sending invalid requests and observing error responses.

### 4. Logging Functionality

**Goal:** Verify that all actions are logged to both file and console, and logs are accessible via the web API.

**Steps:**
1. Trigger actions (Bluetooth send, USB file detection, config changes) as above.
2. Check the log file directly:
    ```bash
    tail -n 50 logs/ipr_keyboard.log
    ```
3. Access logs via the web API as described above.
4. Confirm that log entries are timestamped, include action details, and rotate as expected when the file size limit is reached.

---

---

## Test Fixtures (conftest.py)

Common fixtures for all tests:

```python
@pytest.fixture
def temp_config(tmp_path, monkeypatch):
    """Create a temporary config file and patch ConfigManager."""

@pytest.fixture
def temp_log_dir(tmp_path, monkeypatch):
    """Create a temporary log directory."""

@pytest.fixture
def mock_bt_helper(monkeypatch):
    """Mock the Bluetooth helper subprocess."""

@pytest.fixture
def flask_client(temp_config):
    """Create a Flask test client with temporary config."""

@pytest.fixture
def usb_folder(tmp_path):
    """Create a temporary USB folder with test files."""
```

---

## Running Tests

### Run All Tests
```bash
pytest
```

### Run with Coverage
```bash
pytest --cov=ipr_keyboard --cov-report=term-missing
```

### Run Specific Modules
```bash
pytest tests/bluetooth/
pytest tests/usb/test_detector.py
pytest tests/integration/
```

### Run with Verbose Output
```bash
pytest -v
```

---

## Coverage Goals

| Module | Current | Target |
|--------|---------|--------|
| bluetooth/keyboard.py | 65% | 95% |
| config/manager.py | 91% | 98% |
| config/web.py | 88% | 95% |
| logging/logger.py | 100% | 100% |
| logging/web.py | 32% | 95% |
| usb/detector.py | 48% | 95% |
| usb/reader.py | 53% | 95% |
| usb/deleter.py | 50% | 95% |
| usb/mtp_sync.py | 0% | 90% |
| web/server.py | 93% | 98% |
| utils/helpers.py | 94% | 100% |
| main.py | 0% | 70% |
| **TOTAL** | 49% | **85%+** |

---

## Dependencies

Test dependencies are in `pyproject.toml`:
- pytest
- pytest-cov (for coverage reports)

Install with:
```bash
uv pip install -e ".[dev]"
```
