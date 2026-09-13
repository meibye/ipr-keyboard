#!/usr/bin/env bash
#
# ipr_hotspot_ctl.sh — root helper for the reed-switch / LED monitor
#
# Purpose:
#   The ipr_keyboard service runs as an unprivileged user.  The magnet
#   gestures (hotspot toggle, network reset) need root, so gpio_monitor.py
#   calls this helper through a NOPASSWD sudoers entry instead of calling
#   systemctl/nmcli/reboot directly.  Keeping every privileged action in one
#   small script keeps the sudoers grant narrow and auditable.
#
# Usage (as root, or via sudo -n from the app user):
#   ipr_hotspot_ctl.sh start          # bring the management hotspot up now
#   ipr_hotspot_ctl.sh stop           # take it down again
#   ipr_hotspot_ctl.sh status         # exit 0 if the hotspot is up, 1 if not
#   ipr_hotspot_ctl.sh factory-reset  # delete WiFi profiles (not the hotspot) and reboot
#   ipr_hotspot_ctl.sh poweroff       # controlled shutdown (magnet held 6 s)
#   ipr_hotspot_ctl.sh service <start|stop|restart> <unit>
#                                     # unit in: bluetooth bt_hid_agent_unified bt_hid_ble
#                                     # (dashboard "Reconnect Bluetooth" and the Debug
#                                     # page; the app has no polkit session, so a bare
#                                     # systemctl gets "Interactive authentication required")
#
# "start" works at any time, not only at boot: it writes the request file
# that /usr/local/sbin/ipr-provision.sh treats as a trigger, then restarts
# ipr-provision.service.  A plain `systemctl start` would be a no-op on a
# oneshot unit that is already active, and the script would exit without
# a trigger — both problems this helper exists to avoid.
#
# Installed by scripts/headless/install_gpio_support.sh to
# /usr/local/bin/ipr_hotspot_ctl.sh together with the sudoers entry.
#
# category: Headless
# purpose: Privileged hotspot / reset actions for the LED and reed-switch monitor
# sudo: yes

set -euo pipefail

HOTSPOT_SERVICE="ipr-provision.service"
HOTSPOT_CON="ipr-hotspot"
REQUEST_FILE="/run/ipr-hotspot.request"

log() { echo "[ipr_hotspot_ctl] $*"; }

if [[ $EUID -ne 0 ]]; then
  echo "ipr_hotspot_ctl.sh must run as root (via sudo)" >&2
  exit 2
fi

hotspot_up() {
  nmcli -t -f NAME con show --active 2>/dev/null | grep -qx "${HOTSPOT_CON}"
}

case "${1:-}" in
  start)
    if hotspot_up; then
      log "hotspot already up"
      exit 0
    fi
    : > "${REQUEST_FILE}"
    log "request written, restarting ${HOTSPOT_SERVICE}"
    # restart, not start: the oneshot unit is normally already "active"
    # (RemainAfterExit) from boot, and start would do nothing.
    systemctl restart "${HOTSPOT_SERVICE}"
    if hotspot_up; then
      log "hotspot is up"
    else
      log "hotspot did not come up — see: journalctl -u ${HOTSPOT_SERVICE}" >&2
      exit 1
    fi
    ;;
  stop)
    rm -f "${REQUEST_FILE}"
    # ExecStop in the unit runs `ipr-provision.sh --stop`; take the
    # connection down directly as well in case an older unit is installed.
    systemctl stop "${HOTSPOT_SERVICE}" || true
    if hotspot_up; then
      nmcli con down "${HOTSPOT_CON}" || true
    fi
    if hotspot_up; then
      log "hotspot still up" >&2
      exit 1
    fi
    log "hotspot is down"
    ;;
  status)
    if hotspot_up; then
      echo "up"
    else
      echo "down"
      exit 1
    fi
    ;;
  factory-reset)
    log "deleting all WiFi profiles except ${HOTSPOT_CON}"
    nmcli -t -f NAME,TYPE con show 2>/dev/null | while IFS=: read -r name ctype; do
      [[ "${ctype}" == *wireless* ]] || continue
      [[ "${name}" == "${HOTSPOT_CON}" ]] && continue
      log "  delete ${name}"
      nmcli con delete "${name}" || true
    done
    sync
    log "rebooting"
    systemctl reboot
    ;;
  poweroff)
    log "controlled shutdown requested"
    sync
    systemctl poweroff
    ;;
  service)
    action="${2:-}"; unit="${3:-}"
    case "${action}" in start|stop|restart) ;; *) echo "bad action: ${action}" >&2; exit 2 ;; esac
    unit="${unit%.service}"
    case "${unit}" in
      bluetooth|bt_hid_agent_unified|bt_hid_ble) ;;
      *) echo "unit not allowed: ${unit}" >&2; exit 2 ;;
    esac
    log "systemctl ${action} ${unit}.service"
    systemctl "${action}" "${unit}.service"
    ;;
  *)
    echo "usage: $0 {start|stop|status|factory-reset|poweroff|service <start|stop|restart> <unit>}" >&2
    exit 2
    ;;
esac
