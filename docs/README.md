# Documentation Index

This repository keeps tool-facing control files at the repository root and human-facing technical documentation under `docs/`.

## Keep at repository root

- `README.md` — project entry point and quick start
- `AGENTS.md` — Codex / agent guidance
- `CLAUDE.md` — Claude Code guidance

## Documentation sections

- `docs/architecture/ARCHITECTURE.md` — canonical architecture baseline and cleanup decision rules
- `docs/development/development-workflow.md` — day-to-day development loop and common commands
- `docs/development/testing-plan.md` — test inventory, validation commands, and acceptance criteria
- `docs/operations/device-bringup.md` — provisioning and bring-up procedure
- `docs/operations/services.md` — current service inventory and install sequence
- `docs/operations/bluetooth-pairing.md` — current BLE pairing flow and diagnostics
- `docs/maintenance/script-evaluation.md` — current script keep/remove evaluation baseline
- `docs/history/pairing-fix-summary.md` — historical pairing fix notes and retained context

## Existing specialized docs

- `docs/copilot/` — Copilot and AI assistant playbooks
- `docs/ui/` — UI and API documentation for the dashboard

## Guidance

When cleaning or refactoring the repo, start from `docs/architecture/ARCHITECTURE.md` and use the development and operations docs as the current-state references.
