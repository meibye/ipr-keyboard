#!/usr/bin/env bash
#
# IPR Keyboard on-demand management hotspot
#
# Purpose:
#   Starts a WPA2-secured Wi-Fi hotspot on wlan0 when triggered by one of:
#     1. Reed switch held ≥ 3 s (handled by gpio_monitor in ipr_keyboard.service)
#        This script is called via: systemctl start ipr-provision.service
#     2. Triple power-cycle: power off/on 3× within 120 s at boot
#     3. Boot marker file: create file named IPR_SETUP on /boot/firmware (FAT32)
#     4. GPIO gate (optional legacy): set HOTSPOT_GPIO_PIN in /etc/default/ipr-provision
#     5. HOTSPOT_MODE=always (legacy): always start at boot (backwards compatible)
#
#   Hotspot is stopped by calling: systemctl stop ipr-provision.service
#   Or by holding the reed switch ≥ 3 s again (toggles off).
#
#   Credentials are generated once and stored in /etc/ipr-hotspot.secret
#   Management web UI: https://10.42.0.1/setup/
#
# Configuration (/etc/default/ipr-provision):
#   HOTSPOT_MODE=on-demand   # default for Pi Zero 2 W (hotspot only when triggered)
#   HOTSPOT_MODE=always      # legacy / dev Pi (always start at boot)
#   HOTSPOT_GPIO_PIN=27      # optional BCM pin for hardware GPIO gate
#
# Installation:
#   sudo cp scripts/headless/net_provision_hotspot.sh /usr/local/sbin/ipr-provision.sh
#   sudo chmod +x /usr/local/sbin/ipr-provision.sh
#
# Service:
#   Managed by ipr-provision.service (Type=oneshot RemainAfterExit=yes)
#
# category: Headless
# purpose: On-demand management hotspot for Pi Zero 2 W
# sudo: yes

set -euo pipefail

HOTSPOT_CON="ipr-hotspot"
WLAN_IF="wlan0"
AP_SSID_PREFIX="ipr-setup"
SECRET_FILE="/etc/ipr-hotspot.secret"
DEFAULTS_FILE="/etc/default/ipr-provision"

# Boot-counter state file (persistent across reboots, lives in /var/lib)
BOOT_COUNT_FILE="/var/lib/ipr-keyboard/boot-count"
BOOT_COUNT_WINDOW=120   # seconds — window within which reboots are counted
BOOT_COUNT_TRIGGER=3    # number of rapid reboots that triggers the hotspot

# Boot marker files (FAT32 boot partition, writable from any PC/Mac)
BOOT_MARKERS=("/boot/firmware/IPR_SETUP" "/boot/IPR_SETUP")

# Optional env override — defaults can be set in /etc/default/ipr-provision
ENV_HOTSPOT_GPIO_PIN="${HOTSPOT_GPIO_PIN-}"
ENV_HOTSPOT_MODE="${HOTSPOT_MODE-}"
if [[ -r "${DEFAULTS_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${DEFAULTS_FILE}"
fi
HOTSPOT_GPIO_PIN="${ENV_HOTSPOT_GPIO_PIN:-${HOTSPOT_GPIO_PIN:-}}"
# Default mode: on-demand (hotspot only when explicitly triggered).
# Set HOTSPOT_MODE=always in /etc/default/ipr-provision for legacy always-on behaviour.
HOTSPOT_MODE="${ENV_HOTSPOT_MODE:-${HOTSPOT_MODE:-on-demand}}"

log() { echo "[ipr-provision] $*"; }

# ---------------------------------------------------------------------------
# Credential management
# ---------------------------------------------------------------------------

machine_suffix() {
  (cat /etc/machine-id 2>/dev/null || hostname | tr -d '\n') | head -c 4
}

load_or_generate_secret() {
  if [[ -f "${SECRET_FILE}" ]]; then
    # Ensure correct ownership/permissions in case file was created by an older version
    # (old default was root:root 0600; Flask app needs group-read via ipr-ssl).
    chown root:ipr-ssl "${SECRET_FILE}" 2>/dev/null || true
    chmod 0640 "${SECRET_FILE}" 2>/dev/null || true
    # shellcheck source=/dev/null
    source "${SECRET_FILE}"
    [[ -n "${SSID:-}" && -n "${PASS:-}" ]] && return
    log "Secret file incomplete — regenerating."
  fi

  local ssid="${AP_SSID_PREFIX}-$(machine_suffix)"
  local pass
  pass="$(python3 -c "import secrets,string; a=string.ascii_letters+string.digits+'!@#\$'; print(''.join(secrets.choice(a) for _ in range(12)))")"

  # 0640 + ipr-ssl group: root writes, app user reads (group set by gen_ipr_ssl_cert.sh)
  install -m 0640 -o root -g ipr-ssl /dev/null "${SECRET_FILE}"
  printf 'SSID=%s\nPASS=%s\n' "${ssid}" "${pass}" >"${SECRET_FILE}"
  log "Generated new credentials in ${SECRET_FILE}"

  SSID="${ssid}"
  PASS="${pass}"
}

# ---------------------------------------------------------------------------
# Trigger 1: boot-partition marker file
# ---------------------------------------------------------------------------

check_boot_marker() {
  for marker in "${BOOT_MARKERS[@]}"; do
    if [[ -f "${marker}" ]]; then
      log "Boot marker found: ${marker} — starting hotspot"
      rm -f "${marker}" 2>/dev/null || true
      return 0
    fi
  done
  return 1
}

# ---------------------------------------------------------------------------
# Trigger 2: triple power-cycle counter
# ---------------------------------------------------------------------------

check_boot_count() {
  mkdir -p "$(dirname "${BOOT_COUNT_FILE}")"

  local count=1
  local now
  now=$(date +%s)

  if [[ -f "${BOOT_COUNT_FILE}" ]]; then
    local stored_count stored_time
    read -r stored_count stored_time < "${BOOT_COUNT_FILE}" 2>/dev/null || true
    stored_count="${stored_count:-0}"
    stored_time="${stored_time:-0}"
    local age=$(( now - stored_time ))

    if (( age < BOOT_COUNT_WINDOW )); then
      count=$(( stored_count + 1 ))
    fi
    # age >= window: reset to 1 (too long since last boot)
  fi

  if (( count >= BOOT_COUNT_TRIGGER )); then
    log "Triple power-cycle detected (${count}/${BOOT_COUNT_TRIGGER} within ${BOOT_COUNT_WINDOW}s) — starting hotspot"
    printf '%s %s\n' "0" "${now}" > "${BOOT_COUNT_FILE}"  # reset counter
    return 0
  fi

  log "Boot count: ${count}/${BOOT_COUNT_TRIGGER} (window ${BOOT_COUNT_WINDOW}s). Power-cycle ${BOOT_COUNT_TRIGGER} times rapidly to trigger hotspot."
  printf '%s %s\n' "${count}" "${now}" > "${BOOT_COUNT_FILE}"
  return 1
}

# ---------------------------------------------------------------------------
# Optional GPIO gate (legacy hardware trigger)
# ---------------------------------------------------------------------------

gpio_pin_held_low() {
  local pin="${1}" hold_sec=2 interval=0.1 elapsed=0
  # raspi-gpio is available on Raspberry Pi OS; skip gate if missing
  if ! command -v raspi-gpio &>/dev/null; then
    log "raspi-gpio not found — skipping GPIO gate, hotspot will start."
    return 0
  fi

  raspi-gpio set "${pin}" ip pu 2>/dev/null || true
  log "GPIO gate enabled on pin ${pin}. Waiting ${hold_sec}s hold to start hotspot..."

  while (( $(echo "${elapsed} < ${hold_sec}" | bc -l) )); do
    local state
    state=$(raspi-gpio get "${pin}" 2>/dev/null | grep -oP 'level=\K[01]' || echo "1")
    if [[ "${state}" != "0" ]]; then
      log "GPIO ${pin} not held — hotspot not started."
      return 1
    fi
    sleep "${interval}"
    elapsed=$(echo "${elapsed} + ${interval}" | bc -l)
  done
  log "GPIO ${pin} held low — activating hotspot."
  return 0
}

# ---------------------------------------------------------------------------
# Hotspot setup — WPA2-RSN+CCMP (maximum client compatibility)
# ---------------------------------------------------------------------------

apply_wpa2_rsn() {
  # proto=rsn: WPA2 only (no legacy WPA/TKIP)
  # pairwise/group=ccmp: AES only
  # pmf=1 (disabled): avoids iOS/Android rejection on WPA2-only AP modes
  nmcli con modify "${HOTSPOT_CON}" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.proto rsn \
    wifi-sec.pairwise ccmp \
    wifi-sec.group ccmp \
    wifi-sec.pmf 1 \
    wifi-sec.psk "${PASS}"
}

ensure_hotspot_connection() {
  if nmcli -t -f NAME con show | grep -qx "${HOTSPOT_CON}"; then
    log "Updating existing hotspot connection: ${HOTSPOT_CON}"
    nmcli con modify "${HOTSPOT_CON}" 802-11-wireless.ssid "${SSID}"
  else
    log "Creating hotspot connection: ${HOTSPOT_CON} (${SSID})"
    nmcli con add type wifi ifname "${WLAN_IF}" con-name "${HOTSPOT_CON}" \
      autoconnect no ssid "${SSID}"
    nmcli con modify "${HOTSPOT_CON}" \
      802-11-wireless.mode ap \
      802-11-wireless.band bg \
      ipv4.method shared \
      ipv6.method ignore
  fi

  apply_wpa2_rsn
  nmcli con up "${HOTSPOT_CON}"
  log "Hotspot up with WPA2-RSN+CCMP. SSID=${SSID}  URL=https://10.42.0.1/setup/"
}

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

main() {
  nmcli radio wifi on || true

  # Determine whether to start the hotspot.
  # Evaluation order: marker file > boot counter > GPIO gate > mode setting.
  local should_start=0

  if check_boot_marker; then
    should_start=1
  elif check_boot_count; then
    should_start=1
  elif [[ -n "${HOTSPOT_GPIO_PIN}" ]]; then
    gpio_pin_held_low "${HOTSPOT_GPIO_PIN}" && should_start=1
  elif [[ "${HOTSPOT_MODE}" == "always" ]]; then
    log "HOTSPOT_MODE=always — starting hotspot unconditionally"
    should_start=1
  else
    log "HOTSPOT_MODE=on-demand and no trigger detected — hotspot not started"
    log "Trigger options: reed switch (hold 3 s), triple power-cycle, or create IPR_SETUP on /boot/firmware"
  fi

  if [[ ${should_start} -eq 0 ]]; then
    exit 0
  fi

  load_or_generate_secret
  ensure_hotspot_connection
  log "Hotspot active. Management UI: https://10.42.0.1/setup/"
}

main "$@"
