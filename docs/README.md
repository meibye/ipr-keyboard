# Documentation Index

This repository keeps tool-facing control files at the repository root and
human-facing technical documentation under `docs/`.

Audited 2026-10-04: every path below exists, and nothing under `docs/` is
missing from it.

## Keep at repository root

- `README.md` — project entry point and quick start
- `AGENTS.md` — Codex / agent guidance
- `CLAUDE.md` — Claude Code guidance
- `SERVICES.md` — service inventory and install sequence
- `DEVICE_BRINGUP.md` — provisioning and bring-up procedure
- `TESTING_PLAN.md` — the six test tiers and the full test inventory

## Architecture

- `docs/architecture/ARCHITECTURE.md` — canonical architecture baseline and
  cleanup decision rules
- `docs/architecture/led-status-design.md` — the status LED and (on a device
  with no panel) the timed magnet ladder
- `docs/architecture/magnet-menu-design.md` — the magnet menu that replaced the
  ladder, and how a tap is told from a hold
- `docs/architecture/oled-display-design.md` — what the panel shows and why

## Hardware

- `docs/hardware/gpio-wiring.md` — LED and reed-switch wiring
- `docs/hardware/oled-display.md` — the panel: behaviour, every screen,
  configuration and troubleshooting

## Operations

- `docs/operations/performance.md` — where the time goes in a scan, the typing
  speed and how to tune it, and the KPIs
- `docs/operations/bluetooth-pairing.md` — pairing, reconnecting after a
  restart, advertising intervals, and what not to try
- `docs/operations/network-modes.md` — home network, hotspot, and the three
  network names
- `docs/operations/irispen-automount.md` — the MTP mount and its quirks
- `docs/operations/unsupervised-operation.md` — how a fault becomes visible on
  a device nobody is watching
- `docs/operations/disk-and-logs.md` — what grows, what bounds it, and why no
  cleanup job is needed

## Release

- `docs/release-checklist.md` — **the five gates.** The authoritative hands-on
  list; `TESTING_PLAN.md` is the broader strategy around it

## UI and API

- `docs/ui/dashboard-spec.md` — every dashboard screen and what it must show
- `docs/ui/api-contract.md` — every `/api/` endpoint, request and response
- `docs/ui/user-states.md` — the user-facing state model the backend maps onto
- `docs/ui/wireframes.md` — layout sketches

## End users

- `docs/user/hotspot-setup.md` — joining the setup network, for a non-technical
  reader
- `docs/manuals/` — Danish end-user and administrator manuals (Word) plus their
  generators; see `docs/manuals/README.md` for how to rebuild them

## Development

- `docs/development/development-workflow.md` — day-to-day loop and common
  commands
- `docs/copilot/` — Copilot and AI assistant playbooks

## Guidance

When cleaning or refactoring, start from `docs/architecture/ARCHITECTURE.md`
and use the operations docs as the current-state reference.

Earlier revisions of this index pointed at five files that do not exist:
a testing plan under `docs/development/`, a device bring-up and a services
page under `docs/operations/`, a script evaluation under `docs/maintenance/`
and a pairing-fix summary under `docs/history/`. The first three live at the
repository root as `TESTING_PLAN.md`, `DEVICE_BRINGUP.md` and `SERVICES.md`;
the last two were never written. Paths are deliberately not quoted as links
here, so a link check does not flag them again.
