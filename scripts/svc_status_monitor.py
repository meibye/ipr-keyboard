#!/usr/bin/env python3
"""
svc_status_monitor.py
Interactive TUI for ipr-keyboard service/daemon status and control.
Includes diagnostic information from diag_status.sh and diag_troubleshoot.sh.
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
    except:
        info["backend_file"] = "error reading"
    
    # Config file backend
    try:
        config_path = os.path.expanduser("~/dev/ipr-keyboard/config.json")
        if not os.path.exists(config_path):
            # Try alternate locations
            for alt_path in ["/home/*/dev/ipr-keyboard/config.json", "./config.json", "../config.json"]:
                matches = subprocess.check_output(f"ls {alt_path} 2>/dev/null || true", shell=True, text=True).strip()
                if matches:
                    config_path = matches.split('\n')[0]
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
        bt_show = subprocess.check_output(["bluetoothctl", "show"], text=True, stderr=subprocess.DEVNULL)
        info["bt_powered"] = "yes" if "Powered: yes" in bt_show else "no"
        info["bt_discoverable"] = "yes" if "Discoverable: yes" in bt_show else "no"
        info["bt_pairable"] = "yes" if "Pairable: yes" in bt_show else "no"
    except:
        info["bt_powered"] = "unknown"
        info["bt_discoverable"] = "unknown"
        info["bt_pairable"] = "unknown"
    
    # Paired devices count
    try:
        devices = subprocess.check_output(["bluetoothctl", "devices"], text=True, stderr=subprocess.DEVNULL)
        info["paired_devices"] = len(devices.strip().split('\n')) if devices.strip() else 0
    except:
        info["paired_devices"] = "unknown"
    
    # FIFO pipe status
    try:
        if os.path.exists("/run/ipr_bt_keyboard_fifo"):
            stat_info = os.stat("/run/ipr_bt_keyboard_fifo")
            import stat
            info["fifo_exists"] = "yes (pipe)" if stat.S_ISFIFO(stat_info.st_mode) else "yes (not pipe!)"
        else:
            info["fifo_exists"] = "no"
    except:
        info["fifo_exists"] = "error"
    
    # bt_kb_send helper
    info["bt_kb_send"] = "yes" if os.path.exists("/usr/local/bin/bt_kb_send") else "no"
    
    # Web API status (check if port 8080 is listening)
    try:
        ss_out = subprocess.check_output(["ss", "-tln"], text=True, stderr=subprocess.DEVNULL)
        info["web_api"] = "listening" if ":8080 " in ss_out else "not listening"
    except:
        info["web_api"] = "unknown"
    
    return info


SERVICES = [
    ("ipr_keyboard.service", "Main Application", "both"),
    ("bt_hid_agent.service", "BLE Pairing Agent", "both"),
    ("bt_hid_uinput.service", "UInput HID Daemon", "uinput"),
    ("bt_hid_daemon.service", "BT HID virtual keyboard daemon", "uinput"),
    ("bt_hid_ble.service", "BLE HID Daemon", "ble"),
    ("ipr_backend_manager.service", "Backend Manager \(controls BT type switch\)", "both"),
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
    ("ble", "BLE Backend Services"),
    ("both", "Services for Both Backends"),
]


def draw_table(stdscr, selected, delay, status_snapshot, diag_info=None):
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
        for svc, desc, svc_backend in SERVICES:
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
                row += 1
                idx += 1
        row += 1
    
    # Show diagnostic info at the bottom if available
    if diag_info and row < curses.LINES - 8:
        row += 1
        stdscr.addstr(row, 2, "System Diagnostics", curses.A_BOLD | curses.color_pair(4))
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
                stdscr.addstr(row, 4, line[:curses.COLS - 6], curses.A_DIM)
                row += 1
    
    stdscr.refresh()


def select_action(stdscr, svc):
    stdscr.clear()
    stdscr.addstr(0, 2, f"Actions for {svc}", curses.A_BOLD)
    for i, action in enumerate(ACTIONS):
        stdscr.addstr(i + 2, 4, f"{i + 1}. {action}")
    stdscr.addstr(len(ACTIONS) + 3, 2, f"Select action [1-{len(ACTIONS)}] or [q] to cancel: ")
    stdscr.refresh()
    while True:
        c = stdscr.getch()
        if c in (ord("q"), ord("Q")):
            return None
        if ord("1") <= c <= ord(str(len(ACTIONS))):
            return ACTIONS[c - ord("1")]


def show_diagnostics(stdscr):
    """Show full diagnostic information."""
    stdscr.clear()
    stdscr.addstr(0, 2, "System Diagnostics (Full)", curses.A_BOLD)
    try:
        diag_info = get_diagnostic_info()
        lines = [
            "",
            "Backend Configuration:",
            f"  File (/etc/ipr-keyboard/backend): {diag_info.get('backend_file', 'unknown')}",
            f"  Config (config.json): {diag_info.get('config_backend', 'unknown')}",
            f"  Config path: {diag_info.get('config_path', 'unknown')}",
            "",
            "Bluetooth Adapter:",
            f"  Powered: {diag_info.get('bt_powered', 'unknown')}",
            f"  Discoverable: {diag_info.get('bt_discoverable', 'unknown')}",
            f"  Pairable: {diag_info.get('bt_pairable', 'unknown')}",
            f"  Paired devices: {diag_info.get('paired_devices', 'unknown')}",
            "",
            "System Components:",
            f"  FIFO pipe (/run/ipr_bt_keyboard_fifo): {diag_info.get('fifo_exists', 'unknown')}",
            f"  bt_kb_send helper (/usr/local/bin/bt_kb_send): {diag_info.get('bt_kb_send', 'unknown')}",
            f"  Web API (port 8080): {diag_info.get('web_api', 'unknown')}",
            "",
        ]
        for i, line in enumerate(lines):
            if i + 2 < curses.LINES - 1:
                stdscr.addstr(i + 2, 2, line[:curses.COLS - 4])
    except Exception as e:
        stdscr.addstr(2, 2, f"Error gathering diagnostics: {str(e)}")
    stdscr.addstr(curses.LINES - 1, 2, "Press any key to return...")
    stdscr.refresh()
    stdscr.getch()


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


def main(stdscr, delay):
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_CYAN, -1)
    selected = 0
    total = len(SERVICES)

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
                except:
                    pass
            if changed:
                redraw_event.set()
            time.sleep(delay)

    poll_thread = threading.Thread(target=poll_status, daemon=True)
    poll_thread.start()

    # Initial diagnostic gather
    try:
        diag_info = get_diagnostic_info()
    except:
        pass

    draw_table(stdscr, selected, delay, status_snapshot, diag_info)
    while True:
        if redraw_event.is_set():
            with status_lock:
                draw_table(stdscr, selected, delay, status_snapshot, diag_info)
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
                draw_table(stdscr, selected, delay, status_snapshot, diag_info)
        elif c in (ord("r"), ord("R")):
            with status_lock:
                try:
                    diag_info = get_diagnostic_info()
                except:
                    pass
                draw_table(stdscr, selected, delay, status_snapshot, diag_info)
        elif c == curses.KEY_UP:
            selected = (selected - 1) % total
            with status_lock:
                draw_table(stdscr, selected, delay, status_snapshot, diag_info)
        elif c == curses.KEY_DOWN:
            selected = (selected + 1) % total
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
