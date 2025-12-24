#!/usr/bin/env bash
#
# Verification script for ipr-keyboard provisioning
# Verifies that both devices are at the "same level" with identical configuration
#
# Purpose:
#   - Verifies OS versions match
#   - Verifies services are running correctly
#   - Verifies Bluetooth is operational
#   - Produces a comprehensive report for comparison between devices
#
# Usage:
#   sudo ./provision/05_verify.sh
#
# Prerequisites:
#   - All provisioning scripts completed (00-04)
#
# category: Provisioning
# purpose: Verify device configuration and produce comparison report
# sudo: yes (for full system access)

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[verify]${NC} $*"; }
warn() { echo -e "${YELLOW}[verify]${NC} $*"; }
error() { echo -e "${RED}[verify ERROR]${NC} $*"; }
info() { echo -e "${BLUE}[verify]${NC} $*"; }

# Load environment
ENV_FILE="/opt/ipr_common.env"
if [[ ! -f "$ENV_FILE" ]]; then
  error "Environment file not found: $ENV_FILE"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

log "Running verification checks..."
echo ""

# Generate comprehensive verification report
REPORT_FILE="/opt/ipr_state/verification_report.txt"
{
  echo "============================================="
  echo "IPR Keyboard - Verification Report"
  echo "============================================="
  echo ""
  echo "Generated: $(date)"
  echo ""
  
  echo "===== DEVICE IDENTITY ====="
  echo "Hostname: $(hostname)"
  echo "Device Type: $DEVICE_TYPE"
  echo "Expected Hostname: $HOSTNAME"
  if [[ "$(hostname)" == "$HOSTNAME" ]]; then
    echo "✓ Hostname matches expected value"
  else
    echo "✗ Hostname mismatch!"
  fi
  echo ""
  
  echo "===== OPERATING SYSTEM ====="
  cat /etc/os-release
  echo ""
  echo "Kernel: $(uname -r)"
  echo "Architecture: $(uname -m)"
  echo ""
  
  echo "===== HARDWARE ====="
  cat /proc/cpuinfo | grep -E "(Model|model name|Hardware|Revision)" | head -n 4
  echo ""
  echo "Memory: $(free -h | grep Mem: | awk '{print $2}')"
  echo ""
  
  echo "===== NETWORK ====="
  echo "IP Addresses:"
  ip -4 addr show | grep inet | awk '{print "  " $NF ": " $2}'
  echo ""
  echo "mDNS Name: $(hostname).local"
  echo ""
  
  echo "===== BLUETOOTH ====="
  echo "BlueZ Version: $(bluetoothd -v)"
  echo ""
  echo "Adapter Info:"
  bluetoothctl show || echo "Bluetooth adapter not available"
  echo ""
  echo "Bluetooth Name from config: $BT_DEVICE_NAME"
  BT_NAME_ACTUAL=$(bluetoothctl show | grep "Name:" | cut -d: -f2 | xargs || echo "unknown")
  echo "Bluetooth Name (actual): $BT_NAME_ACTUAL"
  if [[ "$BT_NAME_ACTUAL" == "$BT_DEVICE_NAME" ]]; then
    echo "✓ Bluetooth name matches expected value"
  else
    echo "✗ Bluetooth name mismatch!"
  fi
  echo ""
  
  echo "===== PYTHON ENVIRONMENT ====="
  echo "Python3: $(python3 --version)"
  echo "UV: $(uv --version || echo 'not available')"
  echo "Venv Location: $APP_VENV_DIR"
  if [[ -d "$APP_VENV_DIR" ]]; then
    echo "✓ Virtual environment exists"
    echo "Venv Python: $(sudo -u "$APP_USER" "$APP_VENV_DIR/bin/python" --version)"
    echo "Package count: $(sudo -u "$APP_USER" "$APP_VENV_DIR/bin/pip" list --format=freeze | wc -l)"
  else
    echo "✗ Virtual environment not found!"
  fi
  echo ""
  
  echo "===== REPOSITORY ====="
  cd "$REPO_DIR"
  echo "Repository: $REPO_URL"
  echo "Location: $REPO_DIR"
  echo "Current Branch: $(git rev-parse --abbrev-ref HEAD)"
  echo "Current Commit: $(git rev-parse HEAD)"
  echo "Current Tag: $(git describe --tags --exact-match 2>/dev/null || echo 'not on a tag')"
  echo ""
  
  echo "===== SYSTEMD SERVICES ====="
  for service in ipr_keyboard.service bt_hid_ble.service bt_hid_agent_unified.service ipr_backend_manager.service; do
    echo "--- $service ---"
    if systemctl is-enabled "$service" &>/dev/null; then
      echo "Enabled: yes"
    else
      echo "Enabled: no"
    fi
    if systemctl is-active "$service" &>/dev/null; then
      echo "Active: yes"
      echo "Status: $(systemctl show -p ActiveState --value "$service")"
    else
      echo "Active: no"
    fi
    echo ""
  done
  
  echo "===== BACKEND CONFIGURATION ====="
  if [[ -f "$REPO_DIR/config.json" ]]; then
    echo "Backend in config.json:"
    grep -o '"KeyboardBackend"[^,]*' "$REPO_DIR/config.json" || echo "Not found"
  fi
  if [[ -f "/etc/ipr-keyboard/backend" ]]; then
    echo "Backend file: $(cat /etc/ipr-keyboard/backend)"
  fi
  echo "Expected: $BT_BACKEND"
  echo ""
  
  echo "===== RECENT LOGS ==="
  echo "--- ipr_keyboard.service (last 20 lines) ---"
  journalctl -u ipr_keyboard.service -n 20 --no-pager || echo "No logs available"
  echo ""
  echo "--- bt_hid_ble.service (last 20 lines) ---"
  journalctl -u bt_hid_ble.service -n 20 --no-pager || echo "No logs available"
  echo ""
  echo "--- bluetooth.service (last 20 lines) ---"
  journalctl -u bluetooth.service -n 20 --no-pager || echo "No logs available"
  echo ""
  
  echo "===== PROVISIONING STATE ====="
  if [[ -f "/opt/ipr_state/bootstrap_info.txt" ]]; then
    cat /opt/ipr_state/bootstrap_info.txt
  else
    echo "Bootstrap state file not found"
  fi
  echo ""
  
  echo "============================================="
  echo "End of Verification Report"
  echo "============================================="
  
} > "$REPORT_FILE"

log "Verification report saved to: $REPORT_FILE"
echo ""

# Display summary
info "═══════════════════════════════════════════"
info "              VERIFICATION SUMMARY"
info "═══════════════════════════════════════════"
echo ""

# Check critical items
ERRORS=0
WARNINGS=0

# Hostname
if [[ "$(hostname)" == "$HOSTNAME" ]]; then
  log "✓ Hostname: $HOSTNAME"
else
  error "✗ Hostname mismatch: expected=$HOSTNAME, actual=$(hostname)"
  ((ERRORS++))
fi

# Bluetooth name
BT_NAME_ACTUAL=$(bluetoothctl show | grep "Name:" | cut -d: -f2 | xargs || echo "unknown")
if [[ "$BT_NAME_ACTUAL" == "$BT_DEVICE_NAME" ]]; then
  log "✓ Bluetooth name: $BT_DEVICE_NAME"
else
  warn "⚠ Bluetooth name mismatch: expected='$BT_DEVICE_NAME', actual='$BT_NAME_ACTUAL'"
  ((WARNINGS++))
fi

# Venv
if [[ -d "$APP_VENV_DIR" ]]; then
  log "✓ Python venv: $APP_VENV_DIR"
else
  error "✗ Python venv not found: $APP_VENV_DIR"
  ((ERRORS++))
fi

# Repository
cd "$REPO_DIR"
CURRENT_COMMIT=$(git rev-parse HEAD)
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
log "✓ Repository: $CURRENT_BRANCH @ ${CURRENT_COMMIT:0:8}"

# Services
for service in ipr_keyboard.service bt_hid_ble.service bt_hid_agent_unified.service ipr_backend_manager.service; do
  if systemctl is-active "$service" &>/dev/null; then
    log "✓ Service active: $service"
  else
    warn "⚠ Service not active: $service"
    ((WARNINGS++))
  fi
done

# Bluetooth adapter
if bluetoothctl show &>/dev/null; then
  log "✓ Bluetooth adapter operational"
else
  error "✗ Bluetooth adapter not available"
  ((ERRORS++))
fi

echo ""
info "═══════════════════════════════════════════"

if [[ $ERRORS -eq 0 ]] && [[ $WARNINGS -eq 0 ]]; then
  log "✓✓✓ All checks passed! Device is ready."
elif [[ $ERRORS -eq 0 ]]; then
  warn "Device is operational with $WARNINGS warning(s)"
else
  error "Device has $ERRORS error(s) and $WARNINGS warning(s)"
  error "Review the verification report for details"
fi

echo ""
log "To compare two devices, copy verification reports and diff them:"
log "  scp meibye@ipr-dev-pi4.local:/opt/ipr_state/verification_report.txt ./dev_report.txt"
log "  scp meibye@ipr-target-zero2.local:/opt/ipr_state/verification_report.txt ./zero_report.txt"
log "  diff -u dev_report.txt zero_report.txt"
echo ""

if [[ $ERRORS -gt 0 ]]; then
  exit 1
fi
