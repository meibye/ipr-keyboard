# src/ipr_keyboard/web/

Flask web layer: the dashboard, its JSON API, the setup portal on the
hotspot, and a few legacy pages.

## Files

- `server.py`: app factory, login, the dashboard root and the legacy HTML pages
- `api.py`: `/api/` blueprint — the dashboard's JSON API.  **Every endpoint
  is documented in `docs/ui/api-contract.md`**; that file is the reference,
  not this one.
- `setup.py`, `setup_i18n.py`: the setup portal at `/setup/` (hotspot;
  English and Danish), with its own login
- `auth.py`: dashboard accounts in `users.json`, hashed
- `templates/dashboard.html`: the image-first single-page dashboard (primary UI)
- `templates/login.html`: dashboard login
- `templates/setup/`: the setup portal's pages
- `templates/index.html`, `status.html`, `config.html`, `logs.html`,
  `logs_select.html`, `pairing.html`: legacy pages
- `static/`: SVG icons and the device-flow illustration, `ipr.css`,
  `setup.css`, and `localtime.js` (shows every time in the viewer's time zone)

## Routes registered by `create_app()`

- `/` — the dashboard; `/login`, `/logout`; `/health` (JSON, no login)
- `/api/...` — see `docs/ui/api-contract.md`
- `/setup/...` — the setup portal
- `/status`, `/pairing/` — legacy HTML pages
- `/config/` and `/logs/` — answered by the `config` and `logs`
  blueprints (JSON config; the log file as text).  `server.py` also defines
  HTML pages at those two paths, but the blueprints are registered first and
  win, so those pages are not reachable.

Every route except `/health`, `/login`, `/logout`, `/api/auth/login` and
`/setup` needs a signed-in session.

## Implementation Notes

- Live state reaches the dashboard by Server-Sent Events (`/api/stream`): a
  `status_update` every `StatusIntervalSeconds`, every second while a send
  is on screen.
- The status builders read the Bluetooth link from sysfs and cache
  `bluetoothctl` / `systemctl` answers (see the API contract), so an open
  dashboard costs the device almost nothing per tick.
- Events are translated from the journal (`journalctl -o short-iso`) on
  request; each carries the journal entry's own time.
- Times leave the server as instants (UTC or with an offset) and are shown
  in the viewer's time zone by `static/localtime.js`.
- Privileged actions (reboot, shutdown, hotspot, service restarts, network,
  date and time) go through root helpers with narrow sudoers entries —
  `ipr_hotspot_ctl.sh`, `ipr_mode_ctl.sh`, `ipr_net_apply.sh`.
