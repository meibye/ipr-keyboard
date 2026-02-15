# GitHub Copilot Instructions for ipr-keyboard

## Source of Truth

Use `ARCHITECTURE.md` as the canonical reference for current system design.

## Current Stack Summary

- Python package: `src/ipr_keyboard`
- Entry point: `ipr_keyboard.main:main`
- BLE service path: `bt_hid_ble.service` + `bt_hid_agent_unified.service`
- Send helper: `/usr/local/bin/bt_kb_send`
- Main service: `ipr_keyboard.service`

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
