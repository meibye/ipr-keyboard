---
name: fix-script-permissions
description: Set the executable flag on all shell and Python scripts under scripts/ on the target RPi after file upload.
---

# When to use
- After uploading files to the RPi via MCP SSH (upload tool does not preserve Unix permissions)
- After a fresh clone or rsync to the RPi
- Whenever a new script is added to scripts/ and deployed

# Background
Windows has no concept of Unix execute bits. Any file transferred from Windows to the RPi
via MCP upload, scp, or rsync without explicit permission preservation will land without the
executable flag, causing `Permission denied` when the script is invoked directly.

Only files under `scripts/` need `+x`; source modules under `src/ipr_keyboard/` are imported,
not executed directly, and must NOT be made executable.

# Inputs
- `TARGET_DIR`: root of the repo on the RPi (default: `/home/meibye/dev/ipr-keyboard`)

# Procedure

Run the following via `ipr-rpi-dev-ssh` execute-command:

```bash
TARGET_DIR=/home/meibye/dev/ipr-keyboard
find "$TARGET_DIR/scripts" \( -name "*.sh" -o -name "*.py" \) -exec chmod +x {} +
echo "Permissions fixed. Verifying sample..."
ls -l "$TARGET_DIR/scripts/test_smoke.sh" "$TARGET_DIR/scripts/headless/test_gpio_led_reed.sh"
```

Expected output: both files show `-rwxr-xr-x` (or similar with `x` in all three groups).

# Verification

After running, spot-check a few scripts:

```bash
ls -l /home/meibye/dev/ipr-keyboard/scripts/test_smoke.sh
ls -l /home/meibye/dev/ipr-keyboard/scripts/service/bin/bt_hid_ble_daemon.py
ls -l /home/meibye/dev/ipr-keyboard/scripts/headless/gpio_factory_reset.py
```

All must show `x` in the owner permission bit (`-rwx...`).

# Quality bar
- Zero scripts under scripts/ remain without the execute bit after this skill runs
- No files outside scripts/ are modified
- Verification `ls -l` output must confirm `x` on the spot-checked paths

# Output format
- Count of files affected (from find output)
- ls -l output for the two spot-checked files
- Any errors (permission denied on chmod = run with sudo)

# Related skills
- deploy-dev
- test-on-rpi
