# Claude project context

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

## Design preferences

- plain-language user-facing text
- translated events before raw logs
- SVG assets preferred
- avoid heavy SSR/runtime web frameworks unless clearly justified
- preserve the existing Python-oriented architecture where practical

## Change preferences

- prefer incremental changes
- keep diffs reviewable
- update docs with implementation changes
- include testing notes in commits or PR summaries when appropriate