# GPIO Wiring — Reed Switch and RGB LED

Hardware guide for the Pi Zero 2 W in a Flirc aluminium case.
The onboard ACT LED is not visible through the case; the external RGB LED
is the sole visual indicator.  The analysis and design behind the boot-phase
handling are in `docs/architecture/led-status-design.md`.

---

## Components

| Component | Value / type | Notes |
|-----------|-------------|-------|
| Reed switch | Normally-Open (NO), any voltage rating | SMD or THT; 3 × 1.5 mm SMD or 14 × 2 mm THT glass tube |
| Small neodymium magnet | 5–10 mm disc or bar | Stored near the device; brought close to trigger |
| RGB LED | 5 mm common-cathode | R/G/B on separate anodes, one shared GND leg |
| Resistor — R leg | 150 Ω | Limits current on red element |
| Resistor — G leg | 150 Ω | Limits current on green element |
| Resistor — B leg | 22 Ω | Blue element has higher Vf, needs lower resistance |

**Temporary test rig** (use until RGB LED arrives):
three separate LEDs — red, yellow (green substitute), blue — each with its
own cathode wire to GND.  The blue resistor is still 22 Ω; red and yellow
use 150 Ω.  Software behaviour is identical; yellow maps to the "green" states.

---

## Pin assignments (BCM numbering)

| Signal | BCM | Physical pin | Notes |
|--------|-----|-------------|-------|
| Reed switch | **GPIO 27** | Pin 13 | Pull-up enabled in software |
| RGB LED — Red | **GPIO 22** | Pin 15 | 150 Ω series |
| RGB LED — Green | **GPIO 23** | Pin 16 | 150 Ω series |
| RGB LED — Blue | **GPIO 24** | Pin 18 | 22 Ω series |
| Factory reset (existing) | GPIO 17 | Pin 11 | Do not reuse |

All five signals are in the safe zone — no conflicts with I²C (GPIO 2/3),
UART (GPIO 14/15), or SPI (GPIO 7–11).

---

## Schematic

```
3.3 V supply
    │
    └─ internal pull-up (software)
             │
          GPIO 27 ──────────[Reed Switch]────── GND
             (Pin 13)         (NO type)

GPIO 22 ──[150 Ω]──┬── R anode   ┐
(Pin 15)            │             │
GPIO 23 ──[150 Ω]──┼── G anode   ├── Common cathode ── GND
(Pin 16)            │             │
GPIO 24 ──[ 22 Ω]──┴── B anode   ┘
(Pin 18)
```

For the **test rig** (three separate LEDs):

```
GPIO 22 ──[150 Ω]── Red LED   (+) ── Red LED   (−) ──┐
GPIO 23 ──[150 Ω]── Yellow LED(+) ── Yellow LED(−) ──┼── GND
GPIO 24 ──[ 22 Ω]── Blue LED  (+) ── Blue LED  (−) ──┘
```

---

## Resistor value rationale

| LED | Typical Vf | Supply | Formula | Result | Use |
|-----|-----------|--------|---------|--------|-----|
| Red | 2.0 V | 3.3 V | (3.3 − 2.0) / 0.009 | 144 Ω | 150 Ω |
| Green | 2.1 V | 3.3 V | (3.3 − 2.1) / 0.008 | 150 Ω | 150 Ω |
| Yellow | 2.1 V | 3.3 V | (3.3 − 2.1) / 0.008 | 150 Ω | 150 Ω |
| Blue | 3.0 V | 3.3 V | (3.3 − 3.0) / 0.0136 | 22 Ω | 22 Ω |

GPIO pins on Pi Zero 2 W and Pi Zero W are rated for a maximum of 16 mA per pin.
The two boards share the same 40-pin header and the same GPIO numbering, so this
wiring applies unchanged to both.
Red and green run at 8–9 mA; blue runs at about 13.6 mA at typical Vf.
All three stay within the limit.

**Blue is the marginal channel.** Only about 0.3 V is left across its
resistor after the LED's forward drop, so part-to-part Vf spread moves the
current more than the resistor value does:

| Blue Vf | Voltage across 22 Ω | Current |
|---------|---------------------|---------|
| 2.9 V | 0.4 V | 18.2 mA — **over the 16 mA limit** |
| 3.0 V (typical) | 0.3 V | 13.6 mA |
| 3.1 V | 0.2 V | 9.1 mA |
| 3.2 V | 0.1 V | 4.5 mA — safe but dim |

Do not fit a resistor below 22 Ω: on a unit with below-typical Vf the pin
would already exceed its 16 mA rating.  If blue still looks dim, measure the
actual Vf before changing the resistor, and prefer trimming the other two
channels' PWM duty cycle to rebalance the composite colours instead.

---

## Physical placement in the Flirc case

The Flirc Pi Zero 2 W case is a sealed aluminium shell; the GPIO header
protrudes from one end.  Recommended approach:

1. Mount the reed switch inside the case or along the GPIO breakout PCB,
   positioned close to one edge of the aluminium shell so the external
   magnet can activate it through the thin wall (≤ 3 mm aluminium passes
   the field of a 6–10 mm neodymium magnet).
2. Mount the LED(s) on a small breakout PCB connected via a short ribbon to
   the GPIO header, visible through a small hole (3 mm drill) in the top or
   side of the case.
3. Store the trigger magnet on a small adhesive patch on the back of the
   case or on the cable management area.

---

## LED colour map

| Colour | Pattern | Meaning | Driven by |
|--------|---------|---------|-----------|
| White | Solid | Power on — firmware and kernel are starting | `gpio=` line in `config.txt` |
| White | Fast blink (4 Hz) | Booting — services starting, dashboard not yet answering | `ipr-led-boot.service`, then `gpio_monitor` |
| Green | Solid | All OK — WiFi connected and Bluetooth host connected | `gpio_monitor` |
| Amber / Yellow | Solid | WiFi connected, Bluetooth host not yet connected | `gpio_monitor` |
| Red | Slow blink (1 Hz) | No WiFi / no home network configured | `gpio_monitor` |
| Red | Solid | A core service (`bluetooth`, `bt_hid_ble`, `bt_hid_agent_unified`) is not running — see `/var/lib/ipr-keyboard/incidents.log` | `gpio_monitor` |
| Blue | Solid (while held) | Hotspot arming — magnet held 3–6 s | `gpio_monitor` |
| Blue | Fast blink | Hotspot starting or stopping (after release) | `gpio_monitor` |
| Blue | Solid | Management hotspot is active (setup mode) — stays on until the hotspot stops. **The device is then reachable only via the hotspot (10.42.0.1), not on the home network** | `gpio_monitor` |
| Off (while held) | — | Magnet pressed, no threshold reached yet ("press registered"), or the 0.3 s gap at a phase change, or held ≥ 20 s (cancel) | `gpio_monitor` |
| White | Solid (while held) | Shutdown arming — magnet held 6–10 s | `gpio_monitor` |
| White | Solid | Shutting down — wait; **off = safe to unplug** (`ipr-led-halt.service`) | `gpio_monitor`, then `ipr-led-halt` |
| Purple | Solid (while held) | Mode toggle arming — magnet held 10–15 s | `gpio_monitor` |
| Purple | Solid (3 s) | Mode changed (production ↔ development) | `gpio_monitor` |
| Purple | Short blip every 4 s | **Development mode** — SSH and dashboard are open on the network. Shown on top of any other state, including off | `gpio_monitor` |
| Red | Solid (while held) | Factory reset arming — magnet held 15–20 s | `gpio_monitor` |
| Red | Fast blink | Factory reset in progress; also 3 s after a failed hotspot request | `gpio_monitor` |
| Off | — | Idle — normal operation, no power draw | `gpio_monitor` |

### Boot sequence

The LED reflects the whole boot, not only the application:

```
power on ─┬─ ~1 s ──── ~14 s ──────── ~35 s ──── ~41 s ──── +30 s ──▶
          │ solid   │ white blink   │ white blink  │ status  │ off
          │ white   │ ipr-led-boot  │ gpio_monitor │ colour  │ (idle)
          │ firmware│ .service      │ (app start)  │         │
```

1. **Firmware** — `config.txt` contains `gpio=22,23,24=op,dh`, so the three
   channels go high (white) before the kernel loads.
2. **Early boot** — `ipr-led-boot.service` (`DefaultDependencies=no`) runs
   `gpioset --toggle 125ms` on the three pins from right after `sysinit.target`.
3. **Application** — `ipr_keyboard.service` has a drop-in with
   `ExecStartPre=+systemctl stop ipr-led-boot.service` (plus `Conflicts=`), so
   the blinker is stopped and the pins released just before the app starts;
   `GpioMonitor` starts first thing in `main()` and keeps blinking white.
   (`Conflicts=` alone is not enough at boot: both units are in the same start
   transaction and systemd drops a job instead of stopping the blinker.)
4. **Ready** — when the dashboard answers `/health` on `LogPort`, the LED shows
   the status colour for `GpioLedIdleSeconds` (default 30 s) and then goes off.

If the LED blinks white for more than about three minutes, the application did
not come up — check `journalctl -u ipr_keyboard.service`.

Timings above are from a Pi Zero 2 W; a Zero W is slower but the sequence is
the same.

### Shutdown sequence

White is used for both power transitions on purpose: white = the device is
powering up or down.  (Cyan was tried first for shutdown and could not be told
apart from the 3 s blue blink on the small LED; users released too early and
started the hotspot instead.)

The device is usually powered from a PC's USB port, so "just unplug it" is
the tempting thing to do.  The magnet gives a controlled alternative:

```
hold 6 s ──▶ release ──▶ ~10–20 s ──▶ dark
white blink   white solid              safe to unplug
             (OS stopping)           (power-cycle to start again)
```

1. `gpio_monitor` arms at 6 s (white blink); on release it calls
   `ipr_hotspot_ctl.sh poweroff` (`systemctl poweroff`) and shows solid white.
2. When systemd stops `ipr_keyboard.service` the monitor deliberately leaves
   the pins at white instead of clearing them.
3. `ipr-led-halt.service` — started early at boot doing nothing, so that its
   `ExecStop` runs late in the shutdown — turns the LED off (`pinctrl`) just
   before the kernel halts.  Dark LED = the SD card is no longer being
   written to; unplugging is safe.

A halted Pi Zero cannot be started by the magnet: remove and reconnect power.

---

## Reed switch interaction

The magnet works at any time after the application is up (gestures during the
white boot blink are ignored).  **While the magnet is held the LED shows one
steady colour per phase**, and every phase change starts with a 0.3 s dark
gap so the step registers as a "click" even between similar hues.  Blinking
is reserved for things in progress after release.

| Hold | LED while held | Release → |
|------|----------------|-----------|
| < 3 s (tap) | dark (press registered) | status colour for `GpioLedIdleSeconds`, then off |
| 3–6 s | **solid blue** | hotspot **starts** (blue fast blink while starting, then solid blue) — or **stops** if it was on |
| 6–10 s | **solid white** | **controlled shutdown**: white solid while the OS stops, then **off = safe to unplug** |
| 10–15 s | **solid purple** | **mode toggle** production ↔ development; purple solid 3 s to confirm |
| 15–20 s | **solid red** | all WiFi profiles except the hotspot are deleted, reboot |
| ≥ 20 s | dark | **cancel** — release does nothing |

To abort, keep holding until the LED goes dark (≥ 20 s) and release then, or
release during the dark first 3 s.  (Earlier versions blinked the phase
colours; a blue 4 Hz blink and a cyan 4 Hz blink were not distinguishable on
the small LED and users released in the wrong phase.)

While the hotspot is on, the LED stays **solid blue** regardless of how it was
started (magnet, `ipr_hotspot_ctl.sh start`, boot marker or triple
power-cycle), and a tap does not change it.  If a hotspot request does not
complete within 40 s the LED flashes red for 3 s and returns to the status
colour; the reason is in `journalctl -u ipr-provision.service`.

---

## Software configuration

GPIO pin assignments and LED idle timeout are stored in `config.json`:

```json
{
  "GpioEnabled": true,
  "GpioReedPin": 27,
  "GpioLedRPin": 22,
  "GpioLedGPin": 23,
  "GpioLedBPin": 24,
  "GpioLedIdleSeconds": 30
}
```

Set `GpioEnabled: false` to disable GPIO monitoring on development machines.
The module also disables itself — with a **warning** in the journal naming the
import error — when no `RPi.GPIO`-compatible module can be imported.

### What the LED needs on the device

Installed by `scripts/headless/install_gpio_support.sh` (called from
`provision/04_enable_services.sh` and `scripts/deploy/deploy_full_update.sh`;
safe to re-run):

| Piece | Where | Purpose |
|---|---|---|
| `gpio=22,23,24=op,dh` / `gpio=27=ip,pu` | `/boot/firmware/config.txt` (managed block) | Solid white from power-on; reed pull-up from the firmware |
| `ipr-led-boot.sh` + `ipr-led-boot.service` | `/usr/local/sbin/`, `/etc/systemd/system/` | White blink during OS boot |
| `ipr-led-halt.sh` + `ipr-led-halt.service` | `/usr/local/sbin/`, `/etc/systemd/system/` | LED off at the very end of a shutdown (`ExecStop`, ordered late) — the "safe to unplug" signal |
| `10-led-boot.conf` | `/etc/systemd/system/ipr_keyboard.service.d/` | `ExecStartPre=+systemctl stop ipr-led-boot` + `Conflicts=` so the app takes the pins over |
| `ipr_hotspot_ctl.sh` + sudoers | `/usr/local/bin/`, `/etc/sudoers.d/<user>-ipr-gpio` | Lets the unprivileged app start/stop the hotspot, reset WiFi, reboot |
| `/etc/default/ipr-led` | — | Pin numbers for the boot blink (copied from `config.json`) |
| `python3-rpi-lgpio`, `gpiod` | apt | `RPi.GPIO` API over `lgpio`; `gpioset` |
| `include-system-site-packages = true` | `.venv/pyvenv.cfg` | Makes the Debian `RPi.GPIO` visible to the app |

`rpi-lgpio` is used instead of the legacy `RPi.GPIO` because the legacy module
does not work on current kernels, and because there is no PyPI wheel for the
ARMv6 Zero W — the Debian package covers both boards.  Packages installed in
the venv still take precedence over system ones.

### Privileged actions

`gpio_monitor.py` never calls `systemctl`, `nmcli con delete` or `reboot`
itself.  Everything that needs root goes through
`sudo -n /usr/local/bin/ipr_hotspot_ctl.sh {start|stop|status|factory-reset}`
and, for the 10 s gesture, `sudo -n /usr/local/bin/ipr_mode_ctl.sh toggle`
(sudoers from `install_firewall.sh`).
`start` writes `/run/ipr-hotspot.request` and restarts
`ipr-provision.service`; the hotspot script treats that file as a trigger, so
the hotspot can be started at any time — not only at boot.  `stop` stops the
unit, whose `ExecStop` takes the `ipr-hotspot` connection down.  Hotspot state
is read from NetworkManager (`nmcli con show --active`), never from the unit
state, because a oneshot unit with `RemainAfterExit` is "active" after every
boot whether or not a hotspot is running.

### Troubleshooting

| Symptom | Check |
|---|---|
| LED dark during the whole boot, colour appears only later | `config.txt` block missing → re-run `install_gpio_support.sh`, reboot |
| LED never lights, app runs | `journalctl -u ipr_keyboard.service -b` and look for `GPIO monitor disabled — RPi.GPIO not importable`: the venv cannot see `python3-rpi-lgpio` |
| LED lights but the magnet does nothing | `gpioget -c gpiochip0 27` should read `active` while the magnet is close; check the reed wiring and the pull-up |
| Blue blink, then red flash, hotspot never up | `journalctl -u ipr_keyboard.service` — `unable to change to root gid` means the unit still has `CapabilityBoundingSet=` (re-run `install_gpio_support.sh`, then `systemctl restart ipr_keyboard`); otherwise check sudoers with `sudo -n /usr/local/bin/ipr_hotspot_ctl.sh status` as the app user, and `journalctl -u ipr-provision.service` |
| Blue solid although no hotspot is visible | `nmcli con show --active` — the LED follows NetworkManager; if `ipr-hotspot` is listed the AP is up, check the client |
| White blink for minutes | Either the dashboard never answered on `LogPort`, or the boot blinker was never stopped: `systemctl is-active ipr-led-boot.service` must be `inactive` once the app runs; the journal then shows `GPIO busy`. Re-run `install_gpio_support.sh` (installs the `ExecStartPre` drop-in) |

`sudo bash scripts/headless/test_gpio_led_reed.sh` exercises the hardware
directly (outside the application); `test_provision.sh` phase K checks that
all pieces above are installed.

---

## Migrating from test rig to final RGB LED

When the common-cathode RGB LED arrives:

1. Desolder the three individual LEDs.
2. Wire the new RGB LED: anode R → GPIO 22 via 150 Ω, anode G → GPIO 23 via
   150 Ω, anode B → GPIO 24 via 22 Ω, common cathode → GND.
3. No software change required — GPIO pin assignments are identical.
