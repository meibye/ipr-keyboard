#!/bin/bash
#
# Tail logs for all ipr-keyboard and Bluetooth stack services
#
# Usage:
#   sudo ./scripts/service/svc_tail_all_logs.sh
#
# Shows live logs for all ipr-keyboard, bt_hid, and core Bluetooth services.
#
# category: Service
# purpose: Tail all relevant service logs
# sudo: yes

set -euo pipefail

sudo journalctl \
  -u "ipr*" \
  -u "bt_hid*" \
  -u "bluetooth.service" \
  -u "dbus.service" \
  -u "systemd-udevd.service" \
  -f
  -o short 
  --output-fields=_SYSTEMD_UNIT,MESSAGE