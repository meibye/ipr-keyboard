#!/usr/bin/env python3
"""
svc_status_monitor.py
Interactive TUI for ipr-keyboard service/daemon status and control.
Requires: python3, curses, systemctl, journalctl
"""

import curses
import subprocess
import sys
import time


def get_status(service):
    try:
        out = subprocess.check_output(
            ["systemctl", "is-active", service], text=True
        ).strip()
        return out if out else "unknown"
    except subprocess.CalledProcessError:
        return "unknown"


SERVICES = [
    ("ipr_keyboard.service", "Main Application", "both"),
    ("bt_hid_uinput.service", "UInput HID Daemon", "uinput"),
    ("bt_hid_ble.service", "BLE HID Daemon", "ble"),
    ("bt_hid_agent.service", "BLE Pairing Agent", "ble"),
    ("ipr_backend_manager.service", "Backend Manager", "both"),
]

ACTIONS = ["Start", "Stop", "Restart", "Journal"]

COLOR_STATUS = {
    "active": 2,  # green
    "inactive": 3,  # yellow
    "failed": 1,  # red
    "disabled": 1,  # red
    "unknown": 4,  # cyan
}

BACKEND_LABELS = [
    ("uinput", "UINPUT Backend Services"),
    ("ble", "BLE Backend Services"),
    ("both", "Services for Both Backends"),
]


def draw_table(stdscr, selected, delay):
    stdscr.clear()
    stdscr.addstr(
        0, 2, "IPR-KEYBOARD SERVICE STATUS MONITOR (Python TUI)", curses.A_BOLD
    )
    stdscr.addstr(
        1,
        2,
        f"Delay: {delay}s   [Arrows: Move] [Enter: Action] [q: Quit] [r: Refresh] [+/-: Adjust delay]",
        curses.A_DIM,
    )
    row = 3
    idx = 0
    svc_col = 4
    for backend, label in BACKEND_LABELS:
        stdscr.addstr(row, 2, label, curses.A_BOLD | curses.color_pair(4))
        row += 1
        stdscr.addstr(
            row,
            svc_col,
            f"{'Service':<28}{'Status':<12}{'Description'}",
            curses.A_UNDERLINE,
        )
        row += 1
        for svc, desc, svc_backend in SERVICES:
            if backend == svc_backend or (backend == "both" and svc_backend == "both"):
                status = get_status(svc)
                color = curses.color_pair(COLOR_STATUS.get(status, 4))
                marker = ">" if idx == selected else " "
                stdscr.addstr(
                    row,
                    svc_col,
                    f"{marker} {svc:<26} {status:<12} {desc}",
                    color | (curses.A_REVERSE if idx == selected else 0),
                )
                row += 1
                idx += 1
        row += 1
    stdscr.refresh()


def select_action(stdscr, svc):
    stdscr.clear()
    stdscr.addstr(0, 2, f"Actions for {svc}", curses.A_BOLD)
    for i, action in enumerate(ACTIONS):
        stdscr.addstr(i + 2, 4, f"{i + 1}. {action}")
    stdscr.addstr(len(ACTIONS) + 3, 2, "Select action [1-4] or [q] to cancel: ")
    stdscr.refresh()
    while True:
        c = stdscr.getch()
        if c in (ord("q"), ord("Q")):
            return None
        if c in (ord("1"), ord("2"), ord("3"), ord("4")):
            return ACTIONS[c - ord("1")]


def show_journal(stdscr, svc):
    stdscr.clear()
    stdscr.addstr(0, 2, f"Journal for {svc} (last 20 lines)", curses.A_BOLD)
    try:
        out = subprocess.check_output(
            ["journalctl", "-u", svc, "-n", "20", "--no-pager"],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except subprocess.CalledProcessError as e:
        out = e.output
    lines = out.splitlines()
    for i, line in enumerate(lines[: curses.LINES - 3]):
        stdscr.addstr(i + 2, 2, line[: curses.COLS - 4])
    stdscr.addstr(curses.LINES - 1, 2, "Press any key to return...")
    stdscr.refresh()
    stdscr.getch()


def main(stdscr):
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_CYAN, -1)
    delay = 2
    selected = 0
    total = len(SERVICES)
    while True:
        draw_table(stdscr, selected, delay)
        c = stdscr.getch()
        if c in (ord("q"), ord("Q")):
            break
        elif c in (ord("r"), ord("R")):
            continue
        elif c == curses.KEY_UP:
            selected = (selected - 1) % total
        elif c == curses.KEY_DOWN:
            selected = (selected + 1) % total
        elif c == curses.KEY_ENTER or c == 10 or c == 13:
            svc, desc, backend = SERVICES[selected]
            action = select_action(stdscr, svc)
            if action == "Start":
                subprocess.call(["sudo", "systemctl", "start", svc])
            elif action == "Stop":
                subprocess.call(["sudo", "systemctl", "stop", svc])
            elif action == "Restart":
                subprocess.call(["sudo", "systemctl", "restart", svc])
            elif action == "Journal":
                show_journal(stdscr, svc)
        elif c == ord("+"):
            delay = min(delay + 1, 30)
        elif c == ord("-"):
            delay = max(delay - 1, 1)
        time.sleep(delay)


if __name__ == "__main__":
    delay = 2
    if len(sys.argv) > 1:
        try:
            delay = max(1, int(sys.argv[1]))
        except Exception:
            pass
    curses.wrapper(lambda stdscr: main(stdscr, delay))
