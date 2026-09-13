#!/usr/bin/env bash
#
# ipr_net_apply.sh — apply the dashboard's network settings via NetworkManager
#
# Replaces ipr_write_dhcpcd.sh: the devices run NetworkManager (netplan-
# generated profiles), dhcpcd is not even active, so writing /etc/dhcpcd.conf
# changed nothing.  This edits the HOME network profile (the Wi-Fi / Ethernet
# connection that is not the ipr-hotspot) and re-activates it if it is the
# one currently up, so the change takes effect immediately.
#
# Usage (root, or via sudo -n from the app user):
#   ipr_net_apply.sh dhcp
#   ipr_net_apply.sh static <ip> <netmask|prefix> [gateway]
#   ipr_net_apply.sh show         # profile name, method, addresses
#
# The netmask may be dotted (255.255.255.0) or a prefix length (24).
# DNS follows the gateway for static, and DHCP for dhcp.
#
# category: Service
# purpose: Apply dhcp/static IPv4 settings to the home network profile (nmcli)
# sudo: yes

set -euo pipefail

HOTSPOT_CON="ipr-hotspot"

log() { echo "[ipr-net-apply] $*"; }
die() { echo "[ipr-net-apply] ERROR: $*" >&2; exit 1; }

if [[ $EUID -ne 0 ]]; then
  die "must run as root (via sudo)"
fi

# The home profile: prefer the active non-hotspot wifi/ethernet connection,
# else the wifi profile with autoconnect (the one the device joins at boot).
home_profile() {
  local name
  name="$(nmcli -t -f NAME,TYPE con show --active 2>/dev/null \
          | awk -F: -v h="${HOTSPOT_CON}" '$1!=h && ($2 ~ /wireless/ || $2 ~ /ethernet/) {print $1; exit}')"
  if [[ -z "${name}" ]]; then
    name="$(nmcli -t -f NAME,TYPE,AUTOCONNECT con show 2>/dev/null \
            | awk -F: -v h="${HOTSPOT_CON}" '$1!=h && $2 ~ /wireless/ && $3=="yes" {print $1; exit}')"
  fi
  [[ -n "${name}" ]] || die "no home network profile found (nmcli con show)"
  printf '%s' "${name}"
}

mask_to_prefix() {
  local m="$1"
  if [[ "${m}" =~ ^[0-9]+$ ]]; then
    (( m >= 0 && m <= 32 )) || die "prefix out of range: ${m}"
    echo "${m}"; return
  fi
  [[ "${m}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || die "bad netmask: ${m}"
  local n=0 o
  IFS=. read -r -a octs <<< "${m}"
  for o in "${octs[@]}"; do
    (( o >= 0 && o <= 255 )) || die "bad netmask: ${m}"
    while (( o > 0 )); do n=$(( n + (o & 1) )); o=$(( o >> 1 )); done
  done
  echo "${n}"
}

is_active() {
  nmcli -t -f NAME con show --active 2>/dev/null | grep -qx "$1"
}

reactivate() {
  local con="$1"
  if is_active "${con}"; then
    log "re-activating ${con} so the change takes effect (an SSH session on the old address will drop)"
    nmcli -w 20 con up "${con}" >/dev/null || log "warning: re-activation failed; the profile is saved and applies at the next connect"
  else
    log "${con} is not active right now (hotspot on?) — the profile applies at the next connect"
  fi
}

case "${1:-}" in
  dhcp)
    con="$(home_profile)"
    nmcli con modify "${con}" ipv4.method auto ipv4.addresses "" ipv4.gateway "" ipv4.dns "" ipv4.ignore-auto-dns no
    log "${con}: ipv4.method=auto"
    reactivate "${con}"
    ;;
  static)
    ip="${2:-}"; mask="${3:-}"; gw="${4:-}"
    [[ "${ip}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || die "bad IP address: ${ip}"
    [[ -n "${mask}" ]] || die "netmask/prefix required"
    prefix="$(mask_to_prefix "${mask}")"
    if [[ -n "${gw}" ]]; then
      [[ "${gw}" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || die "bad gateway: ${gw}"
    fi
    con="$(home_profile)"
    nmcli con modify "${con}" ipv4.method manual ipv4.addresses "${ip}/${prefix}" \
      ipv4.gateway "${gw}" ipv4.dns "${gw}" ipv4.ignore-auto-dns yes
    log "${con}: ipv4.method=manual ${ip}/${prefix} gw=${gw:-none}"
    reactivate "${con}"
    ;;
  show)
    con="$(home_profile)"
    echo "profile: ${con}"
    nmcli -g ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns con show "${con}" \
      | paste -d' ' - - - - | sed 's/^/ipv4:    /'
    ;;
  *)
    echo "usage: $0 {dhcp|static <ip> <netmask|prefix> [gateway]|show}" >&2
    exit 2
    ;;
esac
