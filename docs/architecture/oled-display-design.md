# OLED status display — analysis and design

Date: 16 September 2026.  Applies to the Pi Zero 2 W and the Pi Zero W.

An SSD1306-compatible 0.96" OLED (128 × 64, I²C address `0x3C` on bus 1, top
16 pixel rows yellow, lower 48 rows blue) is added next to the RGB status
LED.  This note records why the display is used the way it is; the wiring
and user-facing screens are documented in `docs/hardware/oled-display.md`
and in the two manuals under `docs/manuals/`.

---

## 1. Hardware verified

| Parameter | Result |
|---|---|
| Interface | I²C, bus 1 (`/dev/i2c-1`, GPIO 2 SDA / GPIO 3 SCL, pins 3 / 5) |
| Address | `0x3C` (`i2cdetect -y 1`) |
| Controller | SSD1306-compatible (draws to the edges; SH1106 offset not needed) |
| Resolution | 128 × 64, colour split at row 16 (yellow above, blue below) |
| Supply | 3.3 V from pin 1 |

## 2. Requirements

1. Respect the platform: single-core ARMv6 Zero W, no build step, no PyPI
   wheel without an ARMv6 fallback (`AGENTS.md`), small diffs.
2. The display must never be required: a device without one, or with a
   broken one, behaves exactly as before.
3. Bluetooth, MTP and HID code do not draw on the display.  They report
   state; a display component renders it.
4. The LED's documented behaviour (gestures, colours, boot and halt
   phases) is unchanged.

## 3. Evaluation 1 — power, and when the display is on

The device is powered from a PC USB port, so power was the first concern.

| Consumer | Typical draw |
|---|---|
| SSD1306, every pixel lit, max contrast | ≈ 20 mA |
| SSD1306, a text status screen (~15 % pixels) | ≈ 5–8 mA |
| SSD1306, display off (`0xAE`) | < 10 µA |
| Pi Zero 2 W idle / with Wi-Fi + BT traffic | ≈ 100–120 mA / more |
| Pi Zero W idle | ≈ 80–100 mA |
| PC USB 2.0 port budget (USB 3: 900 mA) | 500 mA |

**Power is not a constraint.**  A lit display is under 10 % of the Pi's own
draw and nowhere near the port budget, so it cannot cause a brown-out.

What does argue for limiting the on-time:

1. **Burn-in.**  A static header lit around the clock ghosts visibly on these
   panels within months, and brightness halves after roughly 10 000 hours.
2. **CPU on the Zero W.**  A full frame is 1 KB over I²C: ≈ 90 ms at the
   default 100 kHz, ≈ 25 ms at 400 kHz.  Provisioning sets
   `dtparam=i2c_arm_baudrate=400000`; the manager only redraws when the
   rendered content changes (or a long line is rolling, § 4.4).
3. **Consistency.**  The LED is already off when idle.  "Quiet until you look
   at it — tap the magnet" is the established mental model.

The display therefore follows the LED phase, which is the single source of
truth for "is someone looking":

| Situation | Display |
|---|---|
| Boot (`Phase.BOOT`) | on — "Starting…" checklist |
| Magnet tap / status window (`Phase.STATUS`) | on for `GpioLedIdleSeconds`, same window as the LED |
| Magnet held (arming) | on — gesture help with the armed action highlighted |
| Hotspot up (`Phase.HOTSPOT_ON`) | on: SSID and URL; contrast lowered after 5 min |
| Send in progress / just finished / failed | on during the send and `OledSendHoldSeconds` after |
| Status change (BT, pen, Wi-Fi, service failure) | wakes for the status window (edge-triggered) |
| Shutdown / reset / mode-confirm phases | on with instruction text |
| Idle | panel off (`0xAE`) |

Errors are not kept on screen permanently (burn-in).  They wake the screen
once when they appear; a magnet tap shows them again, and the LED's red is
still there in the status window.

## 4. Evaluation 2 — what to show

### 4.1 Layout

The 16 yellow rows are a **header**: one big state word on the left, a small
badge on the right (`DEV` in development mode).  The 48 blue rows are the
**body**: up to three 12-px lines with a fixed 10-px icon column, or a
progress bar.  Text is plain language and mirrors the dashboard labels in
`docs/ui/user-states.md`.

### 4.2 Screens

```
Boot                         Ready (tap)                   Problem (tap / on change)
┌──────────────────────┐    ┌──────────────────────┐     ┌──────────────────────┐
│ STARTING…        DEV │    │ READY            DEV │     │ PROBLEM              │
├──────────────────────┤    ├──────────────────────┤     ├──────────────────────┤
│ Services     ✓       │    │ ᛒ  Laptop-MSE        │     │ ✗ Service down:      │
│ Bluetooth    …       │    │ ✎  Pen ready         │     │   bt_hid_ble         │
│ Dashboard    …       │    │ ⌂  HomeNet 192.168.1.23│   │ ⌂  HomeNet 192.168.1.23│
└──────────────────────┘    └──────────────────────┘     └──────────────────────┘

Sending                      Sent                          Setup mode (hotspot up)
┌──────────────────────┐    ┌──────────────────────┐     ┌──────────────────────┐
│ SENDING…             │    │ SENT ✓               │     │ SETUP MODE           │
├──────────────────────┤    ├──────────────────────┤     ├──────────────────────┤
│ ▓▓▓▓▓▓▓▓░░░░░░░░░░░░ │    │ 142 characters       │     │ Wi-Fi  ipr-setup-a1b2│
│ → Laptop-MSE         │    │ → Laptop-MSE  14:32  │     │ Open   10.42.0.1/setup│
│ 142 characters       │    │ Total 13             │     │ Hold 3 s to stop     │
└──────────────────────┘    └──────────────────────┘     └──────────────────────┘

Magnet held                  Shutting down
┌──────────────────────┐    ┌──────────────────────┐
│ RELEASE → HOTSPOT    │    │ SHUTTING DOWN        │
├──────────────────────┤    ├──────────────────────┤
│ ▶ 3 s  Hotspot       │    │ Wait for the LED to  │
│   6 s  Shutdown      │    │ go off, then unplug  │
│  10 s  Mode  15 s Rst│    │                      │
└──────────────────────┘    └──────────────────────┘
```

Header words: `STARTING…`, `READY`, `PROBLEM`, `SENDING…`, `SENT ✓`,
`SEND FAILED`, `SETUP MODE`, `HOLD…`, `RELEASE → HOTSPOT / SHUTDOWN / MODE /
RESET`, `CANCELLED`, `SHUTTING DOWN`, `RESETTING…`, `MODE: DEVELOPMENT` /
`MODE: PRODUCTION`, `HOTSPOT…` (starting / stopping), `HOTSPOT FAILED`.

Body lines by state:

| Line | Text |
|---|---|
| Bluetooth | `<host name>` · `Waiting for PC…` · `Bluetooth service down` |
| Pen | `Pen ready` · `Plug in the pen` · `Pen busy (mounting)` · `USB port off — reboot` |
| Network | `<ssid>  <ip>` · `No Wi-Fi — hold 3 s` · `Setup mode` |

The magnet help screen is the display's biggest usability gain: the hold
thresholds are hard to remember, and the LED can only show a colour.

### 4.3 Progress

`transmission.set_sending()` records the character count of the text being
typed; the bar is indeterminate (a sweeping block) unless a percentage is
known.  `SENT ✓` stays for `OledSendHoldSeconds` (10 s) with the count and
the running total; `SEND FAILED` shows the reason and "Text kept on pen".

### 4.4 Long lines roll

A header or body line wider than its slot (a long SSID, host name or IP) is
never truncated.  The renderer scrolls it: hold 1.5 s at the start, roll
left at 12 px/s (about two characters per second), hold 1 s once the last
character is fully visible, then restart.  Lines that fit never move; the
icon column stays fixed.  While a line is rolling the manager redraws at
`OledMarqueeFps` (8 Hz; 6 on a Zero W) instead of only on change.  Rolling
happens only while the display is on, so it costs nothing when idle.

## 5. Evaluation 3 — the LED's role with a display present

The LED stays exactly as it is.

1. It works **before and after Python**: firmware white at ~1 s,
   `ipr-led-boot.service` at ~14 s, `ipr-led-halt.service` "safe to unplug".
   The display can only start with the application (~35 s).  An early boot
   unit for the display was considered and rejected: Python + Pillow start-up
   costs seconds on the Zero W for one static frame, and the LED already
   covers that window.
2. It is glanceable from across the room and through the case; the display
   has to be read.
3. Zero W units without a display must keep working, and the gestures and
   colours are printed in both manuals.
4. "Blink = in progress" costs nothing on the LED; on the display it would
   need animation frames.

Division of labour: **LED = glanceable state and gesture arming colour;
display = explanation, names, numbers and gesture help.**

## 6. Design

```
GpioMonitor (20 Hz thread) ── snapshot() ──▶ OledManager (4 Hz thread)
   LedLogic.phase / armed / held            │ compose(): Snapshot → Screen   (pure, no Pillow)
   SystemProbe (+ ssid, ip, failed services)│ render():  Screen → PIL.Image  (Pillow)
transmission.get()  ────────────────────────▶ │ Ssd1306: /dev/i2c-N via os/fcntl (stdlib)
usb.detector.pen_presence() ────────────────▶ │ sleep() / wake() per § 3
```

- **No event bus.**  The display polls the same way the LED does; the LED's
  `LedLogic` exposes a `snapshot()` (phase, armed gesture, held seconds,
  probe fields).  When GPIO is disabled or unavailable, a `StandaloneSource`
  with its own `SystemProbe` provides BOOT → STATUS → IDLE by timeout.
- **`Screen` is plain data** (header, badge, lines, progress), so screen
  selection is unit-tested without Pillow.  Pillow only appears in
  `render.py` and the driver.
- **Rendering: Pillow from Debian** (`python3-pil`, `fonts-dejavu-core`),
  visible through the venv's `--system-site-packages` exactly like
  `python3-rpi-lgpio`.  `luma.oled` was rejected: its value over Pillow is a
  100-line driver plus five transitive packages (smbus2, pyftdi, cbor2,
  spidev, pyusb) that would have to be wheel-checked for ARMv6.  `pillow`
  is a **dev** dependency only, for tests on the PC.
- **Driver in-repo** (`oled/ssd1306.py`): `os.open("/dev/i2c-1")`,
  `ioctl(I2C_SLAVE)`, `os.write()` with the SSD1306 control bytes.  No C
  extension, no third-party package.
- **Absent hardware = inert.**  `OledManager.start()` logs one warning and
  returns when `OledEnabled` is false, Pillow is not importable,
  `/dev/i2c-N` is missing, or nothing answers at the address — the same
  pattern as `GpioMonitor` without `RPi.GPIO`.
- **Halt.**  `OledManager.stop()` blanks the panel, except during a
  shutdown where it leaves "SHUTTING DOWN" and `ipr_led_halt.sh` (the
  existing `ipr-led-halt.service`) sends `0xAE` with `i2cset` at the same
  moment it turns the LED off.  No new unit.
- **Host name.**  The LED probe reads Bluetooth link state from sysfs on
  purpose (`bluetoothctl` floods the journal).  The display needs the host
  name once per connection; it is fetched with `bluetoothctl devices
  Connected` only on the connected edge and cached.

## 7. Files

| Area | Files |
|---|---|
| Application | `src/ipr_keyboard/oled/{ssd1306,screens,render,manager}.py`, `gpio_monitor.py` (snapshot, probe fields), `usb/detector.py` (`pen_presence`), `transmission.py` (chars), `main.py`, `config/manager.py`, `config.default.json` |
| Tests | `tests/oled/test_{screens,render,ssd1306,manager}.py`, `tests/config/test_manager.py` |
| Device pieces | `scripts/headless/install_oled_support.sh`, `ipr_led_halt.sh`, `test_oled.sh`, `test_provision.sh` (phase N) |
| Provisioning | `provision/04_enable_services.sh`, `scripts/deploy/deploy_full_update.sh`, `scripts/sys_install_packages.sh` |
| Docs | `docs/hardware/oled-display.md`, `docs/hardware/gpio-wiring.md`, `docs/architecture/ARCHITECTURE.md`, `docs/user/hotspot-setup.md`, `scripts/headless/README.md`, both manuals |

## 8. Rolling out to an existing device

```bash
sudo bash scripts/headless/install_oled_support.sh   # config.txt, i2c-dev, packages, group, halt hook
sudo systemctl restart ipr_keyboard.service           # picks up the i2c group
sudo reboot                                           # only if /dev/i2c-1 did not exist before
sudo bash scripts/headless/test_provision.sh --auto   # phase N must be all green
```

`deploy_full_update.sh` runs the installer automatically.
