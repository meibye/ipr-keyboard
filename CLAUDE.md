# CLAUDE.md

Project instructions for Claude Code in this repository.

## Canonical Architecture Reference

`ARCHITECTURE.md` is the source of truth for current vs legacy/deprecated patterns.

## Current Runtime Expectations

- App entry: `python -m ipr_keyboard.main`
- Canonical services: `ipr_keyboard.service`, `bt_hid_ble.service`, `bt_hid_agent_unified.service`, `ipr-provision.service`
- Helper send path: `/usr/local/bin/bt_kb_send`

## Working Rules

1. Prefer edits aligned to modules marked `Current` in `ARCHITECTURE.md`.
2. If touching modules marked `Legacy` or `Deprecated`, call this out before extending behavior.
3. Keep docs and prompt files aligned with repository implementation state.

## Architectural Alignment Skill

When asked to "clean" the repo, compare every module against ARCHITECTURE.md. If a module implements a pattern marked as "Deprecated" or "Legacy" in the architecture doc, even if it is still being called, flag it as Architectural Dead Code and propose a refactor or removal.
