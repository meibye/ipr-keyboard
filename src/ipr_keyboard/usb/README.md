# src/ipr_keyboard/usb/

Reading scans from the IrisPen, which is mounted over MTP at `/mnt/irispen`
by `irispen-mount.service` (jmtpfs; see docs/operations/irispen-automount.md).

## Files

- `detector.py`
  - `pen_presence()` — `ready` / `busy` / `missing` / `stale` / `disabled`,
    from the USB bus and the mount, for the panel and the dashboard
  - `expand_folders(patterns)` — the configured `IrisPenFolders`, with `*`
    matching the pen's storage name (e.g. `Intern delt lagerplads`)
  - `list_files(folder)` — the `*.txt` scans in a folder, oldest first
  - `newest_file()`, `wait_for_new_file()` — older helpers, kept for tools
- `reader.py` — `read_file(path, max_size)`: size-capped reading
- `deleter.py` — `delete_file()` and helpers
- `mtp_sync.py` — copy text files from the MTP mount to a local cache; a CLI
  used by `scripts/usb_sync_cache.sh`, not by the application

## How the application uses it

The main loop (`main.py`) does not compare timestamps.  For each configured
folder it asks `delivery.DeliveryLog` (`delivery.py`) for the oldest scan not
yet delivered, keyed by `name|mtime|size` in `pen_state.json`:

1. The first time a folder is seen, everything already in it is recorded as
   delivered (a baseline), so old scans are not re-typed.  A folder that was
   empty at that moment has an empty baseline, so its first scan *is* typed.
2. A new scan is recorded as delivered first, then read and typed through
   `BluetoothKeyboard`.  Once the characters have reached the PC it is
   deleted from the pen (if `DeleteFiles` is on); an unreadable or oversized
   file is deleted too.  A scan whose send **failed** stays on the pen and
   is not retried by itself — recording it first is what stops a failing
   scan being re-typed on every poll.

The pen's own scan-history list (on its screen) is not visible over MTP; an
entry there whose file was delivered and deleted opens empty and disappears.

## `mtp_sync.py` CLI

```bash
python -m ipr_keyboard.usb.mtp_sync \
  --mtp-root /mnt/irispen \
  --cache-root ./cache/irispen \
  --delete-source
```
