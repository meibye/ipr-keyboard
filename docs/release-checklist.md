# Release checklist

What has to be true before a build goes on a device that someone depends on.
Five gates, cheapest first; a release is valid when all five pass on **both**
board types.

The automated gates are run by whoever prepares the release.  Gate 3 is the
one that cannot be automated: it needs eyes on the panel and a hand on the
magnet.

---

## Gate 1 — Repository (every change)

```bash
python -m pytest tests -q --ignore=tests/e2e     # all green
python -m ruff check src tests scripts
python -m ruff format --check src tests
for f in $(git ls-files '*.sh'); do bash -n "$f" || echo "SYNTAX $f"; done
```

Also: no stray carriage byte inside a line of a shell script (they silently
break `awk` and `tr` filters — this has happened):

```bash
python - <<'PY'
import pathlib
for p in pathlib.Path(".").rglob("*.sh"):
    if ".venv" in p.parts or ".git" in p.parts: continue
    d = p.read_bytes()
    if any(b == 13 and d[i+1:i+2] != b"\n" for i, b in enumerate(d)):
        print("stray CR:", p)
PY
```

## Gate 2 — Device, automated

```bash
sudo bash ~/dev/ipr-keyboard/scripts/headless/test_provision.sh --auto
```

Must report **0 failures**; the result is kept at
`/opt/ipr_state/provision_verify.log`.  Skips are expected — they are the
manual checks in gate 3.

Section **O** is the one to read first on a fresh install: it checks the three
tmpfs files that carry state between the BLE daemon and the application, and
that the env default and the saved typing speed agree.  None of those is needed
for a send to *work*, which is why they are audited — when one is missing the
device degrades quietly: no progress on the panel, no typing measurement, or a
speed that cannot be changed without dropping the PC.

Then prove the device is the repository, not something that drifted from it:

- every file under `src/`, `scripts/` and `provision/` matches the checkout
  (compare line-ending-normalised hashes);
- every installed artefact under `/usr/local/`, `/etc/systemd/system/` and
  `/etc/NetworkManager/` matches its source in the repository.

Stale installed helpers have caused a failed firewall and a lost Wi-Fi
configuration in the past, and neither showed up in the application's own
tests.

`/usr/local/bin/bt_hid_ble_daemon.py` is the one to check by hand if anything
else is skipped: the application degrades quietly when it is older than the
repository, because progress reporting is optional by design.

Disk, once per release rather than on a schedule (see
docs/operations/disk-and-logs.md):

```bash
df -h /                 # expect well under 75%; the dashboard warns above it
journalctl --disk-usage # bounded at 64 MB by SystemMaxUse
du -sh /var/cache/apt/archives   # the one unbounded item; apt-get clean
```

## Gate 3 — Device, by hand

Nothing here can be automated.  Tick every line.

**Boot**
- [ ] The panel lights within ~20 s of power-on with `STARTING…` and the
      checklist, long before the application is up.
- [ ] It continues into the application's checklist, then `READY`.
- [ ] The LED goes white → white blink → status colour.

**Magnet menu** (device with a panel)
- [ ] Three white LED blinks the moment the magnet lands.
- [ ] Holding **1.2 s** opens the menu — **while the magnet is still down**,
      not when it comes away.  The LED shows the ordinary status colour; blue
      is reserved for "the hotspot is up" and is deliberately not reused.
- [ ] Releasing after the menu opens does **not** also step to the next item.
- [ ] Taps move through the list and wrap; a hold opens `Display`.
- [ ] A hold selects the instant the bar fills, with the magnet still down.
- [ ] `Display ▸ Display timeout` marks the current value; choosing another
      returns to `Display` and the setting survives a reboot.
- [ ] `Display ▸ Menu timeout` likewise, and the chosen value is the one the
      menu then waits.
- [ ] `Shutdown` asks for one tap; the panel says what it will do.
- [ ] `Factory reset` asks for **two** taps and counts them; walking away
      cancels it.
- [ ] `Recovery info` asks for a tap, then shows the hotspot name, key **and
      the dashboard login**; after the configured number of reveals it refuses.
- [ ] The menu closes by itself after the configured menu timeout.

**Telling a tap from a hold** — both of these were reported from a device, and
they fail in opposite directions, so test both
- [ ] `Back` and `Exit` can be selected **first time**, repeatedly.  They are
      the worst case: stepping past them wraps the whole list.
- [ ] Deliberately let the magnet wobble mid-hold (shift it, do not lift it).
      One hold, one action — it must not arrive as two taps.
- [ ] Lift the magnet just **short** of the bar filling.  It counts as a tap
      and steps on; it must not select.
- [ ] Twenty taps in a row step exactly twenty times.

**Magnet ladder** (device without a panel, or `OledEnabled: false`)
- [ ] 3/6/10/15/20 s still arm hotspot / shutdown / mode / reset / cancel with
      the documented colours.

**After a daemon update, a bonded PC still works**

"Update the daemon" means install it and restart the unit:

```bash
cd ~/dev/ipr-keyboard && sudo ./scripts/deploy/deploy_install_ble_daemons.sh
```

That copies `scripts/service/bin/bt_hid_ble_daemon.py` to `/usr/local/bin/` and
restarts `bt_hid_agent_unified.service` and `bt_hid_ble.service`.

- [ ] After installing, the journal shows `GATT application registered` and
      then `Registered GATT+ADV ... (fast, 40-80 ms)`.  **If the GATT line is
      missing, the device is advertising nothing and is invisible** — that is
      the failure mode of a rejected service, and it crash-loops.
- [ ] The PC reconnects and typing works, without removing and re-pairing.
- [ ] If a re-pair *is* needed after an update, it is the host's handle cache.
      Do not try to fix it with a Service Changed characteristic: BlueZ owns
      `0x1801` and refuses an application that registers it, taking the whole
      database and the advertisement down with it.  See
      docs/operations/bluetooth-pairing.md.

**Getting the PC back after a restart**
- [ ] Restart the device (magnet menu ▸ Power ▸ Restart).  The journal says
      `Registered GATT+ADV ... (fast, 40-80 ms)`.
- [ ] The PC reconnects in **seconds to a couple of minutes**, not the 26
      minutes measured before fast advertising.  The device cannot force it —
      it is a BLE peripheral — so this is a "much better", not a guarantee.
- [ ] While it is away the panel says `Reconnect from PC`, not
      `Waiting for PC…`, and the header stays `READY`.
- [ ] Once connected, the journal shows the back-off to the slow interval.
- [ ] With nothing ever paired, the panel says `Waiting for PC…` instead.

**The home screen says whether anything is outstanding**
- [ ] Unplug the pen: the header becomes `NOT READY` and the pen line carries a
      warning triangle.  It must **not** say `READY` — it used to, and nobody
      noticed the sentence in the middle of the screen.
- [ ] Plug it back in: `READY` returns.
- [ ] With no Wi-Fi: `NOT READY` and `No Wi-Fi: see menu`.
- [ ] A PC that has not connected yet does **not** make the device
      `NOT READY` — it connects by itself.
- [ ] A real fault (stop `bt_hid_ble.service`) gives `PROBLEM` and a ✗, not a
      triangle.  The two tiers must stay distinct.

**Scanning**
- [ ] A paired PC receives a real scan; the panel shows `SENDING…` then
      `SENT ✓` with the character count.
- [ ] **Leave the device idle for more than two minutes, then scan once.**  The
      panel must show the character count climbing, and the KPIs must gain a
      `type_ms` sample.  This is the case that was broken: the progress file
      goes stale after 120 s, which was read as "this daemon reports nothing",
      so the commonest case of all — an idle device, then one scan — silently
      lost both the panel progress and the measurement.
- [ ] The dashboard's Transmission card shows a bar and `N of M characters`
      during that send, agreeing with the panel.
- [ ] The scan is deleted from the pen afterwards, and a second scan of the
      same text is delivered too (it is a new file, not a duplicate).
- [ ] The pen is detected after a re-plug, and the panel says `Pen ready`.

**Typing speed** (Settings, and Debug ▸ Typing speed trial)
- [ ] Settings ▸ Typing speed lists Normal / Fast / Faster / Fastest with the
      characters-a-second figure.
- [ ] Choosing a speed applies to the **next scan** with no restart, and the
      PC does **not** have to pair again.
- [ ] Run the trial: every step reports a timing.  A step saying it could not
      be timed is a defect — the first step is the one to watch, because it
      always follows a quiet spell.
- [ ] The trial's `Expected` and `Measured` columns are both characters a
      second, and the names match the Settings list word for word.
- [ ] The PC receives four clearly separated ten-line blocks, each under a
      `===== Normal (20 ms) =====` banner.
- [ ] Read the blocks: at the fastest step, expect missing or transposed
      characters.  **That** is what decides the setting, not the timings.
- [ ] The Performance panel gains samples during the trial (`MetricsEnabled`
      on), and names a bottleneck instead of staying empty.
- [ ] After the trial, Settings still shows the speed you started with.

**Network and recovery**
- [ ] With the hotspot up, the panel's `SETUP MODE` screen says
      `Hold: menu to stop`, and following it actually stops the hotspot.  The
      old text said `Hold 3s to stop`, which did nothing once a hold started
      opening the menu.
- [ ] The setup portal's *Rescan* lists the networks actually in range.
- [ ] Entering an SSID and key saves without error and the device joins.
- [ ] Production mode closes SSH and the dashboard; development opens them.
- [ ] From a device with no Wi-Fi: hotspot → portal → credentials → back on
      the network, using only what the panel shows.

## Gate 3b — Traps found the hard way

- [ ] **Do not edit `config.json` while the service is running.**  The process
      holds the configuration in memory and rewrites the whole file on the next
      `update()`, so a hand edit is silently reverted.  `RecoveryRevealLimit`
      was raised to 10 that way and was back to 3 the next day.  Change it in
      the dashboard, or stop the service first.
- [ ] **`/opt/ipr_common.env` is the only env file that is read.**
      `bt_hid_ble.service` has `EnvironmentFile=-/opt/ipr_common.env`, and the
      leading `-` means a missing file is not an error — so editing
      `/etc/default/bt_hid_ble` changes nothing and fails silently.
- [ ] After a release, check that the env default and the saved
      `TypingDelayMs` say the same thing.  A device left at
      `BT_KEY_DELAY_MS=12` that then saves the 20 ms default gets **slower**,
      and nothing announces it.

## Gate 4 — Both boards

Everything above on the **Zero 2 W** (64-bit, multi-core) *and* the
**Zero W** (ARMv6, single core, 32-bit).  The Zero W is where Pillow and
`rpi-lgpio` come from Debian packages, where the I²C frame time matters, and
where `OledMarqueeFps` may need lowering.

## Gate 5 — A fresh install, unattended

**First remove "IPR Keyboard" in the PC's Bluetooth settings.**  The install
wipes the device's half of the bond but not the PC's, and a PC holding a stale
bond reconnects in a loop — Connected / Not connected, `PC connecting…` on the
panel — which looks like a fault in the build.  See
docs/operations/bluetooth-pairing.md.

From a freshly imaged card:

```bash
bash ./scripts/deploy/host_push_to_device.sh <host>
ssh -t <host> 'sudo mv /tmp/ipr_common.env /opt/ipr_common.env \
  && sudo chmod 0600 /opt/ipr_common.env \
  && sudo ~/dev/ipr-keyboard/scripts/deploy/device_bootstrap.sh --unattended'
```

Must finish without a keyboard, reboot and resume by itself (three reboots on
a fresh image: OS base, identity, and the firmware change that enables I²C),
and **exit 0** — the wizard's exit status is the audit's failure count.

Record the generated credentials from the step-14 summary; they are
regenerated by every install.
