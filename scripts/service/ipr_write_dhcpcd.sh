#!/usr/bin/env bash
#
# ipr_write_dhcpcd.sh
#
# Privileged helper: reads new /etc/dhcpcd.conf content from stdin and writes
# it atomically.  Accepts no arguments so the sudoers rule requires no wildcard.
#
# Usage (via sudo from the ipr_keyboard service):
#   printf '%s' "$content" | sudo /usr/local/bin/ipr_write_dhcpcd.sh
#
# category: Service
# purpose: Write /etc/dhcpcd.conf with elevated privileges on behalf of the app user
# sudo: yes

set -euo pipefail

TARGET="/etc/dhcpcd.conf"
TMPFILE="$(mktemp /etc/dhcpcd.conf.tmp.XXXXXX)"
trap 'rm -f "$TMPFILE"' EXIT

cat > "$TMPFILE"

if [[ ! -s "$TMPFILE" ]]; then
  echo "ipr_write_dhcpcd: ERROR: received empty input, refusing to overwrite $TARGET" >&2
  exit 1
fi

if [[ -f "$TARGET" ]]; then
  chmod --reference="$TARGET" "$TMPFILE"
  chown --reference="$TARGET" "$TMPFILE"
fi

mv "$TMPFILE" "$TARGET"
