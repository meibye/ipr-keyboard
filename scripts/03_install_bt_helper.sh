
#!/usr/bin/env bash
set -euo pipefail

# Load environment variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/00_set_env.sh"

#
# 03_install_bt_helper.sh
#
# Install the Bluetooth keyboard helper and backend daemons.
#
# This script installs:
#   - /usr/local/bin/bt_kb_send
#       → writes text into a FIFO (/run/ipr_bt_keyboard_fifo)
#   - /usr/local/bin/bt_hid_uinput_daemon.py
#       → reads FIFO and types on the Pi via uinput (local virtual keyboard)
#   - /usr/local/bin/bt_hid_ble_daemon.py
#       → scaffold for a future BLE HID over GATT implementation
#   - systemd units:
#       * bt_hid_uinput.service
#       * bt_hid_ble.service
#
# The active backend is controlled via:
#   - Config:  KeyboardBackend in config.json ("uinput" or "ble")
#   - Service: enable/disable the corresponding systemd service
#
# By default this script enables the uinput backend.
#

FIFO_PATH="/run/ipr_bt_keyboard_fifo"
HELPER_PATH="/usr/local/bin/bt_kb_send"
UINPUT_DAEMON="/usr/local/bin/bt_hid_uinput_daemon.py"
BLE_DAEMON="/usr/local/bin/bt_hid_ble_daemon.py"

echo "=== [03] Installing Bluetooth keyboard helper and backends ==="

########################################
# 1. Install system dependencies
########################################
echo "=== [03] Installing OS packages (python3, evdev, bluez) ==="
sudo apt update
sudo apt install -y \
  python3 \
  python3-pip \
  python3-evdev \
  bluez \
  bluez-tools

########################################
# 2. Create helper script: bt_kb_send
########################################
echo "=== [03] Writing $HELPER_PATH ==="
sudo tee "$HELPER_PATH" > /dev/null << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

FIFO="/run/ipr_bt_keyboard_fifo"

if [[ ! -p "$FIFO" ]]; then
  echo "bt_kb_send: FIFO $FIFO not found or not a pipe" >&2
  exit 1
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: bt_kb_send \"text to send\"" >&2
  exit 1
fi

TEXT="$*"
printf '%s\n' "$TEXT" > "$FIFO"
EOF

sudo chmod +x "$HELPER_PATH"

########################################
# 3. Create uinput backend daemon
########################################
echo "=== [03] Writing $UINPUT_DAEMON ==="
sudo tee "$UINPUT_DAEMON" > /dev/null << 'EOF'
#!/usr/bin/env python3
"""
bt_hid_uinput_daemon.py

Backend daemon for the "uinput" keyboard backend.

Responsibilities:
  - Create /run/ipr_bt_keyboard_fifo if it does not exist.
  - Create a uinput virtual keyboard device.
  - Read UTF-8 text lines from the FIFO.
  - Map characters to evdev key codes (with Danish layout support).
  - Emit key events on the virtual keyboard (local typing on the Pi).
"""

import os
import time
import threading
from evdev import UInput, ecodes as e

FIFO_PATH = "/run/ipr_bt_keyboard_fifo"

# Map characters to (evdev keycode, shift_required)
KEYMAP = {
    # Letters
    "a": (e.KEY_A, False), "A": (e.KEY_A, True),
    "b": (e.KEY_B, False), "B": (e.KEY_B, True),
    "c": (e.KEY_C, False), "C": (e.KEY_C, True),
    "d": (e.KEY_D, False), "D": (e.KEY_D, True),
    "e": (e.KEY_E, False), "E": (e.KEY_E, True),
    "f": (e.KEY_F, False), "F": (e.KEY_F, True),
    "g": (e.KEY_G, False), "G": (e.KEY_G, True),
    "h": (e.KEY_H, False), "H": (e.KEY_H, True),
    "i": (e.KEY_I, False), "I": (e.KEY_I, True),
    "j": (e.KEY_J, False), "J": (e.KEY_J, True),
    "k": (e.KEY_K, False), "K": (e.KEY_K, True),
    "l": (e.KEY_L, False), "L": (e.KEY_L, True),
    "m": (e.KEY_M, False), "M": (e.KEY_M, True),
    "n": (e.KEY_N, False), "N": (e.KEY_N, True),
    "o": (e.KEY_O, False), "O": (e.KEY_O, True),
    "p": (e.KEY_P, False), "P": (e.KEY_P, True),
    "q": (e.KEY_Q, False), "Q": (e.KEY_Q, True),
    "r": (e.KEY_R, False), "R": (e.KEY_R, True),
    "s": (e.KEY_S, False), "S": (e.KEY_S, True),
    "t": (e.KEY_T, False), "T": (e.KEY_T, True),
    "u": (e.KEY_U, False), "U": (e.KEY_U, True),
    "v": (e.KEY_V, False), "V": (e.KEY_V, True),
    "w": (e.KEY_W, False), "W": (e.KEY_W, True),
    "x": (e.KEY_X, False), "X": (e.KEY_X, True),
    "y": (e.KEY_Y, False), "Y": (e.KEY_Y, True),
    "z": (e.KEY_Z, False), "Z": (e.KEY_Z, True),

    # Digits
    "0": (e.KEY_0, False),
    "1": (e.KEY_1, False),
    "2": (e.KEY_2, False),
    "3": (e.KEY_3, False),
    "4": (e.KEY_4, False),
    "5": (e.KEY_5, False),
    "6": (e.KEY_6, False),
    "7": (e.KEY_7, False),
    "8": (e.KEY_8, False),
    "9": (e.KEY_9, False),

    # Space and newline
    " ": (e.KEY_SPACE, False),
    "\n": (e.KEY_ENTER, False),
    "\r": (e.KEY_ENTER, False),

    # Danish letters (assuming Danish keyboard layout on the Pi):
    #   å / Å  → key right of P      → KEY_LEFTBRACE
    #   ø / Ø  → key right of Å      → KEY_APOSTROPHE
    #   æ / Æ  → key right of L      → KEY_SEMICOLON
    "å": (e.KEY_LEFTBRACE, False),
    "Å": (e.KEY_LEFTBRACE, True),
    "ø": (e.KEY_APOSTROPHE, False),
    "Ø": (e.KEY_APOSTROPHE, True),
    "æ": (e.KEY_SEMICOLON, False),
    "Æ": (e.KEY_SEMICOLON, True),
}


def send_key(ui: UInput, keycode: int, shift: bool) -> None:
    """Emit a single key press + release, with optional shift."""
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
    """Emit a sequence of key events for the given text."""
    for ch in text:
        keycode, shift = KEYMAP.get(ch, (0, False))
        if keycode:
            send_key(ui, keycode, shift)
            time.sleep(0.01)


def fifo_worker(ui: UInput) -> None:
    """Worker thread that reads lines from the FIFO and types them."""
    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)
        os.chmod(FIFO_PATH, 0o666)

    print(f"[uinput] FIFO ready at {FIFO_PATH}")

    while True:
        with open(FIFO_PATH, "r", encoding="utf-8") as fifo:
            for line in fifo:
                text = line.rstrip("\n")
                if not text:
                    continue
                print(f"[uinput] Received text: {text!r}")
                send_text(ui, text)


def main() -> None:
    print("[uinput] Starting uinput virtual keyboard daemon...")
    ui = UInput()  # create a default keyboard-capable device
    thread = threading.Thread(target=fifo_worker, args=(ui,), daemon=True)
    thread.start()

    print("[uinput] Daemon running. Waiting for FIFO input...")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("[uinput] Shutting down.")


if __name__ == "__main__":
    main()
EOF

sudo chmod +x "$UINPUT_DAEMON"

########################################
# 4. Create BLE HID backend scaffold
########################################
echo "=== [03] Writing $BLE_DAEMON (scaffold) ==="
sudo tee "$BLE_DAEMON" > /dev/null << 'EOF'
#!/usr/bin/env python3
"""
bt_hid_ble_daemon.py

Scaffold for the "ble" keyboard backend (BLE HID over GATT).

This file is intentionally minimal: it wires the FIFO reading loop and
logs incoming text, but the actual BLE HID GATT implementation using
BlueZ D-Bus is left as a future enhancement.

Once implemented, this daemon should:
  - Register a BLE HID GATT service with BlueZ (HID service 0x1812).
  - Advertise as a BLE keyboard.
  - Map text to HID usage IDs and modifiers.
  - Send HID input reports to the connected central via notifications.
"""

import os
import time

FIFO_PATH = "/run/ipr_bt_keyboard_fifo"


def main() -> None:
    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)
        os.chmod(FIFO_PATH, 0o666)

    print("[ble] BLE HID daemon scaffold starting.")
    print("[ble] NOTE: BLE HID over GATT is not yet implemented. "
          "Incoming text will only be logged.")

    while True:
        with open(FIFO_PATH, "r", encoding="utf-8") as fifo:
            for line in fifo:
                text = line.rstrip("\\n")
                if not text:
                    continue
                print(f"[ble] Would send via BLE HID: {text!r}")
                # TODO: Implement actual BLE HID GATT logic here.
                time.sleep(0.01)


if __name__ == "__main__":
    main()
EOF

sudo chmod +x "$BLE_DAEMON"

########################################
# 5. Systemd units for both backends
########################################
echo "=== [03] Writing systemd units ==="

sudo tee /etc/systemd/system/bt_hid_uinput.service > /dev/null << 'EOF'
[Unit]
Description=IPR Bluetooth HID (uinput backend)
After=bluetooth.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/bt_hid_uinput_daemon.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/bt_hid_ble.service > /dev/null << 'EOF'
[Unit]
Description=IPR Bluetooth HID (BLE HID over GATT backend - scaffold)
After=bluetooth.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/bt_hid_ble_daemon.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

echo "=== [03] Reloading systemd and enabling uinput backend by default ==="
sudo systemctl daemon-reload
sudo systemctl disable bt_hid_ble.service || true
sudo systemctl enable bt_hid_uinput.service
sudo systemctl restart bt_hid_uinput.service

echo "=== [03] Installation complete. ==="
echo "  - Helper:        $HELPER_PATH"
echo "  - FIFO:          $FIFO_PATH"
echo "  - Backends:      uinput (active), ble (scaffold only)"
echo "To switch backend later, use the switch script (e.g. scripts/14_switch_keyboard_backend.sh)."
