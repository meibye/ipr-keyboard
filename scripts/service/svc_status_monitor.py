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
import json
import os
import subprocess
import sys
import threading
import time


def get_status(service):
    try:
        out = subprocess.check_output(
            ["systemctl", "is-active", service], text=True
        ).strip()
        return out if out else "unknown"
    except subprocess.CalledProcessError:
        return "unknown"


def get_diagnostic_info():
    """Gather diagnostic information from various sources."""
    info = {}

    # Backend selection
    try:
        if os.path.exists("/etc/ipr-keyboard/backend"):
            with open("/etc/ipr-keyboard/backend", "r") as f:
                info["backend_file"] = f.read().strip()
        else:
            info["backend_file"] = "not found"
    except Exception:
        info["backend_file"] = "error reading"

    # Config file backend
    try:
        config_path = os.path.expanduser("~/dev/ipr-keyboard/config.json")
        if not os.path.exists(config_path):
            # Try alternate locations
            for alt_path in [
                "/home/*/dev/ipr-keyboard/config.json",
                "./config.json",
                "../config.json",
            ]:
                matches = subprocess.check_output(
                    f"ls {alt_path} 2>/dev/null || true", shell=True, text=True
                ).strip()
                if matches:
                    config_path = matches.split("\n")[0]
                    break

        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
                info["config_backend"] = config.get("KeyboardBackend", "not set")
                info["config_path"] = config_path
        else:
            info["config_backend"] = "config not found"
            info["config_path"] = "not found"
    except Exception as e:
        info["config_backend"] = f"error: {str(e)[:30]}"
        info["config_path"] = "error"

    # Bluetooth adapter status
    try:
        bt_show = subprocess.check_output(
            ["bluetoothctl", "show"], text=True, stderr=subprocess.DEVNULL
        )
        info["bt_powered"] = "yes" if "Powered: yes" in bt_show else "no"
        info["bt_discoverable"] = "yes" if "Discoverable: yes" in bt_show else "no"
        info["bt_pairable"] = "yes" if "Pairable: yes" in bt_show else "no"
    except Exception:
        info["bt_powered"] = "unknown"
        info["bt_discoverable"] = "unknown"
        info["bt_pairable"] = "unknown"

    # Paired devices count
    try:
        devices = subprocess.check_output(
            ["bluetoothctl", "devices"], text=True, stderr=subprocess.DEVNULL
        )
        info["paired_devices"] = (
            len(devices.strip().split("\n")) if devices.strip() else 0
        )
    except Exception:
        info["paired_devices"] = "unknown"

    # FIFO pipe status
    try:
        if os.path.exists("/run/ipr_bt_keyboard_fifo"):
            stat_info = os.stat("/run/ipr_bt_keyboard_fifo")
            import stat

            info["fifo_exists"] = (
                "yes (pipe)" if stat.S_ISFIFO(stat_info.st_mode) else "yes (not pipe!)"
            )
        else:
            info["fifo_exists"] = "no"
    except Exception:
        info["fifo_exists"] = "error"

    # bt_kb_send helper
    info["bt_kb_send"] = "yes" if os.path.exists("/usr/local/bin/bt_kb_send") else "no"

    # Web API status (check if port 8080 is listening)
    try:
        ss_out = subprocess.check_output(
            ["ss", "-tln"], text=True, stderr=subprocess.DEVNULL
        )
        info["web_api"] = "listening" if ":8080 " in ss_out else "not listening"
    except Exception:
        info["web_api"] = "unknown"

    return info


SERVICES = [
    ("bluetooth.target", "System Bluetooth", "both"),
    ("ipr_keyboard.service", "Main Application", "both"),
    ("bt_hid_agent.service", "BLE Pairing Agent", "both"),
    ("bt_hid_uinput.service", "UInput HID Daemon", "uinput"),
    ("bt_hid_daemon.service", "BT HID virtual keyboard daemon", "legacy"),
    ("bt_hid_ble.service", "BLE HID Daemon", "ble"),
    ("ipr_backend_manager.service", "Backend Switch Manager", "both"),
]

ACTIONS = ["Start", "Stop", "Restart", "Journal", "Diagnostics"]

COLOR_STATUS = {
    "active": 2,  # green
    "inactive": 3,  # yellow
    "failed": 1,  # red
    "disabled": 1,  # red
    "unknown": 4,  # cyan
}

BACKEND_LABELS = [
    ("uinput", "UINPUT Backend Services"),
    ("legacy", "Legacy/advanced Services"),
    ("ble", "BLE Backend Services"),
    ("both", "Services for Both Backends"),
]


def show_diagnostics(stdscr):
    """Display diagnostics using diag_troubleshoot.sh or diag_status.sh in a scrollable window."""
    stdscr.clear()
    stdscr.addstr(
        0,
        2,
        "System Diagnostics (diag_troubleshoot.sh)",
        curses.A_BOLD | curses.color_pair(4),
    )
    stdscr.refresh()
    try:
        # Try diag_troubleshoot.sh, fallback to diag_status.sh
        diag_script = (
            "./scripts/diag_troubleshoot.sh"
            if os.path.exists("./scripts/diag_troubleshoot.sh")
            else "./scripts/diag_status.sh"
        )
        proc = subprocess.Popen(
            [diag_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=False,
        )
        output, _ = proc.communicate(timeout=30)
    except Exception as e:
        output = f"Error running diagnostics: {e}"
    lines = output.splitlines()
    max_y, max_x = stdscr.getmaxyx()
    pos = 0
    while True:
        stdscr.clear()
        stdscr.addstr(
            0,
            2,
            "System Diagnostics (diag_troubleshoot.sh)",
            curses.A_BOLD | curses.color_pair(4),
        )
        for i in range(1, max_y - 2):
            idx = pos + i - 1
            if idx < len(lines):
                stdscr.addstr(i, 2, lines[idx][: max_x - 4])
        stdscr.addstr(
            max_y - 1,
            2,
            f"Up/Down: Scroll  q: Quit diagnostics  ({pos + 1}-{min(pos + max_y - 2, len(lines))}/{len(lines)})",
            curses.A_DIM,
        )
        stdscr.refresh()
        c = stdscr.getch()
        if c in (ord("q"), ord("Q")):
            break
        elif c == curses.KEY_DOWN and pos < len(lines) - (max_y - 2):
            pos += 1
        elif c == curses.KEY_UP and pos > 0:
            pos -= 1


def draw_table(
    stdscr, selected, delay, status_snapshot, diag_info=None, selectable_indices=None
):
    stdscr.clear()
    stdscr.addstr(
        0, 2, "IPR-KEYBOARD SERVICE STATUS MONITOR (Python TUI)", curses.A_BOLD
    )
    stdscr.addstr(
        1,
        2,
        f"Delay: {delay}s   [Arrows: Move] [Enter: Action] [d: Diagnostics] [q: Quit] [r: Refresh] [+/-: Adjust]",
        curses.A_DIM,
    )
    row = 3
    idx = 0
    svc_col = 4
    if selectable_indices is not None:
        selectable_indices.clear()
    for backend, label in BACKEND_LABELS:
        stdscr.addstr(row, 2, label, curses.A_BOLD | curses.color_pair(4))
        row += 1
        stdscr.addstr(
            row,
            svc_col,
            f"{'Service':<34}{'Status':<12}{'Description'}",
            curses.A_UNDERLINE,
        )
        row += 1
        for svc_idx, (svc, desc, svc_backend) in enumerate(SERVICES):
            if backend == svc_backend or (backend == "both" and svc_backend == "both"):
                status = status_snapshot.get(svc, "unknown")
                color = curses.color_pair(COLOR_STATUS.get(status, 4))
                marker = ">" if idx == selected else " "
                stdscr.addstr(
                    row,
                    svc_col,
                    f"{marker} {svc:<31} {status:<12} {desc}",
                    color | (curses.A_REVERSE if idx == selected else 0),
                )
                if selectable_indices is not None:
                    selectable_indices.append(svc_idx)
                row += 1
                idx += 1
        row += 1

    # Show diagnostic info at the bottom if available
    if diag_info and row < curses.LINES - 8:
        row += 1
        stdscr.addstr(
            row, 2, "System Diagnostics", curses.A_BOLD | curses.color_pair(4)
        )
        row += 1
        diag_lines = [
            f"Backend (file): {diag_info.get('backend_file', 'unknown')}  "
            f"Backend (config): {diag_info.get('config_backend', 'unknown')}",
            f"BT Powered: {diag_info.get('bt_powered', 'unknown')}  "
            f"Discoverable: {diag_info.get('bt_discoverable', 'unknown')}  "
            f"Pairable: {diag_info.get('bt_pairable', 'unknown')}",
            f"Paired devices: {diag_info.get('paired_devices', 'unknown')}  "
            f"FIFO: {diag_info.get('fifo_exists', 'unknown')}  "
            f"bt_kb_send: {diag_info.get('bt_kb_send', 'unknown')}",
            f"Web API: {diag_info.get('web_api', 'unknown')}",
        ]
        for line in diag_lines:
            if row < curses.LINES - 1:
                stdscr.addstr(row, 4, line[: curses.COLS - 6], curses.A_DIM)
                row += 1

    stdscr.refresh()


def show_journal(stdscr, svc):
    """Display the systemd journal for a given service in a scrollable window."""
    stdscr.clear()
    stdscr.addstr(
        0,
        2,
        f"Systemd Journal for {svc}",
        curses.A_BOLD | curses.color_pair(4),
    )
    stdscr.refresh()
    try:
        proc = subprocess.Popen(
            ["journalctl", "-u", svc, "--no-pager", "-n", "1000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        output, _ = proc.communicate(timeout=20)
    except Exception as e:
        output = f"Error reading journal: {e}"
    lines = output.splitlines()
    max_y, max_x = stdscr.getmaxyx()
    pos = 0
    while True:
        stdscr.clear()
        stdscr.addstr(
            0,
            2,
            f"Systemd Journal for {svc}",
            curses.A_BOLD | curses.color_pair(4),
        )
        for i in range(1, max_y - 2):
            idx = pos + i - 1
            if idx < len(lines):
                stdscr.addstr(i, 2, lines[idx][: max_x - 4])
        stdscr.addstr(
            max_y - 1,
            2,
            f"Up/Down: Scroll  q: Quit journal  ({pos + 1}-{min(pos + max_y - 2, len(lines))}/{len(lines)})",
            curses.A_DIM,
        )
        stdscr.refresh()
        c = stdscr.getch()
        if c in (ord("q"), ord("Q")):
            break
        elif c == curses.KEY_DOWN and pos < len(lines) - (max_y - 2):
            pos += 1
        elif c == curses.KEY_UP and pos > 0:
            pos -= 1


def select_action(stdscr, svc):
    """Prompt user to select an action for the given service."""
    actions = ACTIONS
    selected = 0
    while True:
        stdscr.clear()
        stdscr.addstr(
            0, 2, f"Select action for {svc}:", curses.A_BOLD | curses.color_pair(4)
        )
        for idx, action in enumerate(actions):
            marker = ">" if idx == selected else " "
            stdscr.addstr(
                2 + idx,
                4,
                f"{marker} {action}",
                curses.A_REVERSE if idx == selected else 0,
            )
        stdscr.addstr(
            len(actions) + 3,
            2,
            "Up/Down: Move  Enter: Select  Esc/q: Cancel",
            curses.A_DIM,
        )
        stdscr.refresh()
        c = stdscr.getch()
        if c in (curses.KEY_UP, ord("k")):
            selected = (selected - 1) % len(actions)
        elif c in (curses.KEY_DOWN, ord("j")):
            selected = (selected + 1) % len(actions)
        elif c in (curses.KEY_ENTER, 10, 13):
            return actions[selected]
        elif c in (27, ord("q"), ord("Q")):  # Esc or q
            return None


def main(stdscr, delay):
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_CYAN, -1)
    selected = 0
    selectable_indices = []

    status_snapshot = {svc: "unknown" for svc, _, _ in SERVICES}
    diag_info = {}
    status_lock = threading.Lock()
    redraw_event = threading.Event()
    stop_event = threading.Event()

    def poll_status():
        nonlocal diag_info
        while not stop_event.is_set():
            changed = False
            with status_lock:
                for svc, _, _ in SERVICES:
                    new_status = get_status(svc)
                    if status_snapshot.get(svc) != new_status:
                        status_snapshot[svc] = new_status
                        changed = True
                # Update diagnostics every poll cycle
                try:
                    diag_info = get_diagnostic_info()
                except Exception:
                    pass
            if changed:
                redraw_event.set()
            time.sleep(delay)

    poll_thread = threading.Thread(target=poll_status, daemon=True)
    poll_thread.start()

    # Initial diagnostic gather
    try:
        diag_info = get_diagnostic_info()
    except Exception:
        pass

    draw_table(stdscr, selected, delay, status_snapshot, diag_info, selectable_indices)
    while True:
        if redraw_event.is_set():
            with status_lock:
                draw_table(
                    stdscr,
                    selected,
                    delay,
                    status_snapshot,
                    diag_info,
                    selectable_indices,
                )
            redraw_event.clear()
        c = stdscr.getch()
        if c == -1:
            time.sleep(0.05)
            continue
        if c in (ord("q"), ord("Q")):
            stop_event.set()
            break
        elif c in (ord("d"), ord("D")):
            show_diagnostics(stdscr)
            with status_lock:
                draw_table(
                    stdscr,
                    selected,
                    delay,
                    status_snapshot,
                    diag_info,
                    selectable_indices,
                )
        elif c in (ord("r"), ord("R")):
            with status_lock:
                try:
                    diag_info = get_diagnostic_info()
                except Exception:
                    pass
                draw_table(
                    stdscr,
                    selected,
                    delay,
                    status_snapshot,
                    diag_info,
                    selectable_indices,
                )
        elif c == curses.KEY_UP:
            selected = (selected - 1) % len(selectable_indices)
            with status_lock:
                draw_table(
                    stdscr,
                    selected,
                    delay,
                    status_snapshot,
                    diag_info,
                    selectable_indices,
                )
        elif c == curses.KEY_DOWN:
            selected = (selected + 1) % len(selectable_indices)
            with status_lock:
                draw_table(
                    stdscr,
                    selected,
                    delay,
                    status_snapshot,
                    diag_info,
                    selectable_indices,
                )
        elif c == curses.KEY_ENTER or c == 10 or c == 13:
            if not selectable_indices:
                continue
            svc_idx = selectable_indices[selected]
            svc, desc, backend = SERVICES[svc_idx]
            action = select_action(stdscr, svc)
            (stdscr, svc)

            def run_action(cmd):
                try:
                    subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
                    return None
                except subprocess.CalledProcessError as e:
                    return e.output

            error_msg = None
            if action == "Start":
                error_msg = run_action(["sudo", "systemctl", "start", svc])
                with status_lock:
                    status_snapshot[svc] = get_status(svc)
                redraw_event.set()
            elif action == "Stop":
                error_msg = run_action(["sudo", "systemctl", "stop", svc])
                with status_lock:
                    status_snapshot[svc] = get_status(svc)
                redraw_event.set()
            elif action == "Restart":
                error_msg = run_action(["sudo", "systemctl", "restart", svc])
                with status_lock:
                    status_snapshot[svc] = get_status(svc)
                redraw_event.set()
            elif action == "Journal":
                show_journal(stdscr, svc)
                with status_lock:
                    draw_table(
                        stdscr,
                        selected,
                        delay,
                        status_snapshot,
                        diag_info,
                        selectable_indices,
                    )
            elif action == "Diagnostics":
                show_diagnostics(stdscr)
                with status_lock:
                    draw_table(
                        stdscr,
                        selected,
                        delay,
                        status_snapshot,
                        diag_info,
                        selectable_indices,
                    )
            if error_msg:
                stdscr.clear()
                stdscr.addstr(
                    0,
                    2,
                    f"Error running {action} for {svc}",
                    curses.A_BOLD | curses.color_pair(1),
                )
                lines = error_msg.splitlines()
                for i, line in enumerate(lines[: curses.LINES - 3]):
                    stdscr.addstr(i + 2, 2, line[: curses.COLS - 4])
                stdscr.addstr(curses.LINES - 1, 2, "Press any key to return...")
                stdscr.refresh()
                stdscr.getch()
        elif c == ord("+"):
            delay = min(delay + 1, 30)
        elif c == ord("-"):
            delay = max(delay - 1, 1)
            # No sleep here; input is responsive
            show_diagnostics(stdscr)
            with status_lock:
                draw_table(stdscr, selected, delay, status_snapshot, diag_info)
        elif c in (ord("r"), ord("R")):
            with status_lock:
                try:
                    diag_info = get_diagnostic_info()
                except Exception:
                    pass
                draw_table(stdscr, selected, delay, status_snapshot, diag_info)
        elif c == curses.KEY_UP:
            selected = (selected - 1) % len(selectable_indices)
            with status_lock:
                draw_table(stdscr, selected, delay, status_snapshot, diag_info)
        elif c == curses.KEY_DOWN:
            selected = (selected + 1) % len(selectable_indices)
            with status_lock:
                draw_table(stdscr, selected, delay, status_snapshot, diag_info)
        elif c == curses.KEY_ENTER or c == 10 or c == 13:
            svc, desc, backend = SERVICES[selected]
            action = select_action(stdscr, svc)

            def run_action(cmd):
                try:
                    subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
                    return None
                except subprocess.CalledProcessError as e:
                    return e.output

            error_msg = None
            if action == "Start":
                error_msg = run_action(["sudo", "systemctl", "start", svc])
                with status_lock:
                    status_snapshot[svc] = get_status(svc)
                redraw_event.set()
            elif action == "Stop":
                error_msg = run_action(["sudo", "systemctl", "stop", svc])
                with status_lock:
                    status_snapshot[svc] = get_status(svc)
                redraw_event.set()
            elif action == "Restart":
                error_msg = run_action(["sudo", "systemctl", "restart", svc])
                with status_lock:
                    status_snapshot[svc] = get_status(svc)
                redraw_event.set()
            elif action == "Journal":
                show_journal(stdscr, svc)
                with status_lock:
                    draw_table(stdscr, selected, delay, status_snapshot, diag_info)
            elif action == "Diagnostics":
                show_diagnostics(stdscr)
                with status_lock:
                    draw_table(stdscr, selected, delay, status_snapshot, diag_info)
            if error_msg:
                stdscr.clear()
                stdscr.addstr(
                    0,
                    2,
                    f"Error running {action} for {svc}",
                    curses.A_BOLD | curses.color_pair(1),
                )
                lines = error_msg.splitlines()
                for i, line in enumerate(lines[: curses.LINES - 3]):
                    stdscr.addstr(i + 2, 2, line[: curses.COLS - 4])
                stdscr.addstr(curses.LINES - 1, 2, "Press any key to return...")
                stdscr.refresh()
                stdscr.getch()
        elif c == ord("+"):
            delay = min(delay + 1, 30)
        elif c == ord("-"):
            delay = max(delay - 1, 1)
        # No sleep here; input is responsive


if __name__ == "__main__":
    delay = 2
    if len(sys.argv) > 1:
        try:
            delay = max(1, int(sys.argv[1]))
        except Exception:
            pass
    curses.wrapper(lambda stdscr: main(stdscr, delay))
