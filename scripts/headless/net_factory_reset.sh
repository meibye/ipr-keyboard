#!/usr/bin/env bash
#
# Factory reset script for ipr-keyboard Wi-Fi provisioning
# Detects a marker file on the boot partition and wipes Wi-Fi profiles
#
# Purpose:
#   - Checks for IPR_RESET_WIFI file on boot partition
#   - If found, deletes all saved Wi-Fi connections
#   - Removes marker file and reboots into hotspot provisioning mode
#
# Usage:
#   Create an empty file named "IPR_RESET_WIFI" on the boot partition
#   Boot the Pi, and it will automatically reset Wi-Fi and enter provisioning mode
#
# Installation:
#   sudo cp scripts/headless/net_factory_reset.sh /usr/local/sbin/ipr-factory-reset.sh
#   sudo chmod +x /usr/local/sbin/ipr-factory-reset.sh
#
# Service:
#   Called by ipr-provision.service before hotspot check
#
# category: Headless
# purpose: Factory reset trigger for Wi-Fi provisioning
# sudo: yes

set -euo pipefail

# Boot partition location (try common mount points)
BOOT_MOUNTS=(/boot/firmware /boot)

MARKER="IPR_RESET_WIFI"

log() { echo "[ipr-reset] $*"; }

boot_has_marker() {
  for m in "${BOOT_MOUNTS[@]}"; do
    if mountpoint -q "$m" && [[ -f "$m/$MARKER" ]]; then
      echo "$m/$MARKER"
      return 0
    fi
  done
  return 1
}

wipe_wifi_profiles() {
  # Delete saved Wi-Fi connections only (keep ethernet/hotspot/etc.)
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    # Identify Wi-Fi connections and delete them
    if nmcli -t -f connection.type con show "$name" 2>/dev/null | grep -q "802-11-wireless"; then
      # Skip the hotspot connection
      if [[ "$name" == "ipr-hotspot" ]]; then
        log "Skipping hotspot connection: $name"
        continue
      fi
      log "Deleting Wi-Fi profile: $name"
      nmcli con delete "$name" || true
    fi
  done < <(nmcli -t -f NAME con show | sort -u)
}

main() {
  if marker_path="$(boot_has_marker)"; then
    log "Marker found: $marker_path"
    wipe_wifi_profiles
    log "Removing marker to avoid repeated resets."
    rm -f "$marker_path" || true
    log "Done. Rebooting into hotspot provisioning…"
    reboot
  else
    # No marker, normal operation
    exit 0
  fi
}

main "$@"
