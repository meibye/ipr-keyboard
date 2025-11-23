# Copilot Coding Agent Instructions for ipr-keyboard

## Project Overview
- **Purpose**: Bridges IrisPen USB scanner to a paired device via Bluetooth HID keyboard emulation on Raspberry Pi.
- **Main Flow**: Monitors a USB folder for new text files (from IrisPen), reads content, sends via Bluetooth keyboard, optionally deletes files, logs all actions, and exposes a web API for config/logs.

## Architecture & Key Components
- **Entry Point**: `src/ipr_keyboard/main.py` orchestrates all modules, starts web server and USB/Bluetooth monitor threads.
- **Bluetooth**: `src/ipr_keyboard/bluetooth/keyboard.py` wraps a system helper (`/usr/local/bin/bt_kb_send`) to send text as keyboard input. Check helper availability before sending.
- **USB Handling**: `src/ipr_keyboard/usb/` provides file detection (`detector.py`), reading (`reader.py`), and deletion (`deleter.py`). Uses file modification time to detect new files.
- **Configuration**: `src/ipr_keyboard/config/manager.py` implements a thread-safe singleton `ConfigManager` with JSON persistence (`config.json` in project root). Config is accessible and updatable at runtime.
- **Logging**: `src/ipr_keyboard/logging/logger.py` sets up a rotating file logger (`logs/ipr_keyboard.log`) and console output. Log viewing is available via web API.
- **Web API**: `src/ipr_keyboard/web/server.py` (Flask) exposes `/config/`, `/logs/`, and `/health` endpoints. Blueprints for config/logs are in their respective modules.
- **Utilities**: `src/ipr_keyboard/utils/helpers.py` provides project root and config path resolution, and JSON file helpers.

## Developer Workflows
- **Setup**: Use numbered scripts in `scripts/` for system setup, Bluetooth config, venv creation (with `uv`), and service install. See `scripts/README.md` for order and details.
- **Development Run**: Use `./scripts/run_dev.sh` to run app in foreground with logs to console. Requires venv and env vars from `00_set_env.sh`.
- **Testing**: Run `pytest` or `pytest --cov=ipr_keyboard` (see `tests/README.md`). Tests mirror source structure and use pytest conventions.
- **Service Mode**: Installed as a systemd service via `05_install_service.sh`. Service runs as non-root user, working dir is project root, entry is `python -m ipr_keyboard.main`.
- **Diagnostics**: Use `./scripts/10_diagnose_failure.sh` for comprehensive troubleshooting (checks config, venv, logs, service, Bluetooth helper, etc).

## Project-Specific Conventions
- **Config**: Always use `ConfigManager.instance()` for config access. Updates are persisted and thread-safe.
- **Logging**: Use `get_logger()` from logging module. All logs go to rotating file and console.
- **Bluetooth**: Always check `BluetoothKeyboard.is_available()` before sending text. Helper script is a system dependency.
- **File Handling**: Use provided USB module functions for file detection, reading, and deletion. Do not access files directly.
- **Web API**: Register new endpoints as Flask blueprints. All config/log endpoints are under `/config/` and `/logs/`.
- **Testing**: Place tests in `tests/` mirroring source structure. Use fixtures and avoid test interdependence.

## Integration Points & External Dependencies
- **Bluetooth Helper**: `/usr/local/bin/bt_kb_send` (installed by `03_install_bt_helper.sh`).
- **Python venv**: Created with `uv` (see `04_setup_venv.sh`).
- **Systemd**: Service installed by `05_install_service.sh`.
- **IrisPen Mount**: USB or MTP mount at `/mnt/irispen` (configurable).

## Examples
- **Send text via Bluetooth**:
  ```python
  from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard
  kb = BluetoothKeyboard()
  if kb.is_available():
      kb.send_text("Hello world!")
  ```
- **Update config via web API**:
  ```bash
  curl -X POST http://localhost:8080/config/ -H "Content-Type: application/json" -d '{"DeleteFiles": false}'
  ```
- **View logs via web API**:
  ```bash
  curl http://localhost:8080/logs/tail?lines=50
  ```

## References
- [README.md](../README.md) — Project overview
- [scripts/README.md](../scripts/README.md) — Setup and workflow scripts
- [src/ipr_keyboard/README.md](../src/ipr_keyboard/README.md) — Code structure
- [tests/README.md](../tests/README.md) — Test suite

---

**If you are an AI coding agent, follow these conventions and reference the above files for project-specific details.**
