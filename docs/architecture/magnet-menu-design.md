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

Holding the magnet for **1.2 s** opens the menu; everything else becomes an
item in it.  The timing ladder is gone — on a device with a display.  (It was
3 s when this was written; the hold was shortened once the menu replaced the
ladder, because nothing destructive sits behind it any more.)

| Input | Meaning in the menu |
|---|---|
| Tap (released before 1 s) | next item, wrapping at the end |
| Hold past 1 s | activate the highlighted item, **at once** |
| Nothing for 20 s | leave the menu, back to status |

Holding 1.2 s opens the menu and 1 s chooses an item, so "a hold" means one
thing everywhere.  Both show a **progress bar** while the magnet is on: with a
single control and no labels, "how long do I hold?" is otherwise guesswork, and
it was the first thing a user asked.

### 3.1a Telling a tap from a hold

Both of these were reported from the device: *"the back and exit options are
hard to select — it often is interpreted as a tap and moves to the next
option"*, and *"a tap is often interpreted as a hold"*.  Failing in **both**
directions is not a badly placed threshold; it is contact noise, and there were
two causes.

**The press was classified on release.**  The user had to judge the duration
with no confirmation that it had been long enough, so a hold meant as "choose
this" was routinely let go a fraction early and arrived as a tap — which
stepped past the item they were trying to pick.  `Back` and `Exit` suffered
most, because stepping past them wraps the whole list.

The threshold now fires **while the magnet is still down**: the item activates
the instant the bar fills, and the release that follows is ignored.  The panel
answers under your hand, so the timing is learned in one go instead of guessed
every time.

**A hand-held magnet wobbles.**  The reed is sampled at 20 Hz with no
filtering, so a wobble appeared as the contact opening for a sample or two.
Taken literally that ends the press: one deliberate hold arrived as two taps,
and a tap whose release bounced arrived as a hold.

`_ReedFilter` in `gpio_monitor.py` applies two rules:

1. An open is only believed once it has lasted `REED_OPEN_DEBOUNCE_SECS`
   (150 ms), so a wobble no longer ends the press.
2. **The hold clock stops at the first sign of that open.**  Without this the
   first rule would make things worse: a magnet lifted at 0.9 s would keep
   counting during the 150 ms the filter spent deciding, and sail past a 1 s
   threshold — turning every late tap into an accidental selection.

Asymmetric on purpose: a *close* is believed immediately, so the device still
feels instant, and only letting go costs 150 ms.

The LED is deliberately **not** repurposed.  Blue is documented as "the
hotspot is up" in both manuals, and giving it a second meaning made the device
ambiguous at a glance; while the menu is open the LED keeps showing the
device's status and the panel says the rest.

### 3.2 No display, no menu

`OledManager.active` decides.  When the display is disabled, absent or broken,
the magnet keeps the timed ladder exactly as before — a menu that cannot be
read is not an interface.  This is also what keeps a Zero W without a panel
working, and it means the ladder's code and tests stay.

### 3.3 The menu

```
MENU
 ├ Hotspot: to on / to off       acts at once
 ├ Display ▸
 │   ├ Display timeout ▸  5 / 15 / 30 / 60 min   (header SCREEN OFF)
 │   └ Menu timeout ▸     20 s / 1 / 2 / 5 min    (header MENU CLOSES)
 ├ Recovery info                 one tap to confirm, limited reveals
 ├ Power ▸   Shut down / Restart one tap to confirm
 ├ System ▸
 │   ├ Mode: to dev / prod      one tap to confirm
 │   └ Factory reset            TWO taps to confirm
 └ Exit
```

Each list ends in `Back` where it is a submenu.  The rarely used,
administrator-only actions sit under **System** so nothing reached for day to
day shares a screen with a factory reset; **Recovery info** stays at the top
level, because burying it would cost exactly when a locked-out device needs
it.

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
