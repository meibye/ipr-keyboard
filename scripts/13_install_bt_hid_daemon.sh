#
# Install Bluetooth HID Daemon Script
#
# Purpose:
#   Installs and configures a Bluetooth HID daemon for keyboard emulation on Raspberry Pi.
#   Intended for advanced setups where a persistent HID daemon is required instead of the simple helper script.
#
# Usage:
#   sudo ./scripts/13_install_bt_hid_daemon.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - Bluetooth hardware and dependencies must be present
#
# Note:
#   This script is optional and not required for the default ipr-keyboard workflow.
#   Use only if you need a system-wide Bluetooth HID daemon.

#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/meibye/dev/ipr-keyboard"

echo "=== [13] Install / update Bluetooth HID daemon and helper ==="

########################################
# 1. Install system dependencies
########################################
echo "=== [13] Installing system packages ==="
sudo apt update
sudo apt install -y \
    python3 \
    python3-pip \
    python3-evdev \
    bluez \
    bluez-tools


########################################
# 2. Create /usr/local/bin/bt_hid_daemon.py
########################################
echo "=== [13] Writing /usr/local/bin/bt_hid_daemon.py ==="
sudo tee /usr/local/bin/bt_hid_daemon.py > /dev/null << 'EOF'

#!/usr/bin/env bash
#
# ipr-keyboard Bluetooth HID Daemon Install Script
#
# Purpose:
#   Installs and configures a Bluetooth HID daemon for advanced keyboard emulation.
#   Optional alternative to the default bt_kb_send helper.
#
# Usage:
#   sudo ./scripts/13_install_bt_hid_daemon.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - Environment variables set (sources 00_set_env.sh)
#
# Note:
#   Advanced/optional. Not required for most setups.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"

import os
import time
import threading
from evdev import UInput, ecodes as e

FIFO_PATH = "/run/bt_keyboard_fifo"

# KEYMAP maps Unicode characters to (evdev keycode, shift_required)
KEYMAP = {
    # ASCII letters
    'a': (e.KEY_A, False), 'A': (e.KEY_A, True),
    'b': (e.KEY_B, False), 'B': (e.KEY_B, True),
    'c': (e.KEY_C, False), 'C': (e.KEY_C, True),
    'd': (e.KEY_D, False), 'D': (e.KEY_D, True),
    'e': (e.KEY_E, False), 'E': (e.KEY_E, True),
    'f': (e.KEY_F, False), 'F': (e.KEY_F, True),
    'g': (e.KEY_G, False), 'G': (e.KEY_G, True),
    'h': (e.KEY_H, False), 'H': (e.KEY_H, True),
    'i': (e.KEY_I, False), 'I': (e.KEY_I, True),
    'j': (e.KEY_J, False), 'J': (e.KEY_J, True),
    'k': (e.KEY_K, False), 'K': (e.KEY_K, True),
    'l': (e.KEY_L, False), 'L': (e.KEY_L, True),
    'm': (e.KEY_M, False), 'M': (e.KEY_M, True),
    'n': (e.KEY_N, False), 'N': (e.KEY_N, True),
    'o': (e.KEY_O, False), 'O': (e.KEY_O, True),
    'p': (e.KEY_P, False), 'P': (e.KEY_P, True),
    'q': (e.KEY_Q, False), 'Q': (e.KEY_Q, True),
    'r': (e.KEY_R, False), 'R': (e.KEY_R, True),
    's': (e.KEY_S, False), 'S': (e.KEY_S, True),
    't': (e.KEY_T, False), 'T': (e.KEY_T, True),
    'u': (e.KEY_U, False), 'U': (e.KEY_U, True),
    'v': (e.KEY_V, False), 'V': (e.KEY_V, True),
    'w': (e.KEY_W, False), 'W': (e.KEY_W, True),
    'x': (e.KEY_X, False), 'X': (e.KEY_X, True),
    'y': (e.KEY_Y, False), 'Y': (e.KEY_Y, True),
    'z': (e.KEY_Z, False), 'Z': (e.KEY_Z, True),

    # Digits (no shift)
    '0': (e.KEY_0, False),
    '1': (e.KEY_1, False),
    '2': (e.KEY_2, False),
    '3': (e.KEY_3, False),
    '4': (e.KEY_4, False),
    '5': (e.KEY_5, False),
    '6': (e.KEY_6, False),
    '7': (e.KEY_7, False),
    '8': (e.KEY_8, False),
    '9': (e.KEY_9, False),

    # Space, newline
    ' ': (e.KEY_SPACE, False),
    '\n': (e.KEY_ENTER, False),
    '\r': (e.KEY_ENTER, False),

    # Danish special characters (Danish keyboard layout on the *target* PC):
    # Typically:
    #   å / Å  -> key right of P          -> KEY_LEFTBRACE
    #   ø / Ø  -> key right of Å          -> KEY_APOSTROPHE
    #   æ / Æ  -> key right of L          -> KEY_SEMICOLON
    'å': (e.KEY_LEFTBRACE, False),
    'Å': (e.KEY_LEFTBRACE, True),
    'ø': (e.KEY_APOSTROPHE, False),
    'Ø': (e.KEY_APOSTROPHE, True),
    'æ': (e.KEY_SEMICOLON, False),
    'Æ': (e.KEY_SEMICOLON, True),
}

def send_key(ui: UInput, keycode: int, shift: bool) -> None:
    """Send a single key with optional shift using uinput."""
    if keycode == 0:
        return

    if shift:
        ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
        ui.syn()

    ui.write(e.EV_KEY, keycode, 1)
    ui.syn()
    time.sleep(0.01)

    ui.write(e.EV_KEY, keycode, 0)
    ui.syn()

    if shift:
        ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
        ui.syn()

def send_text(ui: UInput, text: str) -> None:
    """Send a whole string as keystrokes."""
    for ch in text:
        keycode, shift = KEYMAP.get(ch, (0, False))
        if keycode:
            send_key(ui, keycode, shift)
            time.sleep(0.01)

def fifo_thread(ui: UInput) -> None:
    """Read lines from FIFO and send as keystrokes."""
    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)
        os.chmod(FIFO_PATH, 0o666)

    print(f"BT HID daemon: FIFO ready at {FIFO_PATH}")

    while True:
        with open(FIFO_PATH, "r", encoding="utf-8") as fifo:
            for line in fifo:
                text = line.rstrip("\n")
                if not text:
                    continue
                print(f"BT HID daemon received: {text!r}")
                send_text(ui, text)

def main() -> None:
    print("BT HID daemon starting (uinput virtual keyboard)...")
    ui = UInput()  # default keyboard-capable device

    t = threading.Thread(target=fifo_thread, args=(ui,), daemon=True)
    t.start()

    print("BT HID daemon running. Waiting for FIFO input...")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("BT HID daemon shutting down...")

if __name__ == "__main__":
    main()
EOF

sudo chmod +x /usr/local/bin/bt_hid_daemon.py



########################################
# 3. Reference /usr/local/bin/bt_kb_send (do not overwrite)
########################################
echo "=== [13] Skipping creation of /usr/local/bin/bt_kb_send (managed by 03_install_bt_helper.sh) ==="
echo "If you need to update the Bluetooth keyboard helper, edit or reinstall via scripts/03_install_bt_helper.sh."


########################################
# 4. Create systemd service
########################################
echo "=== [13] Writing /etc/systemd/system/bt_hid_daemon.service ==="
sudo tee /etc/systemd/system/bt_hid_daemon.service > /dev/null << 'EOF'
[Unit]
Description=BT HID virtual keyboard daemon (uinput + FIFO)
After=bluetooth.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/bt_hid_daemon.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

echo "=== [13] Enabling and starting bt_hid_daemon.service ==="
sudo systemctl daemon-reload
sudo systemctl enable bt_hid_daemon.service
sudo systemctl restart bt_hid_daemon.service


########################################
# 5. Ensure Bluetooth config is HID-capable (for later BT side work)
########################################
BT_CONF="/etc/bluetooth/main.conf"

if grep -q "^\[General\]" "$BT_CONF" 2>/dev/null; then
  if ! grep -q "^Enable=.*HID" "$BT_CONF" 2>/dev/null; then
    echo "=== [13] Updating $BT_CONF to include Enable=HID (for future BT HID bridge) ==="
    sudo sed -i '/^\[General\]/a Enable=HID' "$BT_CONF" || true
    sudo systemctl restart bluetooth || true
  fi
fi

echo "=== [13] Done. HID daemon + helper installed with Danish mapping. ==="
echo "You can now test locally with:"
echo "  bt_kb_send \"Test æøå ÆØÅ\""
