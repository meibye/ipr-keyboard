#!/usr/bin/env python3
"""
svc_status_monitor.py

Interactive TUI for ipr-keyboard service/daemon status and control.
Includes diagnostic information from diag_status.sh and diag_troubleshoot.sh.

Usage:
  sudo ./scripts/service/svc_status_monitor.py

Prerequisites:
  - Must be run as root
  - python3, curses, systemctl, journalctl must be available

category: Service
purpose: Interactive TUI for monitoring and controlling services

Requires: python3, curses, systemctl, journalctl
"""

import curses
import subprocess
import threading
import time

SERVICES = [
    ("ipr_keyboard.service", "IPR Keyboard"),
    ("bt_hid_uinput.service", "BT HID UInput"),
    ("bt_hid_ble.service", "BT HID BLE"),
]


def get_service_status(svc):
    try:
        out = subprocess.check_output(
            ["systemctl", "is-active", svc], text=True
        ).strip()
        return out
    except Exception:
        return "unknown"


def get_bt_devices():
    # Placeholder: should call bluetoothctl or similar
    return [
        ("AA:BB:CC:DD:EE:FF", "Test Device", True),
        ("11:22:33:44:55:66", "Other Device", False),
    ]


def get_config_info():
    # Placeholder: should read config.json
    return {"DeleteFiles": True, "KeyboardBackend": "uinput"}


def get_diag_info():
    # Placeholder: should call diag_status.sh/diag_troubleshoot.sh
    return "Diagnostics OK"


class StatusThread(threading.Thread):
    def __init__(self, services):
        super().__init__(daemon=True)
        self.services = services
        self.status = {svc[0]: "unknown" for svc in services}
        self.running = True

    def run(self):
        while self.running:
            for svc in self.services:
                self.status[svc[0]] = get_service_status(svc[0])
            time.sleep(2)

    def stop(self):
        self.running = False


def main(stdscr, delay):
    sel_type = "service"
    sel_idx = 0
    status_thread = StatusThread(SERVICES)
    status_thread.start()
    while True:
        stdscr.clear()
        stdscr.addstr(0, 2, "IPR Service Monitor", curses.A_BOLD)
        stdscr.addstr(1, 2, "Navigate: ↑↓  Select: Enter  Quit: q", curses.A_DIM)
        stdscr.addstr(2, 2, f"Delay: {delay}s (+/-)", curses.A_DIM)
        stdscr.addstr(4, 2, "Services:", curses.A_UNDERLINE)
        for i, svc in enumerate(SERVICES):
            status = status_thread.status.get(svc[0], "unknown")
            label = f"{svc[1]} [{status}]"
            attr = (
                curses.A_REVERSE
                if sel_type == "service" and sel_idx == i
                else curses.A_NORMAL
            )
            stdscr.addstr(5 + i, 4, label, attr)
        dev_start = 5 + len(SERVICES) + 2
        stdscr.addstr(dev_start, 2, "Bluetooth Devices:", curses.A_UNDERLINE)
        devices = get_bt_devices()
        for i, dev in enumerate(devices):
            label = f"{dev[1]} ({dev[0]}) [{'Connected' if dev[2] else 'Disconnected'}]"
            attr = (
                curses.A_REVERSE
                if sel_type == "device" and sel_idx == i
                else curses.A_NORMAL
            )
            stdscr.addstr(dev_start + 1 + i, 4, label, attr)
        cfg_start = dev_start + 2 + len(devices)
        stdscr.addstr(cfg_start, 2, "Config/Diagnostics: c", curses.A_DIM)
        stdscr.refresh()
        c = stdscr.getch()
        if c == curses.KEY_UP:
            sel_idx = max(sel_idx - 1, 0)
        elif c == curses.KEY_DOWN:
            if sel_type == "service":
                sel_idx = min(sel_idx + 1, len(SERVICES) - 1)
            else:
                sel_idx = min(sel_idx + 1, len(devices) - 1)
        elif c == ord("q"):
            status_thread.stop()
            break
        elif c == ord("c"):
            stdscr.clear()
            stdscr.addstr(0, 2, "Config/Diagnostics", curses.A_BOLD)
            cfg = get_config_info()
            diag = get_diag_info()
            stdscr.addstr(2, 2, f"Config: {cfg}", curses.A_DIM)
            stdscr.addstr(3, 2, f"Diagnostics: {diag}", curses.A_DIM)
            stdscr.addstr(curses.LINES - 1, 2, "Press any key to return...")
            stdscr.refresh()
            stdscr.getch()
        elif c == curses.KEY_RIGHT or c == curses.KEY_LEFT:
            if sel_type == "service":
                sel_type = "device"
                sel_idx = 0
            else:
                sel_type = "service"
                sel_idx = 0
        elif c == ord("+"):
            delay = min(delay + 1, 30)
        elif c == ord("-"):
            delay = max(delay - 1, 1)
        elif c == curses.KEY_ENTER or c == 10 or c == 13:
            stdscr.clear()
            if sel_type == "service":
                svc = SERVICES[sel_idx][0]
                stdscr.addstr(0, 2, f"Service: {svc}", curses.A_BOLD)
                stdscr.addstr(
                    2, 2, "Actions: [S]tart [T]op [R]estart [J]ournal", curses.A_DIM
                )
                stdscr.addstr(
                    curses.LINES - 1, 2, "Press key for action or any key to return..."
                )
                stdscr.refresh()
                action = stdscr.getch()
                # Placeholder: handle actions
            elif sel_type == "device":
                dev = devices[sel_idx]
                stdscr.addstr(0, 2, f"Bluetooth Device: {dev[1]}", curses.A_BOLD)
                stdscr.addstr(
                    2,
                    2,
                    "Actions: [C]onnect [D]isconnect [R]emove [I]nfo",
                    curses.A_DIM,
                )
                stdscr.addstr(
                    curses.LINES - 1, 2, "Press key for action or any key to return..."
                )
                stdscr.refresh()
                action = stdscr.getch()
                # Placeholder: handle actions


delay = 5
if __name__ == "__main__":
    curses.wrapper(main, delay)
