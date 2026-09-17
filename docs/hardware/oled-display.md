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

The 16 yellow rows are the **header**: one state word, plus a `DEV` badge in
development mode.  The 48 blue rows are the **body**: three short lines with
an icon column, or a progress bar.

| Header | When | Body |
|---|---|---|
| `STARTING…` | application starting (~35 s after power-on) | Services / Bluetooth / Dashboard checklist |
| `READY` | magnet tap, or a status change | PC name (or `Waiting for PC…`), pen (`Pen ready` / `Plug in the pen` / `Pen busy (mounting)`), Wi-Fi name and IP |
| `PROBLEM` | as `READY`, when something is wrong | the failing line gets a ✗: `Service down: …`, `USB port off — reboot`, `No Wi-Fi — hold 3 s` |
| `SENDING…` | a scan is being typed | sweeping bar, `→ <PC>`, `N characters` |
| `SENT ✓` | 10 s after a send (`OledSendHoldSeconds`) | character count, PC and time, running total |
| `SEND FAILED` | 10 s after a failed send | reason, `Text kept on pen` |
| `HOLD…` / `RELEASE → HOTSPOT` / `… SHUTDOWN` / `… MODE` / `… RESET` / `CANCELLED` | magnet held | the gesture list with the armed action marked ▶ |
| `HOTSPOT…` / `HOTSPOT FAILED` | hotspot starting/stopping, or the request failed | |
| `SETUP MODE` | hotspot up (stays on) | `Wi-Fi <ssid>`, `Open 10.42.0.1/setup`, `Hold 3 s to stop` |
| `MODE: DEVELOPMENT` / `MODE: PRODUCTION` | 3 s after a mode toggle | ports open / closed |
| `SHUTTING DOWN` | after the 6 s gesture or a dashboard shutdown | `Wait for the LED to go off, then unplug` — the panel goes dark at the same moment as the LED |
| `RESETTING…` | after the 15 s gesture | |
| *(dark)* | idle | nothing — tap the magnet |

A line wider than the panel (a long network name, host name or IP) is never
cut: it rolls slowly to the left, pauses when the end is in view, and starts
over.  Lines that fit never move.

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
| `/etc/default/ipr-oled` | — | bus/address for the halt script |
| `ipr-led-halt.sh` (updated) | `/usr/local/sbin/` | also sends `0xAE` (display off) at the end of a shutdown |
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
| Frame time high on a Zero W (`OledMarqueeFps` rolling stutters) | I²C still at 100 kHz — the `config.txt` block needs a reboot; set `OledMarqueeFps: 6` |

Validation: `sudo bash scripts/headless/test_provision.sh --auto` (phase N)
and the interactive `sudo bash scripts/headless/test_oled.sh`.
