#!/usr/bin/env python3
"""Cross-platform KPI comparison.  Run on the PC; pulls /api/metrics from each
device and prints one table with the three boards side by side.

    python scripts/perf/perf_report.py ipr-dev-pi4 ipr-prod-zero2 ipr-prod-zero

Each argument is an ssh alias.  The script reads the dashboard credentials
from IPR_USER / IPR_PASS (defaults: admin / the device's
admin_initial_password.txt if still present) and talks to the device over an
ssh tunnel, so nothing but ssh needs to be reachable from the PC.

Devices that are off, or have metrics disabled, get a column that says so
rather than aborting the whole report.  Add --json for machine-readable output
suitable for keeping a history of runs.

Standard library only.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import ssl
import http.cookiejar

ROWS = [
    ("boot_to_process_s",  "Boot -> app process",     "s"),
    ("detect_latency_ms",  "Pen file -> detected",    "ms"),
    ("read_ms",            "Read file",               "ms"),
    ("send_ms",            "Hand to BLE daemon",      "ms"),
    ("send_ms_per_char",   "  per character",         "ms"),
    ("e2e_latency_ms",     "Pen -> BLE (device e2e)", "ms"),
    ("poll_scan_ms",       "Idle poll cost",          "ms"),
    ("sse_build_ms",       "Dashboard update cost",   "ms"),
]


def _ssh(host: str, cmd: str, timeout: float = 15) -> str:
    return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, cmd],
                          capture_output=True, text=True, timeout=timeout, check=True).stdout


def fetch(host: str, repo: str) -> dict:
    """Return the /api/metrics document, or {"error": ...}."""
    try:
        port = _ssh(host, f"python3 -c \"import json,os; p='{repo}/config.json'; "
                          f"p=p if os.path.exists(p) else '{repo}/config.default.json'; "
                          f"print(json.load(open(p)).get('LogPort', 8080))\"").strip()
    except Exception as e:
        return {"error": f"unreachable ({type(e).__name__})"}

    user = os.environ.get("IPR_USER", "admin")
    pw = os.environ.get("IPR_PASS")
    if not pw:
        try:
            pw = _ssh(host, f"cat {repo}/admin_initial_password.txt 2>/dev/null").strip()
        except Exception:
            pw = ""
    if not pw:
        return {"error": "no credentials (set IPR_PASS)"}

    # Fetch through the device itself over ssh: avoids needing the port open to
    # the PC and sidesteps mDNS entirely.
    script = (
        "import json,ssl,urllib.request,http.cookiejar\n"
        f"base='https://localhost:{port}'\n"
        "ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE\n"
        "cj=http.cookiejar.CookieJar()\n"
        "op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj), urllib.request.HTTPSHandler(context=ctx))\n"
        f"req=urllib.request.Request(base+'/api/auth/login', data=json.dumps({{'username':'{user}','password':'{pw}'}}).encode(), headers={{'Content-Type':'application/json'}})\n"
        "op.open(req, timeout=10).read()\n"
        "print(op.open(base+'/api/metrics', timeout=10).read().decode())\n"
    )
    try:
        out = _ssh(host, f"python3 -c {json.dumps(script)}", timeout=30)
        return json.loads(out)
    except subprocess.CalledProcessError as e:
        return {"error": f"api call failed: {e.stderr.strip()[-120:]}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def cell(doc: dict, key: str) -> str:
    if "error" in doc:
        return "—"
    if key == "boot_to_process_s":
        v = doc.get("boot", {}).get("boot_to_process_s")
        return "—" if v is None else f"{v:.1f}"
    if not doc.get("enabled"):
        return "(off)"
    k = doc.get("kpis", {}).get(key, {})
    if not k.get("count"):
        return "no data"
    return f"{k['p50']:.1f} / {k['p95']:.1f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("hosts", nargs="+", help="ssh aliases, e.g. ipr-dev-pi4 ipr-prod-zero2 ipr-prod-zero")
    ap.add_argument("--repo", default="~/dev/ipr-keyboard")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    docs = {h: fetch(h, args.repo) for h in args.hosts}

    if args.json:
        print(json.dumps(docs, indent=2))
        return 0

    w = max(14, *(len(h) for h in args.hosts))
    print()
    print(f"{'':26}" + "".join(f"{h:>{w+2}}" for h in args.hosts))
    print(f"{'model':26}" + "".join(
        f"{(d.get('platform', {}).get('model', d.get('error', '?'))[:w]):>{w+2}}" for d in docs.values()))
    print(f"{'arch / os':26}" + "".join(
        f"{(d.get('platform', {}).get('machine', '') + ' ' + d.get('platform', {}).get('os', ''))[:w]:>{w+2}}"
        for d in docs.values()))
    print(f"{'metrics':26}" + "".join(
        f"{('on' if d.get('enabled') else 'off' if 'error' not in d else '—'):>{w+2}}" for d in docs.values()))
    print("-" * (26 + (w + 2) * len(args.hosts)))
    for key, label, unit in ROWS:
        print(f"{label + ' (' + unit + ')':26}" + "".join(f"{cell(d, key):>{w+2}}" for d in docs.values()))
    print()
    print("Latency cells are p50 / p95 over the device's last 200 samples.")
    print("'Pen -> BLE' stops at the Bluetooth hand-off; for pen -> PC use perf_keystroke_probe.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
