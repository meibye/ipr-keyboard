#!/usr/bin/env bash
#
# bt_adapter_prepare.sh — bring the adapter to a KNOWN state before the agent
#
# Runs as ExecStartPre of bt_hid_agent_unified.service (root).  Guarantees:
#   powered, LE only (BR/EDR off), bondable, connectable
#
# Why this exists: the unit used to run `hciconfig hci0 up` and then
# `btmgmt bredr off`.  At boot that powered the adapter with the kernel's
# dual-mode defaults *before* bluetoothd had applied ControllerMode = le from
# /etc/bluetooth/main.conf, and `bredr off` is rejected on a powered adapter
# — so the device ran dual-mode after every boot but LE-only after any
# service restart.  A PC bonded in one configuration would not reconnect in
# the other ("Windows never reconnects after Reconnect Bluetooth").
#
# btmgmt hangs without a terminal (bt_shell); every call goes through
# `script -qec` and `timeout`, as before.
#
# category: Service
# purpose: Deterministic LE-only adapter setup for the HOGP stack
# sudo: yes

set -u
HCI="${1:-${BT_HCI:-hci0}}"

log() { echo "[bt_adapter_prepare] $*"; }

mgmt() {  # mgmt <btmgmt args...>
  timeout 15 script -qec "/usr/bin/btmgmt -i ${HCI} $*" /dev/null
}

settings() {
  timeout 10 script -qec "/usr/bin/btmgmt -i ${HCI} info" /dev/null 2>/dev/null \
    | sed -n 's/.*current settings: *//p' | head -1
}

# 1. Wait for bluetoothd to own the adapter (it powers it with
#    ControllerMode = le and AutoEnable = true); do not power it ourselves.
for _ in $(seq 1 30); do
  if busctl get-property org.bluez "/org/bluez/${HCI}" org.bluez.Adapter1 Powered 2>/dev/null | grep -q true; then
    break
  fi
  sleep 1
done

cur="$(settings)"
log "settings before: ${cur:-<none>}"

# 2. Enforce LE-only.  BR/EDR can only be switched while powered off.
if [[ "${cur}" == *"br/edr"* ]]; then
  log "BR/EDR is on — power-cycling the adapter to switch it off"
  mgmt power off >/dev/null 2>&1 || true
  mgmt bredr off >/dev/null 2>&1 || log "warning: bredr off failed"
  mgmt le on     >/dev/null 2>&1 || true
  mgmt power on  >/dev/null 2>&1 || true
fi

mgmt le on          >/dev/null 2>&1 || true
mgmt bondable on    >/dev/null 2>&1 || true
mgmt connectable on >/dev/null 2>&1 || true

cur="$(settings)"
log "settings after:  ${cur:-<none>}"
if [[ "${cur}" == *"br/edr"* ]]; then
  log "ERROR: adapter still dual-mode; HOGP bonds will be inconsistent" >&2
  exit 1
fi
exit 0
