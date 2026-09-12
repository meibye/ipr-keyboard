#!/usr/bin/env python3
"""True pen-to-PC latency probe.  Run this on the PC that receives the keystrokes.

The device can only measure up to the point where text is handed to the BLE
daemon.  Everything after that -- the HID report going over the air, the PC's
Bluetooth stack, the input queue -- is invisible to it.  This probe closes the
gap by putting BOTH timestamps on the PC's own clock:

  t0  the probe tells the device (over SSH) to write a scan file
  t1  the probe sees the first character of that scan arrive on its own stdin

t1 - t0 is the figure a user actually experiences.  No clock synchronisation
between PC and device is needed, because the device's clock is never used.

Usage:
    python scripts/perf/perf_keystroke_probe.py --host ipr-prod [--count 5]

Then click into THIS terminal window so it has keyboard focus: the Bluetooth
keyboard types into whatever is focused, and the probe reads its own stdin.

Requirements: the device is paired and connected to this PC as a keyboard,
ssh <host> works without a password prompt, and the device's IrisPen folder is
writable by that SSH user.  Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time

MARKER = "Q"  # first char of every payload; rare in normal text, easy to spot


# ---------------------------------------------------------------------------
# Raw single-character stdin, without third-party packages
# ---------------------------------------------------------------------------
if os.name == "nt":
    import msvcrt

    def _read_char(timeout: float) -> str | None:
        end = time.time() + timeout
        while time.time() < end:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                return ch
            time.sleep(0.001)
        return None

    def _raw_mode():  # no-op context manager on Windows
        class _C:
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return _C()
else:
    import select
    import termios
    import tty

    class _raw_mode:
        def __enter__(self):
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            return self

        def __exit__(self, *a):
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)
            return False

    def _read_char(timeout: float) -> str | None:
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        return sys.stdin.read(1) if r else None


def _drain(seconds: float = 0.3) -> None:
    """Swallow anything already queued so a previous run cannot leak into this one."""
    end = time.time() + seconds
    while time.time() < end:
        if _read_char(0.02) is None:
            break


# ---------------------------------------------------------------------------
# Device side, over SSH
# ---------------------------------------------------------------------------
def _ssh(host: str, cmd: str, timeout: float = 15) -> str:
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", host, cmd],
        capture_output=True, text=True, timeout=timeout, check=True,
    ).stdout


def _device_folder(host: str, repo: str) -> str:
    cmd = (
        f"python3 -c \"import json,os; p='{repo}/config.json'; "
        f"p=p if os.path.exists(p) else '{repo}/config.default.json'; "
        f"f=json.load(open(p)).get('IrisPenFolders') or []; print(f[0] if f else '')\""
    )
    folder = _ssh(host, cmd).strip()
    if not folder:
        sys.exit("device has no IrisPenFolders configured")
    return folder


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", required=True, help="ssh alias of the device, e.g. ipr-prod")
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--chars", type=int, default=20, help="payload length per scan")
    ap.add_argument("--timeout", type=float, default=30.0, help="max seconds to wait per scan")
    ap.add_argument("--repo", default="~/dev/ipr-keyboard", help="repo path on the device")
    ap.add_argument("--json", action="store_true", help="machine-readable result")
    args = ap.parse_args()

    folder = _device_folder(args.host, args.repo)
    if not args.json:
        print(f"device folder : {folder}")
        print(f"payload       : {MARKER} + {args.chars - 1} chars, {args.count} scans")
        print()
        print(">>> Click into this window now so the Bluetooth keyboard types here. <<<")
        print("    Starting in 3 s ...")
        time.sleep(3)

    results: list[dict] = []
    with _raw_mode():
        for i in range(1, args.count + 1):
            _drain()
            payload = MARKER + ("x" * (args.chars - 1))
            fname = f"{folder}/probe_{int(time.time() * 1000)}_{i}.txt"

            t0 = time.perf_counter()
            _ssh(args.host, f"printf '%s\\n' '{payload}' > '{fname}'")
            t_written = time.perf_counter()

            first = last = None
            got = 0
            deadline = t0 + args.timeout
            while time.perf_counter() < deadline:
                ch = _read_char(0.05)
                if ch is None:
                    if first is not None and got >= args.chars:
                        break
                    continue
                now = time.perf_counter()
                if first is None:
                    if ch != MARKER:
                        continue  # stray key; wait for our marker
                    first = now
                got += 1
                last = now
                if got >= args.chars:
                    break

            if first is None:
                results.append({"n": i, "ok": False, "ssh_ms": (t_written - t0) * 1000})
                if not args.json:
                    print(f"  {i:2d}: TIMEOUT after {args.timeout}s -- is this window focused and the device connected?")
                continue

            r = {
                "n": i,
                "ok": True,
                "ssh_ms": round((t_written - t0) * 1000, 1),
                "first_char_ms": round((first - t0) * 1000, 1),
                "last_char_ms": round((last - t0) * 1000, 1),
                "chars": got,
                "ms_per_char": round((last - first) * 1000 / max(1, got - 1), 2),
            }
            results.append(r)
            if not args.json:
                print(f"  {i:2d}: first char {r['first_char_ms']:7.0f} ms   all {got} chars {r['last_char_ms']:7.0f} ms"
                      f"   ({r['ms_per_char']:.1f} ms/char, ssh overhead {r['ssh_ms']:.0f} ms)")
            time.sleep(1.0)

    ok = [r for r in results if r["ok"]]
    summary = {"host": args.host, "count": args.count, "ok": len(ok), "results": results}
    if ok:
        fc = [r["first_char_ms"] for r in ok]
        lc = [r["last_char_ms"] for r in ok]
        pc = [r["ms_per_char"] for r in ok]
        summary["first_char_ms"] = {"p50": statistics.median(fc), "min": min(fc), "max": max(fc)}
        summary["last_char_ms"] = {"p50": statistics.median(lc), "min": min(lc), "max": max(lc)}
        summary["ms_per_char_p50"] = statistics.median(pc)

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print()
        if ok:
            print(f"pen -> first keystroke on PC : median {summary['first_char_ms']['p50']:.0f} ms"
                  f"  (min {summary['first_char_ms']['min']:.0f}, max {summary['first_char_ms']['max']:.0f})")
            print(f"pen -> last keystroke on PC  : median {summary['last_char_ms']['p50']:.0f} ms")
            print(f"typing rate                  : {summary['ms_per_char_p50']:.1f} ms/char")
            print()
            print("Note: 'first keystroke' includes the device's poll interval (PollIntervalSeconds),")
            print("so it varies by up to that much between runs. The ssh overhead is subtracted from nothing --")
            print("it is part of t0 -> written, which the pen would not incur; compare ssh_ms to judge it.")
        else:
            print("no scans arrived. Check: window focused, device paired+connected, folder writable.")
    return 0 if len(ok) == args.count else 1


if __name__ == "__main__":
    sys.exit(main())
