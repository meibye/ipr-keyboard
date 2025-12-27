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

# Comprehensive list of all relevant ipr-keyboard and BLE GATT/agent services
# (unit, description)
SERVICES = [
    ("ipr_keyboard.service", "Main app: USB→BT bridge, web API, config, logs"),
    ("bt_hid_uinput.service", "Classic BT HID backend (uinput, Linux only)"),
    ("bt_hid_ble.service", "BLE HID backend (GATT, modern devices)"),
    ("bt_hid_daemon.service", "Legacy/alt HID daemon (rarely used)"),
    ("bt_hid_agent_unified.service", "Pairing/authorization agent (all backends)"),
    ("bt_hid_agent.service", "Classic agent (legacy, not default)"),
    ("ipr_backend_manager.service", "Switches/monitors backend daemons"),
]


def get_service_status(svc):
    try:
        out = subprocess.check_output(
            ["systemctl", "is-active", svc], text=True
        ).strip()
        return out
    except Exception:
        return "unknown"


def status_color(status):
    # Map status to color pair index
    if status in ("active", "running"):
        return 2  # green
    elif status in ("failed", "inactive", "dead"):
        return 1  # red
    elif status == "activating":
        return 3  # yellow
    else:
        return 4  # dim/gray


def get_bt_devices():
    # Placeholder: should call bluetoothctl or similar
    # (addr, name, connected, paired)
    # Return empty list to simulate no devices (remove test devices)
    return []


def device_status_color(connected, paired):
    if connected:
        return 2  # green
    elif paired:
        return 3  # yellow
    else:
        return 1  # red


def get_config_info():
    # Placeholder: should read config.json
    return {
        "DeleteFiles": True,
        "KeyboardBackend": "uinput",
        "IrisPenFolder": "/mnt/irispen",
        "LogPort": 8080,
        "Logging": True,
        "MaxFileSize": 1048576,
    }


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
    # Color pairs: 1=red, 2=green, 3=yellow, 4=dim/gray
    has_colors = False
    if curses.has_colors():
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_RED, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_CYAN, -1)
            has_colors = True
        except Exception:
            has_colors = False

    sel_type = "service"
    sel_idx = 0
    status_thread = StatusThread(SERVICES)
    status_thread.start()
    while True:
        stdscr.clear()
        stdscr.addstr(0, 2, "IPR Service Monitor", curses.A_BOLD)
        stdscr.addstr(1, 2, "Navigate: ↑↓  Select: Enter  Quit: q", curses.A_DIM)
        stdscr.addstr(2, 2, f"Delay: {delay}s (+/-)", curses.A_DIM)
        # Service table headers
        stdscr.addstr(4, 2, "Services:", curses.A_UNDERLINE)
        stdscr.addstr(5, 4, "Status", curses.A_BOLD | curses.A_UNDERLINE)
        stdscr.addstr(5, 15, "Service", curses.A_BOLD | curses.A_UNDERLINE)
        stdscr.addstr(5, 45, "Description", curses.A_BOLD | curses.A_UNDERLINE)
        for i, svc in enumerate(SERVICES):
            status = status_thread.status.get(svc[0], "unknown")
            color = status_color(status)
            attr = curses.A_NORMAL
            if has_colors:
                attr |= curses.color_pair(color)
            if sel_type == "service" and sel_idx == i:
                attr |= curses.A_REVERSE
            stdscr.addstr(6 + i, 4, f"{status:8}", attr)
            stdscr.addstr(6 + i, 15, f"{svc[0]:28}", attr)
            stdscr.addstr(6 + i, 45, f"{svc[1]}", attr)

        dev_start = 6 + len(SERVICES) + 2
        stdscr.addstr(dev_start, 2, "Bluetooth Devices:", curses.A_UNDERLINE)
        devices = get_bt_devices()
        if devices:
            for i, dev in enumerate(devices):
                label = f"{dev[1]} ({dev[0]}) [{'Connected' if dev[2] else 'Disconnected'}{'/Paired' if dev[3] else '/Unpaired'}]"
                color = device_status_color(dev[2], dev[3])
                attr = curses.A_NORMAL
                if has_colors:
                    attr |= curses.color_pair(color)
                if sel_type == "device" and sel_idx == i:
                    attr |= curses.A_REVERSE
                stdscr.addstr(dev_start + 1 + i, 4, label, attr)
            device_lines = len(devices)
        else:
            stdscr.addstr(dev_start + 1, 4, "No devices", curses.A_DIM)
            device_lines = 1
        # Config groups below device list
        cfg_start = dev_start + 2 + device_lines
        stdscr.addstr(cfg_start, 2, "Config Groups:", curses.A_UNDERLINE)
        cfg = get_config_info()
        for j, (k, v) in enumerate(cfg.items()):
            stdscr.addstr(cfg_start + 1 + j, 4, f"{k}: {v}", curses.A_DIM)
        diag_start = cfg_start + 2 + len(cfg)
        stdscr.addstr(diag_start, 2, "Diagnostics: c", curses.A_DIM)
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
            if sel_type == "service" and devices:
                sel_type = "device"
                sel_idx = 0
            elif sel_type == "device":
                sel_type = "service"
                sel_idx = 0
        elif c == ord("+"):
            delay = min(delay + 1, 30)
        elif c == ord("-"):
            delay = max(delay - 1, 1)

        elif c == curses.KEY_ENTER or c == 10 or c == 13:
            stdscr.clear()
            if sel_type == "service":
                svc, svc_desc = SERVICES[sel_idx]
                stdscr.addstr(0, 2, f"Service: {svc}", curses.A_BOLD)
                stdscr.addstr(
                    2,
                    2,
                    "Actions: [S]tart [T]op [R]estart [J]ournal [E]nable [D]isable",
                    curses.A_DIM,
                )
                stdscr.addstr(
                    curses.LINES - 1, 2, "Press key for action or any key to return..."
                )
                stdscr.refresh()
                action = stdscr.getch()
                # Implement service actions
                if action in (ord("s"), ord("S")):
                    subprocess.run(["systemctl", "start", svc])
                elif action in (ord("t"), ord("T")):
                    subprocess.run(["systemctl", "stop", svc])
                elif action in (ord("r"), ord("R")):
                    subprocess.run(["systemctl", "restart", svc])
                elif action in (ord("j"), ord("J")):
                    stdscr.clear()
                    stdscr.addstr(0, 2, f"Journal for {svc}", curses.A_BOLD)
                    try:
                        out = subprocess.check_output(
                            ["journalctl", "-u", svc, "-n", "20", "--no-pager"],
                            text=True,
                        )
                        for idx, line in enumerate(
                            out.splitlines()[: curses.LINES - 3]
                        ):
                            stdscr.addstr(2 + idx, 2, line[: curses.COLS - 4])
                    except Exception as e:
                        stdscr.addstr(
                            2,
                            2,
                            f"Error: {e}",
                            curses.A_BOLD | (curses.color_pair(1) if has_colors else 0),
                        )
                    stdscr.addstr(curses.LINES - 1, 2, "Press any key to return...")
                    stdscr.refresh()
                    stdscr.getch()
                elif action in (ord("e"), ord("E")):
                    subprocess.run(["systemctl", "enable", svc])
                elif action in (ord("d"), ord("D")):
                    subprocess.run(["systemctl", "disable", svc])
            elif sel_type == "device" and devices:
                dev = devices[sel_idx]
                stdscr.addstr(0, 2, f"Bluetooth Device: {dev[1]}", curses.A_BOLD)
                stdscr.addstr(
                    2,
                    2,
                    "Actions: [C]onnect [D]isconnect [R]emove [I]nfo [P]air [U]ntrust",
                    curses.A_DIM,
                )
                stdscr.addstr(
                    curses.LINES - 1, 2, "Press key for action or any key to return..."
                )
                stdscr.refresh()
                action = stdscr.getch()
                # Implement Bluetooth device actions (placeholders)
                addr = dev[0]
                if action in (ord("c"), ord("C")):
                    subprocess.run(["bluetoothctl", "connect", addr])
                elif action in (ord("d"), ord("D")):
                    subprocess.run(["bluetoothctl", "disconnect", addr])
                elif action in (ord("r"), ord("R")):
                    subprocess.run(["bluetoothctl", "remove", addr])
                elif action in (ord("i"), ord("I")):
                    stdscr.clear()
                    stdscr.addstr(0, 2, f"Device Info: {dev[1]}", curses.A_BOLD)
                    stdscr.addstr(2, 2, f"Address: {dev[0]}")
                    stdscr.addstr(3, 2, f"Connected: {dev[2]}")
                    stdscr.addstr(4, 2, f"Paired: {dev[3]}")
                    stdscr.addstr(curses.LINES - 1, 2, "Press any key to return...")
                    stdscr.refresh()
                    stdscr.getch()
                elif action in (ord("p"), ord("P")):
                    subprocess.run(["bluetoothctl", "pair", addr])
                elif action in (ord("u"), ord("U")):
                    subprocess.run(["bluetoothctl", "untrust", addr])


delay = 5
if __name__ == "__main__":
    curses.wrapper(main, delay)
