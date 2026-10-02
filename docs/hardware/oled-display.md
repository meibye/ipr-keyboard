# OLED Status Display — SSD1306 128×64 over I²C

Hardware and behaviour guide for the small OLED next to the status LED.
The reasoning (power, when the panel is on, the LED's role) is in
`docs/architecture/oled-display-design.md`; the LED itself is documented in
`gpio-wiring.md`.

The display is optional.  A device without one — or with a broken one —
logs `OLED display disabled — …` once and behaves exactly as before.

---

## Components

| Component | Value / type | Notes |
|-----------|-------------|-------|
| OLED module | 0.96" 128 × 64, SSD1306 controller, I²C | Four pins: GND, VCC, SCL, SDA.  Top 16 rows yellow, lower 48 rows blue on the common two-colour panel |
| Supply | 3.3 V | From the Pi's pin 1.  Draws ≈ 5–8 mA with a text screen, < 10 µA asleep |
| Address | `0x3C` (default) | A solder jumper on the module selects `0x3D`; then set `"OledI2cAddress": 61` |

---

## Pin assignments (BCM numbering)

| Signal | BCM | Physical pin | Notes |
|--------|-----|-------------|-------|
| VCC | — | Pin 1 | 3.3 V — never 5 V |
| GND | — | Pin 6 | or any other GND (9, 14, 20, 25) |
| SDA | **GPIO 2** | Pin 3 | Pi has 1.8 kΩ pull-ups on board |
| SCL | **GPIO 3** | Pin 5 | |

GPIO 2/3 were reserved for I²C from the start (see `gpio-wiring.md`); the
LED and reed switch pins are untouched.

```
Pin 1  3V3 ──────────── VCC ┐
Pin 3  GPIO 2 (SDA) ─── SDA │  SSD1306
Pin 5  GPIO 3 (SCL) ─── SCL │  128 × 64
Pin 6  GND ──────────── GND ┘
```

Check the wiring with `i2cdetect -y 1`: the panel appears as `3c` (or `UU`
while the application holds it).

---

## Screen map

The 16 yellow rows are the **header**: one state word, plus the **mode
badge** — `DEV` or `PROD` — in the top right corner of every screen.  The
48 blue rows are the **body**: three short lines with an icon column, or a
progress bar; screens that need four lines (the boot checklist, the magnet
activity list) use a slightly smaller face.

The mode is on the display, always visible, because the status LED has no
pattern for it — see `gpio-wiring.md`.

| Header | When | Body |
|---|---|---|
| `STARTING…` | from a few seconds after power-on (`ipr-oled-boot.service`), then the application | boot checklist: System / Network / Bluetooth / Application, continued by the application as Services / Network / Bluetooth / Dashboard |
| `READY` | magnet tap, or a status change | PC name (or `Waiting for PC…`), pen (`Pen ready` / `Plug in the pen` / `Pen busy (mounting)`), Wi-Fi name and IP |
| `PROBLEM` | as `READY`, when something is wrong | the failing line gets a ✗: `Service down: …`, `USB port off — reboot`, `No Wi-Fi — hold 3 s` |
| `SENDING…` | a scan is being typed | sweeping bar, `→ <PC>`, `N characters` |
| `SENT ✓` | 10 s after a send (`OledSendHoldSeconds`) | character count, PC and time, running total |
| `SEND FAILED` | 10 s after a failed send | reason, `Text kept on pen` |
| `HOLD…` / `RELEASE →` / `CANCELLED` | magnet held | one activity per line; the selected one is **bold** and marked ▶, and activities already passed disappear so the list rolls up |
| `HOTSPOT…` / `HOTSPOT FAILED` | hotspot starting/stopping, or the request failed | |
| `SETUP MODE` | hotspot up (stays on) | `Wi-Fi <ssid>`, `Open 10.42.0.1/setup`, `Hold 3 s to stop` |
| `MODE: DEV` / `MODE: PROD` | 3 s after a mode toggle | ports open / closed |
| `SHUTTING DOWN` | after the 6 s gesture or a dashboard shutdown | `Wait for the LED to go off, then unplug` — the panel goes dark at the same moment as the LED |
| `RESETTING…` | after the 15 s gesture | |
| *(dark)* | idle | nothing — tap the magnet |

A line wider than the panel (a long network name, host name or IP) is never
cut: it rolls slowly to the left, pauses when the end is in view, and starts
over.  Lines that fit never move.

### The magnet menu

On a device with a working panel the magnet opens a **menu** instead of the
timed activity list: hold 3 s, then tap to move and hold again to choose.  The
list below is what the ladder does on a device **without** a display, where a
menu could not be read — see `docs/architecture/magnet-menu-design.md`.

| Input | In the menu |
|---|---|
| Tap (< 1 s) | next item, wrapping at the end |
| Hold ≥ 1.5 s, then release | activate the highlighted item |
| Nothing for 20 s | leave the menu |

```
MENU
 ├ Hotspot on / off        acts at once
 ├ Display ▸ Timeout: 5 / 15 / 30 / 60 min
 ├ Recovery info           one tap to confirm, limited reveals
 ├ Mode: to dev / prod     one tap to confirm
 ├ Shutdown                one tap to confirm
 ├ Factory reset           TWO taps to confirm
 └ Exit
```

The LED is steady blue while the menu is open.  Before any confirmation the
panel says what the action does — the factory reset names what it deletes —
and a confirmation that times out always cancels.

**Recovery info** shows the hotspot name and key for a device that has lost
its Wi-Fi settings.  It is limited: `RecoveryRevealLimit` (default 3) reveals
per boot, each after a confirming tap, and **none at all once the credentials
have been used** — the setup portal records that, and only a regenerated key
makes them showable again.

**Display ▸ Timeout** sets how long the panel stays on after the last magnet
contact: 5, 15, 30 (default) or 60 minutes, written back to `config.json`.
Any tap starts a fresh period.  Dimming is unchanged — the contrast still
drops after five minutes on, which is what protects the panel.

### The activity list while the magnet is held (no display)

The magnet is the only control on the device, so the panel spells the hold
ladder out and narrows it down as the magnet stays on:

| Held | Header | Body |
|---|---|---|
| < 3 s | `HOLD…` | all four activities, one per line: `3 s Hotspot`, `6 s Shutdown`, `10 s To development` (or `To production`), `15 s Factory reset` |
| 3–6 s | `RELEASE →` | the same list, `3 s Hotspot` bold and marked ▶ |
| 6–10 s | `RELEASE →` | `Hotspot` is gone; `6 s Shutdown` bold and marked |
| 10–15 s | `RELEASE →` | only the mode switch (bold) and the factory reset are left |
| 15–20 s | `RELEASE →` | only `15 s Factory reset`, bold and marked |
| ≥ 20 s | `CANCELLED` | `Nothing will happen` |

The header only says that a release acts — the bold line says what.  Spelling
the activity out in the header made it too wide for the band beside the mode
badge, so it rolled while the user was counting seconds.

Taking the magnet off does whatever the bold line says.  The LED blinks
white three times the moment the magnet lands, so a press registers even
before the first threshold.

### Boot screen

`ipr-oled-boot.service` (started by systemd as soon as the local filesystems
and the i²c module are up — about 14 s into a Zero 2 W boot, long before the
application) draws `STARTING…` and ticks off System,
Network, Bluetooth and Application as each comes up.  It hands the panel to
`ipr_keyboard.service`, which continues with its own checklist, and it never
blanks the panel — so a boot that hangs leaves its last frame on screen.
Journal: `journalctl -u ipr-oled-boot.service -b`.

### When the panel is on

The display follows the LED phase, so it is on exactly when someone is
looking: during boot, for `GpioLedIdleSeconds` (30 s) after a magnet tap or
any status change (PC connected/disconnected, pen plugged/unplugged, Wi-Fi
up/down, a service failing), while the magnet is held, while the hotspot is
up, during a send and 10 s after, and during shutdown/reset.  Otherwise it
sleeps — for OLED lifetime and for a quiet device, not for power (see the
design note).  After five minutes continuously on (a long setup session) the
contrast is lowered.

---

## Software configuration

```json
{
  "OledEnabled": true,
  "OledI2cBus": 1,
  "OledI2cAddress": 60,
  "OledContrast": 128,
  "OledRotate": 0,
  "OledSendHoldSeconds": 10,
  "OledMarqueeFps": 8
}
```

| Key | Meaning |
|---|---|
| `OledEnabled` | `false` disables the display without touching the wiring |
| `OledI2cBus`, `OledI2cAddress` | `/dev/i2c-1`, `0x3C` (decimal 60 in JSON; 61 for `0x3D`) |
| `OledContrast` | 0–255 |
| `OledRotate` | `0` or `180` (module mounted upside down) |
| `OledSendHoldSeconds` | how long `SENT ✓` / `SEND FAILED` stay on |
| `OledDisplayTimeoutMinutes` | how long the panel stays on after the last magnet contact: 5, 15, 30 (default) or 60.  Set from the magnet menu |
| `RecoveryRevealLimit` | how many times the recovery credentials may be shown per boot (default 3) |
| `OledMarqueeFps` | redraw rate while a long line rolls; `6` on a Zero W |

The idle window is shared with the LED (`GpioLedIdleSeconds`).  These keys
are not exposed in the dashboard's configuration page.

### What the display needs on the device

Installed by `scripts/headless/install_oled_support.sh` (called from
`provision/04_enable_services.sh` and `scripts/deploy/deploy_full_update.sh`
after `install_gpio_support.sh`; safe to re-run):

| Piece | Where | Purpose |
|---|---|---|
| `dtparam=i2c_arm=on`, `dtparam=i2c_arm_baudrate=400000` | `/boot/firmware/config.txt` (managed block) | I²C bus 1; 400 kHz makes a full frame ≈ 25 ms instead of ≈ 90 ms |
| `i2c-dev` | `/etc/modules-load.d/ipr-oled.conf` | `/dev/i2c-1` at boot |
| `python3-pil`, `fonts-dejavu-core`, `i2c-tools` | apt | Pillow rendering, the display font, `i2cdetect`/`i2cset` |
| app user in group `i2c` | `usermod -aG i2c` | opens `/dev/i2c-1` (`root:i2c 0660`) — no sudo, no sudoers entry |
| `/etc/default/ipr-oled` | — | bus, address, rotation and `REPO_DIR` for the halt script and the boot screen |
| `ipr-led-halt.sh` (updated) | `/usr/local/sbin/` | also sends `0xAE` (display off) at the end of a shutdown |
| `ipr-oled-boot.py` + `ipr-oled-boot.service` | `/usr/local/sbin/`, `/etc/systemd/system/` | the boot screen; `REPO_DIR` in `/etc/default/ipr-oled` tells it where the driver lives |
| `11-oled-boot.conf` | `/etc/systemd/system/ipr_keyboard.service.d/` | stops the boot screen so the application can claim the panel |
| `include-system-site-packages = true` | `.venv/pyvenv.cfg` | makes the Debian Pillow visible to the app |

Pillow comes from Debian because there is no PyPI wheel for the ARMv6 Zero W;
`luma.oled` is not used — the SSD1306 driver is ~100 lines in
`src/ipr_keyboard/oled/ssd1306.py` on top of `/dev/i2c-1` with the standard
library.

The venv must run the **system** Python for Debian packages to be visible.
On a production image (`requires-python` satisfied by the OS) `uv venv` does
that.  On a development board with an older system Python, uv installs its
own interpreter and the installer prints a hint; there, `uv pip install
pillow` into the venv is the pragmatic fix.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| Journal: `OLED display disabled — /dev/i2c-1 missing` | `dtparam=i2c_arm=on` in `config.txt` needs a reboot; `lsmod \| grep i2c_dev` |
| Journal: `nothing answers at 0x3C` | `i2cdetect -y 1` — no `3c`: wiring (SDA/SCL swapped is the classic), 3.3 V, or the address jumper (`3d` → set `OledI2cAddress: 61`).  `Permission denied` in the journal: the app user is not in group `i2c`, or the service was not restarted after being added |
| Journal: `Pillow not importable` | `python3-pil` installed?  `.venv/pyvenv.cfg` has `include-system-site-packages = true`?  Venv Python = system Python? |
| Panel lights but shows garbage / offset by a few columns | the module is an SH1106, not an SSD1306 — not supported |
| Panel upside down | `"OledRotate": 180` |
| Nothing ever shows although the journal says `OLED display started` | the panel sleeps when idle — tap the magnet; check `OledEnabled` |
| Panel dark for the first ~35 s of a boot | `systemctl is-enabled ipr-oled-boot.service`; `journalctl -u ipr-oled-boot.service -b` names the reason (no `REPO_DIR` in `/etc/default/ipr-oled`, Pillow missing, nothing on the bus).  Re-run `install_oled_support.sh` |
| Display says `Plug in the pen` although the pen is plugged in | Most often the pen simply did not re-attach after a reboot — unplug it and plug it in again.  The pen is an MTP device and does not re-present itself to a host that rebooted under it.  Confirm with `journalctl -k -b \| grep "usb 1-1"`: no line at all means nothing ever attached (see `docs/operations/irispen-automount.md`) |
| The mode badge says `PROD` although SSH works | the badge is read from `/var/lib/ipr-keyboard/mode`; compare with `sudo ipr_mode_ctl.sh status` |
| Frame time high on a Zero W (`OledMarqueeFps` rolling stutters) | I²C still at 100 kHz — the `config.txt` block needs a reboot; set `OledMarqueeFps: 6` |

Validation: `sudo bash scripts/headless/test_provision.sh --auto` (phase N)
and the interactive `sudo bash scripts/headless/test_oled.sh`.
