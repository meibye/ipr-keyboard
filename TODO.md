# TODO

Planned feature changes and new features.  One section per item: what and
why, the constraints that matter, and where in the code it lands.  Move an
item out of this file once it is done (the commit and the docs then carry
it).

---

## 1. A secret code to leave production mode

**What.**  Switching the device from production to development mode must
require a short secret code entered with the magnet, not just a menu choice.
Development mode opens SSH and the dashboard on the home network
(`docs/operations/network-modes.md`), so today anyone holding a magnet can
expose the device.  Development → production stays free: closing ports needs
no secret.

**How it is entered.**  A tapping sequence, e.g. short and long taps like
Morse code.  The admin sees (and can regenerate) the code in the dashboard,
under Settings; the panel never shows it.

**Constraints.**
- Short: the magnet is slow and tiring to operate.  Aim for something like
  4–6 symbols — enough that guessing at the device is not practical, few
  enough to enter in well under half a minute.
- Unambiguous: short vs. long must be easy to tell apart by hand, with the
  panel (and LED) acknowledging each symbol as it is entered.  The menu
  already distinguishes taps from holds while the magnet is down
  (`docs/architecture/magnet-menu-design.md`, 3.1a) — reuse that, do not
  invent a second timing model.
- A wrong code does nothing but say so; after a few wrong attempts, wait
  before the next one, so the code cannot be found by trying.
- Recovery must not get worse: a device whose admin has lost the code must
  still be recoverable — e.g. through the hotspot's setup portal, which
  already needs the hotspot key.  Decide this before building.
- A device without a display (hold-time ladder, 10 s = mode) needs the same
  protection, or that path to development mode is closed.

**Where.**
- `src/ipr_keyboard/menu.py` — *System ▸ Mode: to development* asks for the
  code instead of one confirming tap.
- `src/ipr_keyboard/gpio_monitor.py` — the ladder's 10 s mode toggle.
- `scripts/headless/ipr_mode_ctl.sh` — the root helper stays as it is; the
  check belongs in the application, before the helper is called.
- Dashboard: Settings shows and regenerates the code (`/api/` endpoint,
  admin only); store it hashed, next to the other application state.
- Docs: network-modes, magnet-menu-design, the hotspot user guide, both
  manuals, the release checklist (a Gate 3 line for the code).
