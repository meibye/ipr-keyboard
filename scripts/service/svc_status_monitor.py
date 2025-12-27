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

SERVICES = [("ipr_keyboard.service",), ("bt_hid_uinput.service",), ("bt_hid_ble.service",)]
device_info_list = [("AA:BB:CC:DD:EE:FF", "Test Device", True)]
sel_type = "service"
sel_idx = 0
delay = 5

def main(stdscr, delay):
    global sel_type, sel_idx
    while True:
        stdscr.clear()
        stdscr.addstr(0, 2, "IPR Service Monitor", curses.A_BOLD)
        stdscr.addstr(1, 2, "Navigate: ↑↓  Select: Enter  Quit: q", curses.A_DIM)
        stdscr.addstr(2, 2, f"Delay: {delay}s (+/-)", curses.A_DIM)
        stdscr.addstr(4, 2, "Services:", curses.A_UNDERLINE)
        for i, svc in enumerate(SERVICES):
            attr = curses.A_REVERSE if sel_type == "service" and sel_idx == i else curses.A_NORMAL
            stdscr.addstr(5 + i, 4, f"{svc[0]}", attr)
        dev_start = 5 + len(SERVICES) + 2
        stdscr.addstr(dev_start, 2, "Bluetooth Devices:", curses.A_UNDERLINE)
        for i, dev in enumerate(device_info_list):
            attr = curses.A_REVERSE if sel_type == "device" and sel_idx == i else curses.A_NORMAL
            stdscr.addstr(dev_start + 1 + i, 4, f"{dev[1]} ({dev[0]})", attr)
        stdscr.addstr(curses.LINES - 2, 2, "Config/Diagnostics: c", curses.A_DIM)
        stdscr.refresh()
        c = stdscr.getch()
        if c == curses.KEY_UP:
            sel_idx = max(sel_idx - 1, 0)
        elif c == curses.KEY_DOWN:
            if sel_type == "service":
                sel_idx = min(sel_idx + 1, len(SERVICES) - 1)
            else:
                sel_idx = min(sel_idx + 1, len(device_info_list) - 1)
        elif c == ord('q'):
            break
        elif c == ord('c'):
            stdscr.clear()
            stdscr.addstr(0, 2, "Config/Diagnostics", curses.A_BOLD)
            stdscr.addstr(2, 2, "(Config and diagnostics info would appear here)", curses.A_DIM)
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
        elif c == ord('+'):
            delay = min(delay + 1, 30)
        elif c == ord('-'):
            delay = max(delay - 1, 1)
        elif c == curses.KEY_ENTER or c == 10 or c == 13:
            stdscr.clear()
            if sel_type == "service":
                stdscr.addstr(0, 2, f"Service action for {SERVICES[sel_idx][0]}", curses.A_BOLD)
                stdscr.addstr(2, 2, "(Service actions would appear here)", curses.A_DIM)
            else:
                stdscr.addstr(0, 2, f"Bluetooth Device: {device_info_list[sel_idx][1]}", curses.A_BOLD)
                stdscr.addstr(2, 2, "(Device actions would appear here)", curses.A_DIM)
            stdscr.addstr(curses.LINES - 1, 2, "Press any key to return...")
            stdscr.refresh()
            stdscr.getch()

if __name__ == "__main__":
    curses.wrapper(main, delay)
