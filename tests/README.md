# Tests

This directory contains the test suite for the ipr-keyboard project using pytest.

## Test Structure

The tests are organized to mirror the source code structure:

- `bluetooth/` - Tests for Bluetooth keyboard functionality
- `config/` - Tests for configuration management
- `logging/` - Tests for logging functionality
- `usb/` - Tests for USB file detection, reading, and deletion
- `web/` - Tests for web API endpoints

## Running Tests

### Run all tests

```bash
pytest
```

### Run tests with coverage

```bash
pytest --cov=ipr_keyboard
```

### Run specific test module

```bash
pytest tests/config/
pytest tests/bluetooth/test_keyboard.py
```

## Test Modules

### Bluetooth Tests (`bluetooth/`)
- `test_keyboard.py` - Tests for BluetoothKeyboard wrapper and helper script interaction

### Configuration Tests (`config/`)
- `test_manager.py` - Tests for ConfigManager singleton, thread-safety, and JSON persistence

### Logging Tests (`logging/`)
- `test_logger.py` - Tests for logger initialization and file handling

### USB Tests (`usb/`)
- `test_usb_reader.py` - Tests for file reading and detection functionality

### Web Tests (`web/`)
- `test_config_api.py` - Tests for configuration REST API endpoints

## Writing Tests

Tests follow pytest conventions:
- Test files are named `test_*.py`
- Test functions are named `test_*`
- Use fixtures for common setup/teardown
- Keep tests isolated and independent

## Dependencies

Test dependencies are defined in `pyproject.toml` under `[project.optional-dependencies]`:
- pytest
- pytest-cov (for coverage reports)
