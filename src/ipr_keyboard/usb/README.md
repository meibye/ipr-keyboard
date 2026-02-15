# src/ipr_keyboard/usb/

USB/MTP file ingestion helpers.

## Files

- `detector.py`: list/newest/wait-for-new-file polling
- `reader.py`: read with max-size guards
- `deleter.py`: delete helpers
- `mtp_sync.py`: sync text files from MTP root to cache

## Core Usage in App Loop

- detect newest file newer than last processed mtime
- read text if within size limit
- send text via Bluetooth helper path
- optionally delete processed file

## `mtp_sync.py` CLI

```bash
python -m ipr_keyboard.usb.mtp_sync \
  --mtp-root /mnt/irispen \
  --cache-root ./cache/irispen \
  --delete-source
```
