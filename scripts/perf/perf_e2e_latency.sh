#!/usr/bin/env bash
#
# perf_e2e_latency.sh
#
# Device-side end-to-end latency test: drop N synthetic scan files into the
# first configured IrisPen folder, let the running service process them, then
# report the KPIs it recorded.
#
# Measures what the device can see -- file appears -> text handed to the BLE
# daemon.  It does NOT see the keystrokes reach the PC; for that, run
# scripts/perf/perf_keystroke_probe.py on the receiving PC instead.
#
# Requires MetricsEnabled=true in config.json (Settings -> Diagnostics on the
# dashboard, or --enable below).  Runs against the live service, so the BLE
# host will receive the synthetic text: keep a scratch window focused there.
#
# Usage (on the device):
#   ./scripts/perf/perf_e2e_latency.sh [options]
#
#   -n, --count N       number of files to drop           (default 10)
#   -c, --chars N       characters per file               (default 40)
#   -i, --interval S    seconds between drops             (default 3)
#   --enable            turn MetricsEnabled on first (needs the dashboard
#                       credentials in IPR_USER / IPR_PASS)
#   --json              print the raw /api/metrics document at the end
#
# category: Performance
# purpose: Drop synthetic scans and report device-side latency KPIs
# sudo: no

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

COUNT=10
CHARS=40
INTERVAL=3
ENABLE=false
RAW_JSON=false

log()  { echo "[perf_e2e] $*"; }
die()  { echo "[perf_e2e] ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--count)    COUNT="$2"; shift 2 ;;
        -c|--chars)    CHARS="$2"; shift 2 ;;
        -i|--interval) INTERVAL="$2"; shift 2 ;;
        --enable)      ENABLE=true; shift ;;
        --json)        RAW_JSON=true; shift ;;
        -h|--help)     sed -n '2,29p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)             die "Unknown argument: $1" ;;
    esac
done

# ---------------------------------------------------------------------------
# Where does the service look, and on which port does it answer?
# ---------------------------------------------------------------------------
CONFIG="$REPO_ROOT/config.json"
[[ -f "$CONFIG" ]] || CONFIG="$REPO_ROOT/config.default.json"
[[ -f "$CONFIG" ]] || die "No config.json or config.default.json under $REPO_ROOT"

FOLDER=$(python3 -c "import json,sys; d=json.load(open('$CONFIG')); f=d.get('IrisPenFolders') or []; print(f[0] if f else '')")
PORT=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('LogPort', 8080))")
[[ -n "$FOLDER" ]] || die "IrisPenFolders is empty in $CONFIG"
[[ -d "$FOLDER" ]] || die "IrisPen folder does not exist: $FOLDER"
[[ -w "$FOLDER" ]] || die "IrisPen folder is not writable by $(whoami): $FOLDER"

BASE="https://localhost:${PORT}"
COOKIES="$(mktemp)"
trap 'rm -f "$COOKIES"' EXIT

# ---------------------------------------------------------------------------
# Authenticate once; every /api endpoint needs a session.
# ---------------------------------------------------------------------------
: "${IPR_USER:=admin}"
if [[ -z "${IPR_PASS:-}" ]]; then
    if [[ -f "$REPO_ROOT/admin_initial_password.txt" ]]; then
        IPR_PASS="$(tr -d '\r\n' < "$REPO_ROOT/admin_initial_password.txt")"
    else
        die "Set IPR_PASS (and IPR_USER, default admin) to a dashboard login."
    fi
fi
curl -sk -c "$COOKIES" -o /dev/null -w '%{http_code}' \
     -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' \
     -d "{\"username\":\"$IPR_USER\",\"password\":\"$IPR_PASS\"}" | grep -q '^20' \
    || die "Login to $BASE failed for user $IPR_USER"

api() { curl -sk -b "$COOKIES" "$@"; }

if $ENABLE; then
    log "Enabling MetricsEnabled via /api/config ..."
    api -X POST "$BASE/api/config" -H 'Content-Type: application/json' \
        -d '{"diagnostics":{"metrics_enabled":true}}' >/dev/null
    sleep 2  # let the main loop pick the flag up on its next iteration
fi

if ! api "$BASE/api/metrics" | python3 -c "import json,sys; sys.exit(0 if json.load(sys.stdin)['enabled'] else 1)"; then
    die "MetricsEnabled is off. Enable it in Settings -> Diagnostics, or pass --enable."
fi

api -X POST "$BASE/api/metrics/reset" >/dev/null

# ---------------------------------------------------------------------------
# Drop files.  A recognisable payload so it is obvious on the PC.
# ---------------------------------------------------------------------------
log "Platform: $(python3 -c "import json,sys; p=json.load(sys.stdin)['platform']; print(p.get('model','?'), '|', p.get('machine'), '|', p.get('os','?'))" < <(api "$BASE/api/metrics"))"
log "Dropping $COUNT files of $CHARS chars into $FOLDER every ${INTERVAL}s ..."
PAYLOAD="$(head -c "$CHARS" < <(yes 'perf-test-' | tr -d '\n'))"
for i in $(seq 1 "$COUNT"); do
    printf '%s\n' "$PAYLOAD" > "$FOLDER/perf_$(date +%s%N)_$i.txt"
    printf '  %2d/%d\r' "$i" "$COUNT"
    sleep "$INTERVAL"
done
echo
sleep "$INTERVAL"   # let the last one finish

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
api "$BASE/api/metrics" | python3 - "$RAW_JSON" <<'PY'
import json, sys
raw = sys.argv[1] == "true"
d = json.load(sys.stdin)
if raw:
    print(json.dumps(d, indent=2)); sys.exit(0)
p = d["platform"]; b = d["boot"]
print()
print(f"  Device : {p.get('model','?')}  ({p.get('machine')}, {p.get('os','?')})")
print(f"  Boot   : kernel -> app process {b['boot_to_process_s']} s")
print()
print(f"  {'KPI':22} {'n':>4} {'p50':>9} {'p95':>9} {'mean':>9} {'max':>9}  unit")
for name in ("detect_latency_ms", "read_ms", "send_ms", "send_ms_per_char", "e2e_latency_ms", "poll_scan_ms", "sse_build_ms"):
    k = d["kpis"][name]
    if k["count"] == 0:
        print(f"  {name:22} {0:>4}  {'-':>8}  {'-':>8}  {'-':>8}  {'-':>8}  {k['unit']}")
    else:
        print(f"  {name:22} {k['count']:>4} {k['p50']:>9.1f} {k['p95']:>9.1f} {k['mean']:>9.1f} {k['max']:>9.1f}  {k['unit']}")
print()
print("  detect_latency is bounded below by PollIntervalSeconds; e2e is device-side only.")
PY
