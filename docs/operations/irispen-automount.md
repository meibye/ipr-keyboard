# IrisPen automount

The IrisPen is an MTP device (USB `0e8d:2008`), not a block device.  Its
scans only become files the application can read after `jmtpfs` mounts it
at `/mnt/irispen` — the folder named in `IrisPenFolders` in `config.json`.

Until September 2026 that mount was a manual step
(`scripts/usb_mount_mtp.sh`), so on an unsupervised device the pen was
plugged in but never mounted: the dashboard showed *Ready* (the state was
derived from the Bluetooth agent, not the pen) while the Debug page listed no
files.

## How it works now

| Piece | Role |
|---|---|
| `/etc/udev/rules.d/69-irispen-mtp.rules` | gives the device node to group `plugdev` and exposes it to systemd as `dev-irispen.device`, wanting `irispen-mount.service` |
| `irispen-mount.service` | runs `jmtpfs -f /mnt/irispen` as the app user; `BindsTo=dev-irispen.device` stops it — and `fusermount -u` runs — when the pen is unplugged |
| `install_irispen_mount.sh` | installs both, creates the mountpoint, installs `jmtpfs` if missing; called by provisioning and `deploy_full_update.sh` |

Plug the pen in: within a few seconds `mountpoint /mnt/irispen` is true and
the dashboard's Pen card goes *Not detected → Connecting → Ready*.  The Pen
state is now read from the USB bus (sysfs) and `/proc/mounts`, so it is
honest even when the mount is still coming up.

## Checking

```
systemctl status irispen-mount.service
mountpoint /mnt/irispen && ls /mnt/irispen
journalctl -u irispen-mount.service -b
```

`test_provision.sh` phase M checks the rule, the unit and — when a pen is
plugged in — the mount.  A failed mount is recorded in
`/var/lib/ipr-keyboard/incidents.log` (see `unsupervised-operation.md`).

## Notes

- The mount is private to the app user (no `allow_other`); nothing else on
  the device needs it.
- MTP allows one client at a time: do not run `scripts/usb_mount_mtp.sh` by
  hand while the service is active.
- The old `usb_setup_mount.sh` / fstab path is for mass-storage scanners only.
