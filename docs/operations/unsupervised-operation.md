# Unsupervised operation — how failures become visible

The device runs without anyone watching a terminal.  A failure must
therefore (1) recover on its own where possible, (2) be visible on the
device, and (3) leave a trace an administrator can read days later.

## 1. Self-recovery

- The Bluetooth adapter is brought to the same LE-only state on every start
  (`bt_adapter_prepare.sh`, ExecStartPre of the agent), so a bonded PC
  reconnects after boots and service restarts alike.  Before this the adapter
  was dual-mode after a boot and LE-only after a restart, and Windows would
  not reconnect across the two.

- `bt_hid_ble.service` and `bt_hid_agent_unified.service`: `Restart=always`.
- `ipr_keyboard.service`: `Restart=on-failure`; its web server exits the
  process after five failed binds so systemd restarts it.
- `irispen-mount.service`: `Restart=on-failure`, and restarted by udev when
  the pen is re-plugged.

## 2. Visible on the device

| Where | What |
|---|---|
| Status LED | **white solid → off** during a controlled shutdown (magnet 6 s): off means safe to unplug. **Red solid** when a core service (`bluetooth`, `bt_hid_ble`, `bt_hid_agent_unified`) is not active — checked every few seconds while the LED is on; tap the magnet to see it |
| Dashboard, Home / Connections | System state *Warning — one or more services are not running*; Pen card *Not detected* / *Connecting* / *Ready* from the USB bus and the mount |
| Setup portal, Status page | per-service badges, hotspot state |

## 3. A trace that survives

Installed by `scripts/headless/install_observability.sh` (provisioning and
`deploy_full_update.sh`):

- **Persistent journal**: `/etc/systemd/journald.conf.d/ipr.conf` —
  `Storage=persistent`, capped at 64 MB / 1 month (SD-card friendly).
  Before this the journal kept only the current boot, and a
  `Failed to restart bt_hid_ble.service` from the day before was gone.
- **Incident log**: every core unit carries `OnFailure=ipr-failure@%n.service`,
  which appends one line to `/var/lib/ipr-keyboard/incidents.log`:

  ```
  2026-09-12T13:06:49+02:00  bt_hid_ble.service failed (result=exit-code)
  ```

  The file is world-readable, never rotated by the device (it grows by one
  line per failure), and `test_provision.sh` prints its last lines when it
  is not empty.

## What to do after an incident

```
cat /var/lib/ipr-keyboard/incidents.log
journalctl -u <unit> --since "<timestamp>" --no-pager
systemctl status <unit>
```

A unit that is *active* again with a line in the incident log was a
transient (e.g. a restart race during a deploy); a unit that is *failed*
needs the journal.  `sudo ./scripts/rpi-debug/dbg_diag_bundle.sh` collects
all of it for a report.
