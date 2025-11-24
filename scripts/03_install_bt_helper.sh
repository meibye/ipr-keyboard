#!/usr/bin/env bash
#
# 03_install_bt_helper.sh
#
# Install Bluetooth Keyboard Helper Script and backend daemons.
#
# Installs:
#   - /usr/local/bin/bt_kb_send
#       → writes text into /run/ipr_bt_keyboard_fifo
#   - /usr/local/bin/bt_hid_uinput_daemon.py
#       → reads FIFO, types on the Pi via uinput (local virtual keyboard)
#   - /usr/local/bin/bt_hid_ble_daemon.py
#       → BLE HID over GATT daemon structure (BlueZ-based)
#   - systemd services:
#       * bt_hid_uinput.service
#       * bt_hid_ble.service
#
# The active backend is controlled by:
#   - KeyboardBackend in config.json ("uinput" or "ble")
#   - Enabling/disabling the corresponding systemd units
#

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

FIFO_PATH="/run/ipr_bt_keyboard_fifo"
HELPER_PATH="/usr/local/bin/bt_kb_send"
UINPUT_DAEMON="/usr/local/bin/bt_hid_uinput_daemon.py"
BLE_DAEMON="/usr/local/bin/bt_hid_ble_daemon.py"

echo "=== [03] Installing Bluetooth keyboard helper and backends ==="

########################################
# 1. Install system dependencies
########################################
echo "=== [03] Installing OS packages (python3, evdev, bluez, dbus) ==="
apt update
apt install -y \
  python3 \
  python3-pip \
  python3-evdev \
  python3-dbus \
  bluez \
  bluez-tools

########################################
# 2. Create helper script: bt_kb_send
########################################
echo "=== [03] Writing $HELPER_PATH ==="
cat > "$HELPER_PATH" << 'EOF'
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

chmod +x "$HELPER_PATH"

########################################
# 3. Create uinput backend daemon
########################################
echo "=== [03] Writing $UINPUT_DAEMON ==="
cat > "$UINPUT_DAEMON" << 'EOF'
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

    # Danish letters (Danish keyboard layout on the Pi):
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

chmod +x "$UINPUT_DAEMON"

########################################
# 4. Create BLE HID backend daemon (structured)
########################################
echo "=== [03] Writing $BLE_DAEMON ==="
cat > "$BLE_DAEMON" << 'EOF'
#!/usr/bin/env python3
"""
bt_hid_ble_daemon.py

Structured backend daemon for the "ble" keyboard backend (BLE HID over GATT).

This daemon:
  - Creates /run/ipr_bt_keyboard_fifo if needed.
  - Connects to BlueZ over D-Bus.
  - Registers a minimal BLE HID GATT service skeleton (HID service 0x1812).
  - Reads text from the FIFO.
  - Maps characters to HID usage IDs and modifier bits (Danish-aware).
  - Prepares HID input reports.

NOTE:
  The D-Bus / BlueZ GATT plumbing for sending notifications is highly
  environment-specific. This file provides a structured starting point with
  clear extension points for your actual HID report transmission logic.

You should:
  - Ensure bluetoothd is running with experimental features enabled if needed.
  - Pair the PC with the Pi as a BLE device.
  - Extend `BleHidServer.send_input_report` to actually call into BlueZ,
    e.g. via a custom GATT characteristic's Notify method.
"""

import os
import time
from typing import Tuple

FIFO_PATH = "/run/ipr_bt_keyboard_fifo"

# --- HID Usage and modifier mapping (Danish) -------------------------------

# Modifier bits for HID keyboard
MOD_LCTRL = 0x01
MOD_LSHIFT = 0x02
MOD_LALT = 0x04
MOD_LGUI = 0x08
MOD_RCTRL = 0x10
MOD_RSHIFT = 0x20
MOD_RALT = 0x40  # often used as AltGr
MOD_RGUI = 0x80

# Basic US-like HID usage IDs for letters a-z
# Usage IDs for 'a'..'z' are 0x04..0x1d
LETTER_USAGES = {
    "a": 0x04, "b": 0x05, "c": 0x06, "d": 0x07,
    "e": 0x08, "f": 0x09, "g": 0x0A, "h": 0x0B,
    "i": 0x0C, "j": 0x0D, "k": 0x0E, "l": 0x0F,
    "m": 0x10, "n": 0x11, "o": 0x12, "p": 0x13,
    "q": 0x14, "r": 0x15, "s": 0x16, "t": 0x17,
    "u": 0x18, "v": 0x19, "w": 0x1A, "x": 0x1B,
    "y": 0x1C, "z": 0x1D,
}

# Simple mapping: char → (usage_id, modifier_bits)
def map_char_to_hid(ch: str) -> Tuple[int, int]:
    """Map a Unicode character to HID usage + modifiers.

    This assumes:
      - The host PC uses a Danish keyboard layout.
      - We emit usages corresponding to the *physical* key positions.
    """
    # Newline/Enter
    if ch in ("\n", "\r"):
        return 0x28, 0x00  # ENTER

    # Space
    if ch == " ":
        return 0x2C, 0x00  # SPACE

    # Letters
    if ch.lower() in LETTER_USAGES:
        usage = LETTER_USAGES[ch.lower()]
        mods = MOD_LSHIFT if ch.isupper() else 0x00
        return usage, mods

    # Digits 0-9
    if ch.isdigit():
        # HID: 0x27 = '0', 0x1E-0x26 = '1'-'9'
        if ch == "0":
            return 0x27, 0x00
        else:
            return 0x1E + (ord(ch) - ord("1")), 0x00

    # Danish special letters.
    # On a Danish keyboard (physical layout):
    #   Å is top row, right of P
    #   Ø is to right of Å
    #   Æ is to right of L
    # These map to the corresponding HID usages for those key positions.
    # Here we approximate using the US positions for [ ; ' ] combined
    # with the PC's Danish layout to render the correct glyph.
    if ch in ("å", "Å"):
        # Physical key right of P → US '['  (0x2F)
        usage = 0x2F
        mods = MOD_LSHIFT if ch.isupper() else 0x00
        return usage, mods

    if ch in ("ø", "Ø"):
        # Physical key right of Å → US '\'' (0x34)
        usage = 0x34
        mods = MOD_LSHIFT if ch.isupper() else 0x00
        return usage, mods

    if ch in ("æ", "Æ"):
        # Physical key right of L → US ';' (0x33)
        usage = 0x33
        mods = MOD_LSHIFT if ch.isupper() else 0x00
        return usage, mods

    # Fallback: ignore character
    return 0x00, 0x00


def make_key_report(usage: int, mods: int) -> bytes:
    """Build an 8-byte HID input report for a single key press."""
    # [mods, reserved, key1, key2, key3, key4, key5, key6]
    return bytes([mods, 0x00, usage, 0x00, 0x00, 0x00, 0x00, 0x00])


def make_key_release_report() -> bytes:
    """Build an 8-byte HID input report for key release (all keys up)."""
    return b"\x00\x00\x00\x00\x00\x00\x00\x00"


# --- BLE HID Server skeleton ----------------------------------------------


class BleHidServer:
    """Skeleton for a BLE HID over GATT server.

    This class is deliberately minimal and does not implement the full
    BlueZ D-Bus interaction. Instead, it provides a clear API for sending
    HID input reports and a place to integrate your D-Bus code.

    Extend:
      - __init__ to connect to BlueZ and register a GATT app + advertisement.
      - send_input_report to actually notify the host via the Input Report
        characteristic.
    """

    def __init__(self) -> None:
        # TODO: connect to system bus, BlueZ, and register GATT application.
        print("[ble] BleHidServer initialised (skeleton).")

    def send_input_report(self, report: bytes) -> None:
        """Send a HID input report to the connected host.

        Currently only logs; you should extend this to call into BlueZ.
        """
        print(f"[ble] Would send HID report ({len(report)} bytes): {report!r}")
        # TODO: Implement BlueZ D-Bus GATT notification here.


def process_text(hid: BleHidServer, text: str) -> None:
    """Convert text to HID reports and send via BleHidServer."""
    for ch in text:
        usage, mods = map_char_to_hid(ch)
        if usage == 0x00:
            continue
        down = make_key_report(usage, mods)
        up = make_key_release_report()
        hid.send_input_report(down)
        # Small delay so host sees distinct press/release
        time.sleep(0.01)
        hid.send_input_report(up)
        time.sleep(0.005)


def main() -> None:
    if not os.path.exists(FIFO_PATH):
        os.mkfifo(FIFO_PATH)
        os.chmod(FIFO_PATH, 0o666)

    print("[ble] BLE HID daemon starting.")
    print(f"[ble] FIFO at: {FIFO_PATH}")
    print("[ble] NOTE: BlueZ D-Bus integration needs to be completed in "
          "BleHidServer.send_input_report().")

    hid = BleHidServer()

    while True:
        with open(FIFO_PATH, "r", encoding="utf-8") as fifo:
            for line in fifo:
                text = line.rstrip("\n")
                if not text:
                    continue
                print(f"[ble] Received text: {text!r}")
                process_text(hid, text)


if __name__ == "__main__":
    main()
EOF

chmod +x "$BLE_DAEMON"

########################################
# 5. Systemd units for both backends
########################################
echo "=== [03] Writing systemd units ==="

cat > /etc/systemd/system/bt_hid_uinput.service << 'EOF'
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

cat > /etc/systemd/system/bt_hid_ble.service << 'EOF'
[Unit]
Description=IPR Bluetooth HID (BLE HID over GATT backend)
After=bluetooth.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/bt_hid_ble_daemon.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

echo "=== [03] Reloading systemd and enabling uinput backend by default ==="
systemctl daemon-reload
systemctl disable bt_hid_ble.service || true
systemctl enable bt_hid_uinput.service
systemctl restart bt_hid_uinput.service

echo "=== [03] Installation complete. ==="
echo "  - Helper:        $HELPER_PATH"
echo "  - FIFO:          $FIFO_PATH"
echo "  - Backends:      uinput (active), ble (structured skeleton)"
echo "To switch backend later, use scripts/15_switch_keyboard_backend.sh."
EOF
