

# Copilot Coding Agent Instructions for ipr-keyboard

## Project Architecture & Data Flow

- **Purpose:** Bridges IrisPen USB scanner output to a paired device via Bluetooth HID keyboard emulation (RPi target).
- **Main Flow:**
  1. Monitors USB/MTP mount for new text files (IrisPen output)
  2. Reads file content, sends via Bluetooth keyboard (using `/usr/local/bin/bt_kb_send`)
  3. Optionally deletes files, logs all actions
  4. Exposes Flask web API for config/logs
- **Major Components:**
  - `src/ipr_keyboard/main.py`: Entry point, orchestrates modules, starts web server and monitor threads
  - `src/ipr_keyboard/bluetooth/keyboard.py`: Wraps `bt_kb_send` for keyboard emulation; supports BLE/uinput backends (configurable)
  - `src/ipr_keyboard/usb/`: File detection (`detector.py`), reading (`reader.py`), deletion (`deleter.py`), MTP sync (`mtp_sync.py`)
  - `src/ipr_keyboard/config/manager.py`: Thread-safe singleton config manager, JSON-backed, auto-syncs backend
  - `src/ipr_keyboard/logging/logger.py`: Rotating file logger and console output
  - `src/ipr_keyboard/web/server.py`: Flask API (`/config/`, `/logs/`, `/health`)
  - `src/ipr_keyboard/utils/helpers.py`: Path resolution, JSON helpers, backend sync

## Developer Workflows

- **Provisioning:** Use scripts in `provision/` for automated setup ([provision/README.md](provision/README.md)).
- **Manual Setup:** Use scripts in `scripts/` for system setup, Bluetooth config, venv creation (with `uv`), and service install ([scripts/README.md](scripts/README.md)).
- **Development Run:** `./scripts/dev_run_app.sh` (foreground, logs to console)
- **Testing:** `pytest` or `pytest --cov=ipr_keyboard` ([tests/README.md](tests/README.md)). Tests mirror source structure, use fixtures, avoid interdependence.
- **Diagnostics:** `./scripts/diag_troubleshoot.sh` for troubleshooting. Bluetooth-specific: `scripts/ble/`, remote diagnostics: `scripts/rpi-debug/`.
- **Service Mode:** Installed as a systemd service via provisioning scripts. Runs as non-root, working dir is project root, entry is `python -m ipr_keyboard.main`.

## Project-Specific Conventions

- **Config:** Use `ConfigManager.instance()` for config access. Updates are persisted and thread-safe. Backend selection is auto-synced with `/etc/ipr-keyboard/backend`.
- **Logging:** Use `get_logger()` from logging module. Log file: `logs/ipr_keyboard.log` (rotates at 256KB, 5 backups).
- **Bluetooth:** Always check `BluetoothKeyboard.is_available()` before sending text. Helper script is a system dependency. Backends: BLE (recommended for Windows 11) and uinput.
- **File Handling:** Use USB module functions for file detection, reading, deletion. Do not access files directly.
- **Web API:** Register new endpoints as Flask blueprints. All config/log endpoints are under `/config/` and `/logs/`.
- **Testing:** Place tests in `tests/` mirroring source structure. Use fixtures, avoid test interdependence. End-to-end/systemd tests in `scripts/`.

## Integration Points & External Dependencies

- **Bluetooth Helper:** `/usr/local/bin/bt_kb_send` (installed by `scripts/ble/ble_install_helper.sh`)
- **Python venv:** Created with `uv` (see provisioning scripts)
- **Systemd:** Services installed by provisioning scripts
- **IrisPen Mount:** USB or MTP mount at `/mnt/irispen` (configurable)
- **Backend Sync:** `config.json` and `/etc/ipr-keyboard/backend` are always kept in sync

## Remote Diagnostics & Copilot Agent Mode


- **MCP Server Usage:**
  - Use MCP servers defined in `mcp.json` for remote diagnostics, automation, and agent workflows when you need to interact with a live Raspberry Pi or other remote device.
  - Prefer MCP server actions for tasks that require real device state, logs, or hardware access (e.g., running scripts in `scripts/rpi-debug/`, checking Bluetooth stack, deploying updates).
  - Always use the whitelisted diagnostic scripts (see `scripts/rpi-debug/README.md`) via MCP server commands; do not run arbitrary shell commands.
  - For agent-driven troubleshooting, follow the plan-first, bounded workflow described in `docs/copilot/DIAG_AGENT_PROMPT.md`.
  - Use local emulation or simulation only for code that does not require hardware or system-level access.

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

- [README.md](README.md) — Project overview
- [src/ipr_keyboard/README.md](src/ipr_keyboard/README.md) — Code structure
- [scripts/README.md](scripts/README.md) — Setup and workflow scripts
- [provision/README.md](provision/README.md) — Automated provisioning system
- [tests/README.md](tests/README.md) — Test suite
- [scripts/ble/README.md](scripts/ble/README.md) — Bluetooth-specific scripts
- [scripts/rpi-debug/README.md](scripts/rpi-debug/README.md) — Remote diagnostic scripts

---

**If you are an AI coding agent, follow these conventions and reference the above files for project-specific details.**
