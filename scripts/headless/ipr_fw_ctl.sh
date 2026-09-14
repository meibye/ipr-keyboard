#!/usr/bin/env bash
#
# ipr_fw_ctl.sh — network exposure control (nftables)
#
# The device is used in a critical environment: nothing may listen on the
# network unless the user asked for it.  This script owns one nftables table,
# `inet ipr_fw`, whose input chain has policy DROP, and rebuilds it from two
# facts:
#
#   mode      /var/lib/ipr-keyboard/mode   production (default) | development
#   hotspot   is the `ipr-hotspot` NetworkManager connection active?
#
#   mode         home network         hotspot (10.42.0.0/24 on wlan0)
#   ---------------------------------------------------------------------
#   production   nothing              tcp 443, udp 67 (DHCP so clients get
#                                     an address; DNS 53 stays closed)
#   development  tcp 22, 443,         tcp 22, 443, udp 67
#                udp 5353 (mDNS)
#
# Always allowed: loopback, established/related replies to the device's own
# outbound traffic, ICMP/ICMPv6 (path MTU, IPv6 neighbour discovery) and DHCP
# *client* replies (udp 67 -> 68) so the device can join the home network.
# Outbound traffic is not filtered.  Bluetooth is not IP and is unaffected.
#
# Usage (root):
#   ipr_fw_ctl.sh apply     rebuild the table from mode + hotspot state
#   ipr_fw_ctl.sh status    print mode, hotspot state and the open ports
#   ipr_fw_ctl.sh off       remove the table (everything open; dev/lab only)
#
# Called by ipr-firewall.service (boot, before networking), the NetworkManager
# dispatcher hook 90-ipr-firewall (every connection up/down), ipr_mode_ctl.sh
# (mode change) and ipr-provision.sh (hotspot start/stop).  `nft -f` loads the
# ruleset atomically: on a syntax error the previous table stays in force.
#
# category: Headless
# purpose: nftables input policy driven by production/development mode and hotspot state
# sudo: yes

set -euo pipefail

MODE_FILE="/var/lib/ipr-keyboard/mode"
HOTSPOT_CON="ipr-hotspot"
HOTSPOT_NET="10.42.0.0/24"
TABLE="ipr_fw"

log() { echo "[ipr-firewall] $*"; }

if [[ $EUID -ne 0 ]]; then
  echo "ipr_fw_ctl.sh must run as root" >&2
  exit 2
fi

read_mode() {
  local m=""
  [[ -r "${MODE_FILE}" ]] && m="$(tr -d '[:space:]' < "${MODE_FILE}")"
  case "${m}" in
    development) echo development ;;
    *)           echo production ;;   # unknown/missing = safest
  esac
}

hotspot_iface() {
  # Interface the hotspot connection is active on, or empty.
  # At boot this runs BEFORE NetworkManager (Before=network-pre.target), so
  # nmcli fails; under `set -euo pipefail` that used to abort the whole
  # script and left the device UNFILTERED until the first connection event.
  # A missing or failing nmcli simply means "no hotspot yet".
  local out
  out="$(nmcli -t -f NAME,DEVICE con show --active 2>/dev/null || true)"
  printf '%s\n' "${out}" | awk -F: -v n="${HOTSPOT_CON}" '$1==n {print $2; exit}' || true
}

build_ruleset() {
  local mode="$1" hs_if="$2"
  # Rule order matters.  The service ports are decided BEFORE the generic
  # "established" accept, so that switching to production also kills SSH /
  # dashboard sessions that were already open (conntrack would otherwise keep
  # them alive until they close on their own).
  cat <<EOF
table inet ${TABLE}
delete table inet ${TABLE}
table inet ${TABLE} {
  chain input {
    type filter hook input priority 0; policy drop;
    iif "lo" accept
    ct state invalid drop
EOF
  if [[ -n "${hs_if}" ]]; then
    cat <<EOF
    iifname "${hs_if}" udp dport 67 accept comment "hotspot: DHCP server for clients"
    iifname "${hs_if}" ip saddr ${HOTSPOT_NET} tcp dport 443 accept comment "hotspot: setup portal"
EOF
  fi
  if [[ "${mode}" == "development" ]]; then
    cat <<EOF
    tcp dport { 22, 443 } accept comment "development: ssh + dashboard"
    udp dport 5353 accept comment "development: mDNS (<host>.local)"
EOF
  else
    # Sessions that were open when production mode was switched on get a TCP
    # reset so the remote end sees "connection reset" at once instead of a
    # silent hang; new connection attempts are dropped without any reply.
    cat <<EOF
    ct state established tcp dport { 22, 443 } reject with tcp reset comment "production: cut open sessions"
    tcp dport { 22, 443 } drop comment "production: closed (silent)"
    udp dport 5353 drop comment "production: no mDNS"
EOF
  fi
  cat <<EOF
    ct state established,related accept comment "replies to the device's own traffic"
    meta l4proto { icmp, ipv6-icmp } accept
    udp sport 67 udp dport 68 accept comment "DHCP client replies (home network)"
  }
}
EOF
}

case "${1:-}" in
  apply)
    mode="$(read_mode)"
    hs_if="$(hotspot_iface)"
    if ! command -v nft >/dev/null 2>&1; then
      log "nft not found — install nftables; leaving the network unfiltered" >&2
      exit 1
    fi
    # `delete table` fails if the table does not exist yet; the leading bare
    # `table` line creates it, so the transaction is valid either way.
    build_ruleset "${mode}" "${hs_if}" | nft -f -
    log "applied: mode=${mode} hotspot=${hs_if:-off}"
    ;;
  status)
    echo "mode:    $(read_mode)"
    echo "hotspot: $(hotspot_iface || true)"
    if nft list table inet "${TABLE}" >/dev/null 2>&1; then
      echo "table:   loaded"
      nft list table inet "${TABLE}" | grep -E 'accept|drop|reject|policy' | sed 's/^/  /'
    else
      echo "table:   NOT loaded — network is unfiltered"
      exit 1
    fi
    ;;
  off)
    nft delete table inet "${TABLE}" 2>/dev/null || true
    log "table removed — all ports open (development/lab use only)"
    ;;
  *)
    echo "usage: $0 {apply|status|off}" >&2
    exit 2
    ;;
esac
