# Claude project context

## How to operate in this repository
Follow AGENTS.md as the primary repository policy.

## Workflow preferences
- Use skills for repeatable workflows
- Use subagents for specialized review or generation
- Use hooks and local commands to validate changes automatically where configured
- Use MCP when live system context is needed instead of guessing

## Required behavior
- Make minimal, well-scoped edits
- Preserve architecture boundaries
- Update tests and docs when behavior changes
- Summarize validation results clearly

## Preferred subagents
- reviewer
- tester
- docs-writer
- security-auditor

## Protected areas
Do not modify without explicit need:
- generated artifacts
- secrets and environment templates
- deployment manifests shared across environments

## Project

Raspberry Pi based BLE HID keyboard / pen bridge with a local web dashboard.

## Runtime reality

Target device is Raspberry Pi Zero 2 W.
Changes must respect limited CPU, RAM, and storage.

## Important product direction

The web UI should be:

- image-first
- easy for non-technical users to understand
- responsive on local browsers
- lightweight and robust
- built around status, events, configuration, reboot, and shutdown

## Read before changing the dashboard

- `docs/ui/dashboard-spec.md`
- `docs/ui/wireframes.md`
- `docs/ui/user-states.md`
- `docs/ui/api-contract.md`

## Existing baseline

Flask server: `src/ipr_keyboard/web/server.py`
Templates: `src/ipr_keyboard/web/templates/`
Static assets: `src/ipr_keyboard/web/static/` (SVG icons and illustrations go here)

New dashboard endpoints must use the `/api/` prefix. Evolve the existing server rather than replacing it.

## Design preferences

- plain-language user-facing text
- translated events before raw logs
- SVG assets in `src/ipr_keyboard/web/static/`
- vanilla HTML/CSS/JS — no build step required
- avoid heavy SSR/runtime web frameworks unless clearly justified
- prefer Server-Sent Events for live state updates

## Change preferences

- prefer incremental changes
- keep diffs reviewable
- update docs with implementation changes
- include testing notes in commits or PR summaries when appropriate