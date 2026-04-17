# Agent guidance for this repository

## Project context

This repository contains a Raspberry Pi based BLE HID keyboard / pen bridge project.
The device is resource-constrained and is expected to run reliably on Raspberry Pi Zero 2 W.

## Core engineering priorities

1. reliability on-device
2. low runtime overhead
3. simple deployment and debugging
4. incremental change over unnecessary rewrites
5. clear repository-local documentation

## When working on the web dashboard

Read these files first:

- `docs/ui/dashboard-spec.md`
- `docs/ui/wireframes.md`
- `docs/ui/user-states.md`
- `docs/ui/api-contract.md`

### Dashboard expectations

- keep the UI simple and image-first
- use plain-language labels
- show translated event messages before raw logs
- prefer SVG assets committed to the repository
- preserve a lightweight backend/frontend split
- avoid introducing a heavy server-side web runtime unless justified

### Default implementation direction

Unless the codebase strongly suggests otherwise:

- keep Python as the backend/control layer
- evolve the current web solution incrementally
- use stable API endpoints for UI state
- keep browser-side logic straightforward

## Change management

For larger changes:

- first update or confirm repository guidance and docs
- then implement the feature
- keep PRs reviewable
- describe architecture decisions in the PR summary

## Generated assets

If images or icons are needed:

- generate them as SVG where possible
- store them in a predictable frontend asset folder
- keep the visual style simple and consistent
- avoid oversized or decorative assets

## Testing expectations

At minimum:

- verify key flows manually
- verify API behavior for changed endpoints
- describe how the change was tested

## Prohibited tendencies

Avoid:

- large speculative rewrites
- unnecessary framework churn
- introducing heavyweight UI infrastructure without clear need
- exposing raw technical state directly as primary UI messaging