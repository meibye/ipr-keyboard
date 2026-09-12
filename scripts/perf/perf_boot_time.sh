#!/usr/bin/env bash
#
# perf_boot_time.sh
#
# Boot-time KPIs for the device, from three independent sources so they can be
# cross-checked:
#
#   1. systemd-analyze        kernel / userspace split, as systemd saw it
#   2. journalctl             when each ipr service reported ready
#   3. /api/metrics           kernel -> application process, as the app saw it
#
# The number that matters to a user is "power on -> ready to receive a scan",
# which is roughly (3) plus the BLE stack settling; (1) and (2) show where the
# time goes.  Run after a clean reboot for meaningful figures.
#
# Usage (on the device):
#   ./scripts/perf/perf_boot_time.sh
#
# category: Performance
# purpose: Report where boot time goes and when the service became ready
# sudo: no (journal access needs the user in group systemd-journal or adm)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "[perf_boot] Device: $(tr -d '\0' < /proc/device-tree/model 2>/dev/null || uname -m)"
echo "[perf_boot] Booted: $(uptime -s 2>/dev/null || echo '?')   (up $(awk '{printf "%d", $1}' /proc/uptime) s)"
echo

echo "== 1. systemd-analyze =="
systemd-analyze 2>/dev/null || echo "  (systemd-analyze unavailable)"
echo
echo "   Slowest units:"
systemd-analyze blame 2>/dev/null | head -8 | sed 's/^/   /' || true
echo

echo "== 2. Service readiness (seconds after boot) =="
BOOT_EPOCH=$(date -d "$(uptime -s)" +%s 2>/dev/null || echo 0)
for unit in bluetooth.service bt_hid_agent_unified.service bt_hid_ble.service ipr_keyboard.service; do
    ts=$(systemctl show -p ActiveEnterTimestamp --value "$unit" 2>/dev/null || true)
    if [[ -n "$ts" && "$BOOT_EPOCH" != 0 ]]; then
        at=$(date -d "$ts" +%s 2>/dev/null || echo 0)
        printf '   %-30s +%4d s\n' "$unit" "$(( at - BOOT_EPOCH ))"
    else
        printf '   %-30s %s\n' "$unit" "(not active)"
    fi
done
echo

echo "== 3. Application view (/api/metrics) =="
CONFIG="$REPO_ROOT/config.json"; [[ -f "$CONFIG" ]] || CONFIG="$REPO_ROOT/config.default.json"
PORT=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('LogPort', 8080))" 2>/dev/null || echo 8080)
: "${IPR_USER:=admin}"
if [[ -z "${IPR_PASS:-}" && -f "$REPO_ROOT/admin_initial_password.txt" ]]; then
    IPR_PASS="$(tr -d '\r\n' < "$REPO_ROOT/admin_initial_password.txt")"
fi
if [[ -n "${IPR_PASS:-}" ]]; then
    COOKIES="$(mktemp)"; trap 'rm -f "$COOKIES"' EXIT
    curl -sk -c "$COOKIES" -o /dev/null -X POST "https://localhost:${PORT}/api/auth/login" \
         -H 'Content-Type: application/json' -d "{\"username\":\"$IPR_USER\",\"password\":\"$IPR_PASS\"}"
    curl -sk -b "$COOKIES" "https://localhost:${PORT}/api/metrics" | python3 -c '
import json, sys
d = json.load(sys.stdin); b = d["boot"]
print(f"   kernel -> ipr_keyboard process : {b[\"boot_to_process_s\"]} s")
print(f"   process uptime                 : {b[\"process_uptime_s\"]} s")
print(f"   metrics recording              : {\"on\" if d[\"enabled\"] else \"off\"}")
' 2>/dev/null || echo "   (could not query /api/metrics)"
else
    echo "   (set IPR_PASS to query /api/metrics)"
fi
