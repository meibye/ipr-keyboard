# PR 2 Documentation Audit

Repository Markdown files reviewed for impact from the upcoming web dashboard implementation (PR 2).

Scope: all Markdown files outside `docs/ui/` that describe the web UI, Flask pages, setup,
deployment, architecture, troubleshooting, or user workflow.

---

## Must update in PR 2

### `src/ipr_keyboard/web/README.md`

Directly documents the web layer: endpoints, templates, and implementation notes.
PR 2 adds `/api/` routes, new dashboard templates, and static SVG assets.
This file will be immediately stale without an update that reflects the new endpoints,
templates, and asset location.

### `ARCHITECTURE.md`

The canonical architecture reference for the whole repository (agents and developers treat it as
authoritative). Section 3 (Source Module Map) lists `web/server.py` and current templates.
The runtime topology comment "In parallel, `src/ipr_keyboard/web/server.py` serves Flask APIs
and status endpoints" must be extended to cover the new dashboard and `/api/` prefix pattern.
Keeping this accurate matters because agents use it as a decision rule before extending modules.

---

## Should update in PR 2

### `src/ipr_keyboard/README.md`

Package module map that lists every source file and its role, including the web layer
(`web/server.py`, `web/pairing_routes.py`, `web/templates/pairing_wizard.html`).
PR 2 adds new route modules, dashboard template(s), and static assets under `web/static/`.
A brief update to the table and notes keeps this doc useful as a code-navigation aid.

### `README.md`

The top-level entry point. The "Runtime Flow" section enumerates the current Flask endpoints
(`/health`, `/status`, `/config/`, `/logs/`, `/pairing`).
After PR 2 lands, the dashboard is the recommended way to interact with the device.
The verification step and the directory guide can each gain a one-line reference to the
dashboard and the new `/api/` endpoints without requiring a full rewrite.

---

## Optional follow-up (PR 3 or later)

### `TESTING_PLAN.md`

Lists current web test files. PR 2 is expected to add tests for the new `/api/` endpoints
(e.g., status, events, config, actions, stream). The test inventory should be updated when
those test files are written. If they land in PR 2, update here too; otherwise defer to PR 3.

### `DEVICE_BRINGUP.md`

Verification checklist references `curl http://localhost:8080/health` as the web smoke test.
After PR 2 a browser check of the dashboard URL (`http://<device-ip>:8080/`) is a natural
addition to manual bring-up verification. Not blocking, but a useful follow-up touch.

### `DEVELOPMENT_WORKFLOW.md`

Lists `dev_run_webserver.sh` and related development commands.
If PR 2 adds new developer steps (e.g., running static asset generation or a specific dashboard
test command), this file should be updated. If the workflow is unchanged, no edit is needed.

---

## No change needed

| File | Reason |
|---|---|
| `BLUETOOTH_PAIRING.md` | BLE command-line pairing flow is unchanged by the dashboard. |
| `SERVICES.md` | Service units are unchanged by PR 2; no new services are introduced. |
| `PAIRING_FIX_SUMMARY.md` | Historical document, not living documentation. |
| `SCRIPT_EVALUATION.md` | Script inventory; web dashboard is not a script. |
| `tests/README.md` | Only needs updating when new test files are added (coordinate with `TESTING_PLAN.md`). |
| `provision/README.md` | Provisioning steps are unchanged by PR 2. |
| `scripts/*/README.md` | Script-specific docs; no web dashboard relevance. |
| `docs/copilot/*.md` | Agent playbooks focused on BLE and diagnostics; separate concern. |
| `.github/prompts/copilot/*.md` | Same: separate agent prompts for BLE/diagnostics. |

---

## Recommended update scope for PR 2

Land these four updates alongside the dashboard implementation:

1. `src/ipr_keyboard/web/README.md` — update endpoint list, add new templates and static assets.
2. `ARCHITECTURE.md` — extend Source Module Map and runtime topology note for the dashboard.
3. `src/ipr_keyboard/README.md` — extend package table for new web files.
4. `README.md` — brief note on dashboard in Runtime Flow and directory guide.

Keeping these four in PR 2 ensures that the authoritative docs remain consistent with the code
immediately after merge. Agents and developers depend on `ARCHITECTURE.md` and the web README
as navigation anchors; letting those go stale creates drift.

---

## PR 3 recommendation

A separate docs-only PR 3 is advisable if:

- `TESTING_PLAN.md`, `DEVICE_BRINGUP.md`, or `DEVELOPMENT_WORKFLOW.md` are not ready to update
  by the time PR 2 is ready to merge, or
- additional follow-up notes (e.g., nginx serving notes, dashboard screenshot, link to
  deployment guide update) accumulate after the dashboard is live and verified.

PR 3 should not block PR 2. The four "must / should update" files above are sufficient to keep
the repository coherent at merge time.
