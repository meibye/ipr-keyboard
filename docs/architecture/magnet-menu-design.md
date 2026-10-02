# Magnet menu — analysis and design

How the device is operated from its single control, and why the timed gesture
ladder is being replaced by a menu on the OLED.

Current behaviour: `docs/hardware/gpio-wiring.md` (LED and ladder),
`docs/hardware/oled-display.md` (screens).

---

## 1. Why

The magnet is the only control.  Until now it selected actions by **duration**:
hold 3 s for the hotspot, 6 s to shut down, 10 s to switch mode, 15 s to delete
the Wi-Fi profiles, 20 s to cancel.  The display lists them and marks the armed
one, which helps, but the user still has to hold and count, and the list only
appears once the magnet is already on the switch.

Two things went wrong in practice:

- A factory reset was armed and released by accident while exploring the
  options.  The Wi-Fi profiles were deleted and the device left the network.
- Recovery then depended on the hotspot password, which existed only in the
  scrollback of the terminal that had run provisioning.

Both are consequences of the same design: a destructive action sits in the
middle of a timing ladder, selected by holding still rather than by choosing.

## 2. Requirements

1. Choosing an action must not depend on counting seconds.
2. Destructive actions must be confirmed by a deliberate second input.
3. The set of actions must be extensible (configuration, diagnostics) without
   making the interaction longer.
4. A device **without** a display must keep working exactly as it does today.
5. Production mode keeps the same functionality as development: the magnet is
   physical-access control either way, and removing options in production
   would make a locked-out device unrecoverable.
6. The panel's on-time must be configurable, and a tap must restart it.
7. Recovery credentials must be obtainable at the device, but must not sit on
   the screen for anyone to read.

## 3. Design

### 3.1 One hold opens a menu

Holding the magnet for **3 s** opens the menu; everything else becomes an item
in it.  The timing ladder is gone — on a device with a display.

| Input | Meaning in the menu |
|---|---|
| Tap (< 1 s) | next item, wrapping at the end |
| Hold ≥ 1.5 s, then release | activate the highlighted item |
| Nothing for 20 s | leave the menu, back to status |

The timings are generous because a magnet is slower than a button: the hand
moves away and back for every tap.  The LED shows a steady blue while the menu
is open, so a glance says "this device is in a menu"; the panel is what is
read.

### 3.2 No display, no menu

`OledManager.active` decides.  When the display is disabled, absent or broken,
the magnet keeps the timed ladder exactly as before — a menu that cannot be
read is not an interface.  This is also what keeps a Zero W without a panel
working, and it means the ladder's code and tests stay.

### 3.3 The menu

```
MENU
 ├ Hotspot  on/off        no confirmation
 ├ Display ▸
 │   ├ Timeout: 5 / 15 / 30 / 60 min
 │   └ Back
 ├ Recovery info          confirm (1 tap), limited reveals
 ├ Mode: to dev/prod      confirm (1 tap)
 ├ Shutdown               confirm (1 tap)
 ├ Factory reset          confirm (2 taps)
 └ Exit
```

Items render in the four-line compact layout the gesture list already uses:
the selected line is bold with a ▶ marker, the rest plain, and a list longer
than four lines scrolls so the selection is always visible.

### 3.4 Confirmation graded by consequence

| Class | Items | Confirmation |
|---|---|---|
| Harmless | Hotspot, Display timeout, Exit | none — acts at once |
| Disruptive | Mode, Shutdown | one tap within 10 s |
| Destructive | Factory reset | **two** taps within 10 s, counted on screen |

A timeout always cancels.  Before confirming, the panel says what the action
will do — the factory reset names what it deletes, which "Factory reset" alone
never did.

### 3.5 Recovery information

`Recovery info` shows the hotspot SSID and key, and the dashboard's initial
password when it still exists.  It is governed by two limits:

- **`RecoveryRevealLimit`** (config, default 3): how many times the
  credentials may be shown **per boot**.  Each reveal costs one and needs a
  confirming tap first.  At zero the item says so and does nothing.
- **Used once, gone for good**: when the setup portal records a successful
  login, the credentials are marked used in
  `/var/lib/ipr-keyboard/recovery_used` and are never shown again — the
  password has served its purpose and the screen stops being a place to read
  it.  Regenerating the hotspot secret clears the mark.

This keeps the property that mattered during the lockout: someone standing in
front of the device can always get back in, without the panel becoming a
permanent credentials display.

### 3.6 Display timeout

`OledDisplayTimeoutMinutes` ∈ {5, 15, 30, 60}, default **30**, chosen from the
Display menu and written back to `config.json`.  Any tap restarts the period.

Dimming is unchanged: the contrast still drops after five minutes continuously
on, which is what protects the panel.  A longer on-time therefore costs panel
lifetime but not legibility, and the LED is untouched — it keeps
`GpioLedIdleSeconds` and its existing behaviour.

## 4. Alternatives considered

- **Adding rungs to the ladder** (menu at 3 s, recover at 20 s).  Rejected: it
  makes the hold longer and leaves the destructive action selected by timing,
  which is the thing that failed.
- **Double-tap to open the menu.**  Rejected: with a magnet a reliable
  double-tap window is long enough to feel broken, and taps are the natural
  "next" input once inside.
- **Menu only in development mode.**  Rejected by requirement 5: a locked-out
  production device is exactly the one that needs recovery.

## 5. Files

| Area | Files |
|---|---|
| Menu | `src/ipr_keyboard/menu.py` (pure state machine), `gpio_monitor.py` (reed → menu), `oled/screens.py` (rendering) |
| Config | `config/manager.py`, `config.default.json` |
| Tests | `tests/test_menu.py`, `tests/test_gpio_monitor.py`, `tests/oled/test_screens.py` |
| Docs | this note, `docs/hardware/gpio-wiring.md`, `docs/hardware/oled-display.md`, both manuals |
