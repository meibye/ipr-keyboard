#!/usr/bin/env bash
#
# ipr-keyboard Bluetooth HID Daemon Install Script
#
# Purpose:
#   Installs and configures a Bluetooth HID daemon for advanced keyboard emulation.
#   Optional alternative to the default bt_kb_send helper.
#
# Usage:
#   sudo ./scripts/ble_install_daemon.sh
#
# Prerequisites:
#   - Must be run as root (uses sudo)
#   - Environment variables set (sources env_set_variables.sh)
#
# Note:
#   This script is OPTIONAL. The main Bluetooth helper is installed by ble_install_helper.sh.
#   Use only if you need an additional HID daemon with a separate FIFO.

set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/env_set_variables.sh"

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

echo "=== [ble_install_daemon] Install / update Bluetooth HID daemon ==="

########################################
# 1. Install system dependencies
########################################
echo "=== [ble_install_daemon] Installing system packages ==="
apt update
apt install -y \
    python3 \
    python3-pip \
    python3-evdev \
    bluez \
    bluez-tools


########################################
# 2. Create /usr/local/bin/bt_hid_daemon.py
########################################
echo "=== [ble_install_daemon] Writing /usr/local/bin/bt_hid_daemon.py ==="
cat > /usr/local/bin/bt_hid_daemon.py << 'PYTHONEOF'
#!/usr/bin/env python3
"""
bt_hid_daemon.py

Backend daemon for HID keyboard emulation via uinput.

Responsibilities:
  - Create /run/bt_keyboard_fifo if it does not exist.
  - Create a uinput virtual keyboard device.
  - Read UTF-8 text lines from the FIFO.
  - Map characters to evdev key codes (with Danish layout support).
  - Emit key events on the virtual keyboard.
"""

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
PYTHONEOF

chmod +x /usr/local/bin/bt_hid_daemon.py

########################################
# 3. Note about bt_kb_send
########################################
echo "=== [ble_install_daemon] Skipping creation of /usr/local/bin/bt_kb_send ==="
echo "The Bluetooth keyboard helper is managed by ble_install_helper.sh."

########################################
# 4. Create systemd service
########################################
echo "=== [ble_install_daemon] Writing /etc/systemd/system/bt_hid_daemon.service ==="
cat > /etc/systemd/system/bt_hid_daemon.service << 'EOF'
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

echo "=== [ble_install_daemon] Enabling and starting bt_hid_daemon.service ==="
systemctl daemon-reload
systemctl enable bt_hid_daemon.service
systemctl restart bt_hid_daemon.service

########################################
# 5. Ensure Bluetooth config is HID-capable
########################################
BT_CONF="/etc/bluetooth/main.conf"

if grep -q "^\[General\]" "$BT_CONF" 2>/dev/null; then
  if ! grep -q "^Enable=.*HID" "$BT_CONF" 2>/dev/null; then
    echo "=== [ble_install_daemon] Updating $BT_CONF to include Enable=HID ==="
    sed -i '/^\[General\]/a Enable=HID' "$BT_CONF" || true
    systemctl restart bluetooth || true
  fi
fi

echo "=== [ble_install_daemon] Done. HID daemon installed with Danish mapping. ==="
echo "You can now test locally with:"
echo "  bt_kb_send \"Test æøå ÆØÅ\""
