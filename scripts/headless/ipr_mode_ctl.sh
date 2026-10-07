#!/usr/bin/env bash
#
# ipr_mode_ctl.sh — switch between production and development mode
#
#   production   (default)  no port reachable from the network; when the
#                           hotspot is on, only the setup portal (443) on it
#   development             ssh (22), dashboard (443) and mDNS reachable on
#                           every network; hotspot adds nothing else
#
# The mode is a persistent file, /var/lib/ipr-keyboard/mode, read by
# ipr_fw_ctl.sh (firewall) and by the application (LED heartbeat, setup
# portal).  Changing it re-applies the firewall immediately.
#
# Usage (root, or via sudo -n from the app user — the magnet uses "toggle"):
#   ipr_mode_ctl.sh production
#   ipr_mode_ctl.sh development
#   ipr_mode_ctl.sh toggle
#   ipr_mode_ctl.sh status        prints the mode; exit 0 production, 3 development
#
# WARNING: switching to production over SSH on the home network ends that
# SSH session — that is the point.  Get back in with the magnet (hold 6 s
# toggles the mode) or over the hotspot.
#
# category: Headless
# purpose: Persistent production/development mode switch with firewall re-apply
# sudo: yes

set -euo pipefail

MODE_FILE="/var/lib/ipr-keyboard/mode"
FW="/usr/local/sbin/ipr-firewall.sh"

log() { echo "[ipr-mode] $*"; }

if [[ $EUID -ne 0 ]]; then
  echo "ipr_mode_ctl.sh must run as root (via sudo)" >&2
  exit 2
fi

current() {
  local m=""
  [[ -r "${MODE_FILE}" ]] && m="$(tr -d '[:space:]' < "${MODE_FILE}")"
  [[ "${m}" == "development" ]] && echo development || echo production
}

set_mode() {
  local new="$1"
  mkdir -p "$(dirname "${MODE_FILE}")"
  printf '%s\n' "${new}" > "${MODE_FILE}"
  chmod 0644 "${MODE_FILE}"      # the app reads it (LED heartbeat, portal)
  log "mode set to ${new}"
  if [[ -x "${FW}" ]]; then
    "${FW}" apply
  else
    log "warning: ${FW} not installed — firewall not applied" >&2
  fi
  if [[ "${new}" == "production" ]]; then
    cut_open_sessions
  fi
}

# Production must end SSH/dashboard sessions that are open right now, not
# just block new ones.  The firewall's reset rule only fires when the remote
# side sends something, so the client would notice at its next keystroke or
# keepalive (up to a minute).  Destroy the sockets from our side instead:
# the kernel sends the RST itself (outbound is not filtered), and the remote
# terminal sees "Connection reset by peer" at once.  Falls back to killing
# the sshd session processes where the kernel lacks socket destroy support.
cut_open_sessions() {
  local n=0
  if ss -K state established '( sport = :22 or sport = :443 )' >/dev/null 2>&1; then
    n=1
  fi
  # sshd per-connection processes are "sshd: user@pts/N" (session) and
  # "sshd: user [priv]"; the listener is "sshd: /usr/sbin/sshd ..." and is
  # left alone.  pkill's regexp is anchored to avoid the listener.
  pkill -TERM -f '^sshd: [^ ]+@' 2>/dev/null || true
  pkill -TERM -f '^sshd: [^ ]+ \[priv\]' 2>/dev/null || true
  log "open ssh/dashboard sessions cut (socket destroy: $([[ $n -eq 1 ]] && echo yes || echo no))"
}

case "${1:-}" in
  production|development)
    set_mode "$1"
    ;;
  toggle)
    if [[ "$(current)" == "development" ]]; then set_mode production; else set_mode development; fi
    ;;
  status)
    m="$(current)"
    echo "${m}"
    [[ "${m}" == "production" ]] && exit 0 || exit 3
    ;;
  *)
    echo "usage: $0 {production|development|toggle|status}" >&2
    exit 2
    ;;
esac
