# Status LED and magnet — analysis and design

Date: 13 September 2026.  Applies to `ipr-prod-zero2` (Pi Zero 2 W, Debian 13
Trixie, kernel 6.18) and, unchanged, to the Pi Zero W.

This note records why the status LED did not work on a freshly provisioned
production device, and the design that fixes it.  The user-facing behaviour is
documented in `docs/hardware/gpio-wiring.md` and in the two manuals under
`docs/manuals/`.

---

## 1. Symptoms

- The LED never lit: not during boot, not when the magnet was brought near the
  reed switch after boot.
- The hotspot could only be started at boot (marker file, triple power-cycle),
  never afterwards.
- The wiring was verified good by driving the pins directly with `gpioset`
  (all three colours lit).

## 2. Findings

| # | Finding | Evidence |
|---|---------|----------|
| 1 | **`RPi.GPIO` was not importable inside the application venv**, so `GpioMonitor.start()` returned silently. This alone explains "no LED at all". | Journal: `GPIO not available — GPIO monitor disabled (dev/non-Pi host)`. `.venv/pyvenv.cfg` had `include-system-site-packages = false`; `pyproject.toml` declares no GPIO dependency. The Debian package `python3-rpi-lgpio` was installed on the device but invisible to the venv. |
| 2 | **Nothing drove the LED before the Python application.** `ipr_keyboard.service` started at ~35 s after power-on and was ready at ~41 s; the LED stayed dark through the boot. | `systemd-analyze critical-chain ipr_keyboard.service`: `@34.5s`; userspace boot 47 s. |
| 3 | **The magnet could not start the hotspot** even with working GPIO, for three independent reasons: (a) `sudo systemctl start` needs a password — the app user only had a NOPASSWD grant for the (dhcpcd-era) network helper; (b) `systemctl start` on the already-"active" oneshot unit is a no-op, and even a `restart` exits 0 without starting in on-demand mode because no trigger is present; (c) the unit had no `ExecStop`, so `systemctl stop` never took the AP down. | `sudo -l -U meibye`; `ipr-provision.service`; `net_provision_hotspot.sh` trigger evaluation. |
| 4 | **Hotspot state was misdetected.** `systemctl is-active ipr-provision.service` is true after every boot (`RemainAfterExit=yes`) even when no hotspot runs. Once GPIO worked, the LED would have shown **solid blue permanently**. | `gpio_monitor.py` `_hotspot_active()` (old). |
| 5 | Factory reset (`sudo reboot`) and the dashboard's Reboot/Shutdown buttons failed for the same missing sudo grant. | `gpio_monitor.py` (old), `web/setup.py`, `web/server.py`. |
| 6 | Documented patterns were not implemented: "red slow blink" was solid red; the 30 s status window was a blocking loop that never refreshed; the module had no unit tests. | old code vs. `docs/hardware/gpio-wiring.md`. |
| 7 | **`sudo` cannot work inside `ipr_keyboard.service` at all**: the unit had `CapabilityBoundingSet=CAP_NET_BIND_SERVICE`, which strips the setuid capabilities `sudo` needs. Found on the first magnet test after the sudoers fix: `sudo: unable to change to root gid: Operation not permitted`. This had also silently broken the dashboard's Reboot/Shutdown/cert-renew buttons. | journal of `ipr_keyboard.service`, 13 Sep 09:59. |

## 3. Requirements

1. The LED must reflect the **whole** boot, from power-on, not only the
   application.
2. Bringing the magnet near the reed switch must show the operational status
   at any time after boot.
3. The hotspot must be startable (and stoppable) at any time with the magnet,
   with LED feedback for the request and for the hotspot being up.
4. Respect the platform: single-core ARMv6 Zero W, no build step, no extra
   Python wheels, small diffs.
5. Keep the gestures that are already printed in the manuals (tap / 3 s /
   10 s).

## 4. Design

### 4.1 Boot phases — three layers hand the LED over

| Phase | From | Mechanism | LED |
|---|---|---|---|
| Power on | ~1 s | `gpio=22,23,24=op,dh` in `config.txt` — the firmware drives the pins before the kernel | white solid |
| OS boot | ~14 s (`sysinit.target`) | `ipr-led-boot.service`, `DefaultDependencies=no`, runs `gpioset --toggle 125ms` | white 4 Hz |
| App start | ~35 s | `ipr_keyboard.service` drop-in: `ExecStartPre=+systemctl stop ipr-led-boot.service` (root, via `+`) plus `Conflicts=`/`After=` — the blinker is stopped and the lines released; `GpioMonitor` is started first in `main()` and claims them (with a short retry) | white 4 Hz |
| Ready | ~41 s | a waiter thread polls `/health` on `LogPort`; `set_ready()` ends the boot phase | status colour 30 s, then off |

First attempt used `Conflicts=` alone; on the device the blinker kept running
and the app logged `GPIO busy` ten times.  At boot both units are part of the
same start transaction, and systemd resolves a conflict inside a transaction
by dropping one job — it does not issue a stop.  The explicit `ExecStartPre`
with the `+` prefix (runs as root although the service runs as the app user)
is unambiguous; `Conflicts=` is kept for restarts.  The boot blinker is not
restarted if the application restarts.  If the application never answers
`/health` the LED keeps blinking white — the honest signal for "startup
problem".

### 4.2 GPIO backend

The venv is created with `--system-site-packages` (and existing venvs are
flipped in place) so the Debian `python3-rpi-lgpio` shim is importable as
`RPi.GPIO`.  Rationale: the legacy `RPi.GPIO` does not work on current
kernels; `lgpio` has no PyPI wheel for ARMv6; the Debian package covers both
boards and needs no compiler on the device.  Packages installed in the venv
still shadow system ones, so Flask etc. are unaffected.

`gpio_monitor` now logs a **warning with the import error** when it disables
itself, and `test_provision.sh` phase K fails if `RPi.GPIO` is not importable
from the venv.

### 4.3 State machine

`gpio_monitor.py` is rewritten around a pure state machine (`LedLogic`) that
is ticked at 20 Hz with the current time and reed state and returns a
`Frame` (colour + blink rate).  It has no threads, no GPIO and no wall clock,
so it is covered by unit tests with a fake clock, probe and actions
(`tests/test_gpio_monitor.py`).  `GpioMonitor` is the thin thread that samples
the reed switch, ticks the logic and writes the LED (only on change).

Phases: `BOOT → STATUS → IDLE`, plus `HOTSPOT_BUSY`, `HOTSPOT_ON`,
`FAIL_FLASH`, `RESETTING`.  Probes (`nmcli con show --active`,
`bluetoothctl devices Connected`) run every 2 s while the LED shows status and
every 5 s while idle or solid blue — never in the 20 Hz loop itself.

Hotspot state is **read from NetworkManager** (`ipr-hotspot` connection
active), never from the unit state.  This also makes the LED show blue when
the hotspot was started by the boot marker, the triple power-cycle or the
CLI.

### 4.4 Privileges

All root actions go through one helper,
`/usr/local/bin/ipr_hotspot_ctl.sh {start|stop|status|factory-reset}`, with
a single sudoers line for the app user (`/etc/sudoers.d/<user>-ipr-gpio`,
which also grants `reboot`/`shutdown` for the dashboard buttons).

For `sudo` to work at all, the service must not restrict the capability
bounding set: `svc_install_systemd.sh` no longer writes
`CapabilityBoundingSet=`, and `install_gpio_support.sh` deletes the line from
an already-installed unit (`AmbientCapabilities=CAP_NET_BIND_SERVICE` stays,
for port 443).  Phase K.10 of `test_provision.sh` checks this.

`start` writes `/run/ipr-hotspot.request` and **restarts**
`ipr-provision.service`; `net_provision_hotspot.sh` evaluates the request file
first, before the boot marker and the boot counter.  `stop` stops the unit,
whose new `ExecStop=ipr-provision.sh --stop` takes the connection down (the
helper also does it directly, in case an older unit is installed).
NetworkManager re-activates the home WiFi profile on its own.

### 4.5 Gestures and LED feedback

| Gesture | LED while held | On release |
|---|---|---|
| Tap (< 3 s) | status colour | status colour for `GpioLedIdleSeconds`, then off |
| Hold ≥ 3 s | blue 4 Hz | hotspot start (blue 4 Hz while starting → **blue solid while up, no timeout**) or stop (→ status colour); red 4 Hz for 3 s if the request fails within 40 s |
| (status) | red solid | shown instead of the status colour while a core service is not active (`SystemProbe.services_ok`) — see `docs/operations/unsupervised-operation.md` |
| Hold ≥ 6 s | purple 4 Hz | production ↔ development mode toggle via `ipr_mode_ctl.sh`; purple solid 3 s to confirm |
| Hold ≥ 10 s | red 4 Hz | WiFi profiles deleted, reboot; red 4 Hz until the reboot |

In development mode a 150 ms purple blip every 4 s is rendered on top of
every frame (including off), except while booting, arming or confirming.
See `docs/operations/network-modes.md`.

Gestures are ignored during the boot phase and while a reset is in progress.

## 5. Alternatives considered

- **`pip install rpi-lgpio` in the venv** — needs the `lgpio` C extension;
  no wheel for ARMv6, and a compiler on a production Zero W is not acceptable.
- **`gpiozero`** — same visibility problem; larger dependency; no benefit for
  three outputs and one input.
- **`pinctrl` for the boot blink** — Pi-specific and does not claim the lines
  (so no hand-over would be needed), but `gpioset` is the portable, packaged
  tool; `ipr_led_boot.sh` falls back to `pinctrl` if `gpiod` is missing.
- **Fixing `RemainAfterExit`** so the unit reflects hotspot state — would
  turn a "no trigger" boot into a *failed* unit.  Reading NetworkManager is
  simpler and always correct.
- **Keeping the LED on 30 s after hotspot start** (old behaviour) — the user
  needs to see that setup mode is on for as long as it is on; solid blue
  persists.

## 6. Files

| Area | Files |
|---|---|
| Application | `src/ipr_keyboard/gpio_monitor.py`, `src/ipr_keyboard/main.py`, `tests/test_gpio_monitor.py` |
| Device pieces | `scripts/headless/ipr_hotspot_ctl.sh`, `ipr_led_boot.sh`, `ipr-led-boot.service`, `ipr-provision.service`, `net_provision_hotspot.sh`, `install_gpio_support.sh` |
| Provisioning | `provision/04_enable_services.sh`, `scripts/deploy/deploy_full_update.sh`, `scripts/sys_install_packages.sh`, `scripts/sys_setup_venv.sh`, `scripts/service/svc_install_systemd.sh` |
| Validation | `scripts/headless/test_provision.sh` (H.1 uses `LogPort`; new phase K; manual J.7), `scripts/headless/test_gpio_led_reed.sh` |
| Docs | `docs/hardware/gpio-wiring.md`, `docs/user/hotspot-setup.md`, `scripts/headless/README.md`, `docs/architecture/ARCHITECTURE.md`, both manuals |

## 7. Rolling out to an existing device

```bash
sudo bash scripts/headless/install_provision_service.sh   # new hotspot script + ExecStop
sudo bash scripts/headless/install_gpio_support.sh        # config.txt, boot unit, helper, sudoers, venv flag
sudo systemctl restart ipr_keyboard.service               # LED live immediately
sudo reboot                                               # to see the firmware/boot phases
sudo bash scripts/headless/test_provision.sh --auto       # phase K must be all green
```

`deploy_full_update.sh` runs the first two steps automatically.
