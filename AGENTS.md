# Agent guidance for this repository

## Purpose
This repository contains production software and associated operational and developer documentation.
Every change must preserve buildability, testability, maintainability, and documentation accuracy.

## Global working rules
- Read the relevant files before changing code.
- Prefer small, reviewable changes over broad rewrites.
- Do not change public behavior silently.
- Keep architecture boundaries intact.
- Do not introduce new dependencies unless justified.
- Do not edit generated files unless the task explicitly requires it.

## Required validation
Before concluding work, run the smallest relevant validation set:
- format
- lint
- unit tests
- targeted integration tests when behavior changed
- docs checks when public behavior, configuration, or workflows changed

## Documentation policy
Update documentation when any of the following changes:
- public APIs
- CLI commands or flags
- configuration schema or environment variables
- architecture or component responsibilities
- deployment or operational workflows
- user-visible behavior

Prefer targeted documentation edits over rewriting whole documents.

## Testing policy
For bug fixes:
- add or update a regression test where practical

For new features:
- add happy-path tests
- add at least one boundary or failure-path test when practical

## Security and safety
- Never commit secrets or credentials
- Treat authentication, authorization, encryption, and data handling changes as high risk
- Prefer least privilege in configs and tooling
- Flag any security-relevant uncertainty explicitly

## Review expectations
Summaries must include:
- what changed
- why it changed
- how it was validated
- which docs were updated
- remaining risks or follow-ups

## Skills to use
Use the most relevant skill when applicable:
- implement-feature
- add-tests
- review-pr
- refactor-safely
- update-docs-from-code
- prepare-release
- root-cause-analysis
- dependency-upgrade
- security-review
- design-rfc

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

### Existing baseline

The Flask server at `src/ipr_keyboard/web/server.py` is the starting point.
HTML templates live in `src/ipr_keyboard/web/templates/`.
SVG assets should go in `src/ipr_keyboard/web/static/`.

New dashboard API endpoints must use the `/api/` prefix as defined in the API contract.
Evolve the current server incrementally.

### Dashboard expectations

- keep the UI simple and image-first
- use plain-language labels
- show translated event messages before raw logs
- prefer SVG assets committed to `src/ipr_keyboard/web/static/`
- use vanilla HTML/CSS/JS — no build step required
- preserve a lightweight backend/frontend split
- avoid introducing a heavy server-side web runtime unless justified
- prefer Server-Sent Events for live updates

### Default implementation direction

Unless the codebase strongly suggests otherwise:

- keep Flask as the backend
- evolve the current web solution incrementally
- use stable `/api/` endpoints for UI state
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
- store them in `src/ipr_keyboard/web/static/`
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