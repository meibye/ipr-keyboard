# Copilot Coding Agent Instructions for ipr-keyboard

## Project Purpose & Architecture
- Bridges IrisPen USB scanner output to a paired device via Bluetooth HID keyboard emulation (Raspberry Pi target).
- Main flow: Monitors a USB/MTP mount for new text files, reads content, sends via Bluetooth keyboard, optionally deletes files, logs all actions, exposes a web API for config/logs.

### Major Components
- **Entry Point:** `src/ipr_keyboard/main.py` — Orchestrates all modules, starts web server and USB/Bluetooth monitor threads.
- **Bluetooth:** `src/ipr_keyboard/bluetooth/keyboard.py` wraps `/usr/local/bin/bt_kb_send` (system helper) to send text as keyboard input. Supports BLE and uinput backends, selected via config and `/etc/ipr-keyboard/backend`.
- **USB Handling:** `src/ipr_keyboard/usb/` — File detection (`detector.py`), reading (`reader.py`), deletion (`deleter.py`), and MTP sync (`mtp_sync.py`). Uses file modification time to detect new files.
- **Configuration:** `src/ipr_keyboard/config/manager.py` — Thread-safe singleton `ConfigManager` with JSON persistence (`config.json` in project root). Backend selection is auto-synced with `/etc/ipr-keyboard/backend`.
- **Logging:** `src/ipr_keyboard/logging/logger.py` — Rotating file logger (`logs/ipr_keyboard.log`) and console output. Log viewing via web API.
- **Web API:** `src/ipr_keyboard/web/server.py` (Flask) — Exposes `/config/`, `/logs/`, `/health` endpoints. Blueprints for config/logs.
- **Utilities:** `src/ipr_keyboard/utils/helpers.py` — Project root/config path resolution, JSON helpers, backend sync utilities.

## Developer Workflows
- **Provisioning:** Use scripts in `provision/` for automated setup (see `provision/README.md`).
- **Manual Setup:** Use scripts in `scripts/` for system setup, Bluetooth config, venv creation (with `uv`), and service install. See `scripts/README.md`.
- **Development Run:** `./scripts/dev_run_app.sh` — Runs app in foreground with logs to console (requires venv and env vars).
- **Testing:** Run `pytest` or `pytest --cov=ipr_keyboard` (see `tests/README.md`). Tests mirror source structure and use pytest conventions. End-to-end/systemd tests in `scripts/test_*.sh`.
- **Service Mode:** Installed as a systemd service via provisioning scripts. Service runs as non-root user, working dir is project root, entry is `python -m ipr_keyboard.main`.
- **Diagnostics:** Use `./scripts/diag_troubleshoot.sh` for comprehensive troubleshooting (checks config, venv, logs, service, Bluetooth helper, etc). Bluetooth-specific: `scripts/ble/`, `scripts/rpi-debug/`.

## Project-Specific Conventions
- **Config:** Always use `ConfigManager.instance()` for config access. Updates are persisted and thread-safe. Backend selection is auto-synced with `/etc/ipr-keyboard/backend`.
- **Logging:** Use `get_logger()` from logging module. All logs go to rotating file and console. Log file: `logs/ipr_keyboard.log` (rotates at 256KB, 5 backups).
- **Bluetooth:** Always check `BluetoothKeyboard.is_available()` before sending text. Helper script is a system dependency. Backends: BLE (recommended for Windows 11) and uinput.
- **File Handling:** Use USB module functions for file detection, reading, deletion. Do not access files directly.
- **Web API:** Register new endpoints as Flask blueprints. All config/log endpoints are under `/config/` and `/logs/`.
- **Testing:** Place tests in `tests/` mirroring source structure. Use fixtures, avoid test interdependence. End-to-end/systemd tests in `scripts/`.

## Integration Points & External Dependencies
- **Bluetooth Helper:** `/usr/local/bin/bt_kb_send` (installed by `scripts/ble/ble_install_helper.sh`).
- **Python venv:** Created with `uv` (see provisioning scripts).
- **Systemd:** Services installed by provisioning scripts.
- **IrisPen Mount:** USB or MTP mount at `/mnt/irispen` (configurable).
- **Backend Sync:** `config.json` and `/etc/ipr-keyboard/backend` are always kept in sync (see config/README.md).

## Examples
- **Send text via Bluetooth:**
  ```python
  from ipr_keyboard.bluetooth.keyboard import BluetoothKeyboard
  kb = BluetoothKeyboard()
  if kb.is_available():
      kb.send_text("Hello world!")
  ```
- **Update config via web API:**
  ```bash
  curl -X POST http://localhost:8080/config/ -H "Content-Type: application/json" -d '{"DeleteFiles": false}'
  ```
- **View logs via web API:**
  ```bash
  curl http://localhost:8080/logs/tail?lines=50
  ```


## Key References
- [README.md](../README.md) — Project overview
- [src/ipr_keyboard/README.md](../src/ipr_keyboard/README.md) — Code structure
- [scripts/README.md](../scripts/README.md) — Setup and workflow scripts
- [provision/README.md](../provision/README.md) — Automated provisioning system
- [tests/README.md](../tests/README.md) — Test suite
- [scripts/ble/README.md](../scripts/ble/README.md) — Bluetooth-specific scripts
- [scripts/rpi-debug/README.md](../scripts/rpi-debug/README.md) — Remote diagnostic scripts

---

**If you are an AI coding agent, follow these conventions and reference the above files for project-specific details.**
