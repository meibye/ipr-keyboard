# Repository instructions for GitHub Copilot

## Purpose

This repository contains a Raspberry Pi based BLE HID keyboard / pen bridge solution.
AI-generated changes must preserve lightweight operation and fit the realities of Raspberry Pi Zero 2 W.

## High-level guidance

- Prefer incremental improvement over large rewrites.
- Preserve the current Python-based backend approach where practical.
- Avoid introducing heavy runtime stacks unless clearly justified.
- Prefer simple, maintainable solutions that are easy to debug on-device.
- Keep runtime dependencies small.

## Web dashboard guidance

When working on the web UI:

- treat `docs/ui/dashboard-spec.md` as the product specification
- treat `docs/ui/wireframes.md` as the layout guide
- treat `docs/ui/user-states.md` as the UI state model
- treat `docs/ui/api-contract.md` as the backend/frontend contract

### Existing baseline

The dashboard already has a Flask server at `src/ipr_keyboard/web/server.py` with HTML templates in `src/ipr_keyboard/web/templates/`.
Evolve this incrementally rather than replacing it.

New dashboard API endpoints must be added under the `/api/` prefix as defined in the API contract.

### UI requirements

- image-first and icon-heavy
- understandable to non-technical users
- plain-language user-facing text
- technical logs are secondary to translated events
- touch-friendly and responsive
- lightweight enough for Raspberry Pi Zero 2 W

### Asset requirements

- prefer SVG for UI illustrations and icons
- store SVG assets in `src/ipr_keyboard/web/static/`
- commit generated assets in-repo
- keep assets simple, flat, and readable
- avoid large raster image files unless truly necessary

### Architecture preferences

- the backend is Flask — keep it that way unless there is a strong reason to change
- use vanilla HTML/CSS/JS for the frontend — no build step required
- prefer static frontend assets served by the existing Flask server or nginx
- avoid a persistent heavy SSR runtime such as a full Next.js server
- prefer Server-Sent Events for live state updates; fall back to polling if needed

## Safety and actions

Dangerous actions such as reboot and shutdown must:

- require explicit confirmation
- be visually separated in the UI
- use backend-controlled actions rather than direct frontend shell behavior

## Documentation

When changing functionality, also update relevant documentation:

- deployment notes
- configuration notes
- UI docs
- API docs if contract changes

## Quality bar

Before finalizing a change:

- keep the diff focused
- avoid unnecessary architecture churn
- prefer clear file structure
- add or update tests where practical
- include testing notes in the PR summary