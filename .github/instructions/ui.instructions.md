---
applyTo: "docs/ui/**,web/**,frontend/**,templates/**,static/**,src/**"
---

# UI-specific Copilot instructions

Use these instructions for dashboard, frontend, templates, and web asset work.

## Product intent

Build a lightweight, image-first dashboard for the Raspberry Pi device.

## UI rules

- prefer large cards, icons, and short labels
- use plain-language wording
- treat translated event messages as primary
- keep raw logs secondary and collapsible
- make states understandable at a glance
- keep interactions touch-friendly

## Performance rules

- optimize for Raspberry Pi Zero 2 W
- keep JavaScript and CSS small
- prefer SVG assets
- avoid heavy frontend dependencies unless justified

## Architecture rules

- prefer static or lightly dynamic frontend assets
- do not introduce a full heavy SSR runtime by default
- use backend APIs for authoritative state
- keep frontend logic simple and presentational where possible

## Safety rules

- reboot and shutdown must require confirmation
- destructive or disruptive actions must be clearly separated in the UI