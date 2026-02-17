# GitHub Copilot Instructions for ipr-keyboard

## Source of Truth

Use `ARCHITECTURE.md` as the canonical reference for current system design.
Use `docs/copilot/*.md` as the canonical prompt/skills source.

## Shared Prompt Catalog

The following prompt files are available for Copilot and mirrored from `docs/copilot`:

- `.github/prompts/copilot/ARCH_ALIGNMENT_PROMPT.md`
- `.github/prompts/copilot/DIAG_AGENT_PROMPT.md`
- `.github/prompts/copilot/LOCAL_ONLY_PROMPT.md`
- `.github/prompts/copilot/BT_PAIRING_PLAYBOOK.md`

Shared skills file:

- `.github/prompts/copilot/PYTHON_AGENT_SKILLS.md`

## Current Stack Summary

- Python package: `src/ipr_keyboard`
- Entry point: `ipr_keyboard.main:main`
- BLE service path: `bt_hid_ble.service` + `bt_hid_agent_unified.service`
- Send helper: `/usr/local/bin/bt_kb_send`
- Main service: `ipr_keyboard.service`

# Project Guidelines

## Code Style

- Python 3.12+ (see [pyproject.toml](pyproject.toml))
- Use dataclasses for config/state ([src/ipr_keyboard/config/manager.py](src/ipr_keyboard/config/manager.py))
- Prefer type hints and docstrings throughout
- Logging via [get_logger()](src/ipr_keyboard/logging/logger.py)
- Web endpoints registered via Flask blueprints ([src/ipr_keyboard/web/server.py](src/ipr_keyboard/web/server.py))
- USB file logic via helpers ([src/ipr_keyboard/usb/detector.py](src/ipr_keyboard/usb/detector.py), [src/ipr_keyboard/usb/reader.py](src/ipr_keyboard/usb/reader.py), [src/ipr_keyboard/usb/deleter.py](src/ipr_keyboard/usb/deleter.py))

## Architecture

- Canonical module map: [ARCHITECTURE.md](ARCHITECTURE.md)
- Main app: [src/ipr_keyboard/main.py](src/ipr_keyboard/main.py)
- BLE backend: [bt_hid_ble.service](scripts/service/svc/bt_hid_ble.service), [bt_hid_agent_unified.service](scripts/service/svc/bt_hid_agent_unified.service)
- Helper: [bt_kb_send.sh](scripts/ble/bt_kb_send.sh)
- Web server: [src/ipr_keyboard/web/server.py](src/ipr_keyboard/web/server.py)
- Config: [src/ipr_keyboard/config/manager.py](src/ipr_keyboard/config/manager.py), [config.json](config.json)
- See [ARCHITECTURE.md](ARCHITECTURE.md) for current vs legacy/deprecated patterns

## Build and Test

- Setup: `./scripts/sys_setup_venv.sh`
- Run app: `./scripts/dev_run_app.sh`
- Run web: `./scripts/dev_run_webserver.sh`
- Test: `pytest` or `pytest --cov=ipr_keyboard --cov-report=term-missing`
- E2E/systemd: `./scripts/test_e2e_demo.sh`, `./scripts/test_e2e_systemd.sh`, `./scripts/test_smoke.sh`
- See [tests/README.md](tests/README.md) for test inventory

## Project Conventions

- Config reads/updates via `ConfigManager.instance()` ([src/ipr_keyboard/config/manager.py](src/ipr_keyboard/config/manager.py))
- Logging via `get_logger()` ([src/ipr_keyboard/logging/logger.py](src/ipr_keyboard/logging/logger.py))
- USB file ops via helpers ([src/ipr_keyboard/usb/detector.py](src/ipr_keyboard/usb/detector.py), [src/ipr_keyboard/usb/reader.py](src/ipr_keyboard/usb/reader.py), [src/ipr_keyboard/usb/deleter.py](src/ipr_keyboard/usb/deleter.py))
- Web endpoints in blueprints/app factory ([src/ipr_keyboard/web/server.py](src/ipr_keyboard/web/server.py))
- Pairing wizard: [src/ipr_keyboard/web/pairing_routes.py](src/ipr_keyboard/web/pairing_routes.py)
- Legacy/compatibility paths flagged per [ARCHITECTURE.md](ARCHITECTURE.md)

## Integration Points

- BLE HID stack via systemd services ([scripts/service/svc/bt_hid_ble.service](scripts/service/svc/bt_hid_ble.service), [scripts/service/svc/bt_hid_agent_unified.service](scripts/service/svc/bt_hid_agent_unified.service))
- Helper script: `/usr/local/bin/bt_kb_send` ([scripts/ble/bt_kb_send.sh](scripts/ble/bt_kb_send.sh))
- Flask web API ([src/ipr_keyboard/web/server.py](src/ipr_keyboard/web/server.py))
- Provisioning pipeline ([provision/README.md](provision/README.md))

## Security

- Sensitive config in `/opt/ipr_common.env` (see [provision/README.md](provision/README.md))
- BLE pairing and agent services run as systemd units
- No destructive actions without explicit approval (see [docs/copilot/DIAG_AGENT_PROMPT.md](docs/copilot/DIAG_AGENT_PROMPT.md))

## Development Commands

```bash
./scripts/sys_setup_venv.sh
./scripts/dev_run_app.sh
pytest --cov=ipr_keyboard --cov-report=term-missing
```

## Implementation Conventions

- Use `ConfigManager.instance()` for config reads/updates.
- Use `get_logger()` from `src/ipr_keyboard/logging/logger.py`.
- Use USB helper modules (`detector`, `reader`, `deleter`) instead of ad-hoc file logic.
- Keep web endpoints registered in blueprints/app factory patterns.

## Architectural Alignment Skill

When asked to "clean" the repo, compare every module against ARCHITECTURE.md. If a module implements a pattern marked as "Deprecated" or "Legacy" in the architecture doc, even if it is still being called, flag it as Architectural Dead Code and propose a refactor or removal.
