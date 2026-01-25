#!/usr/bin/env bash
# SSH forced-command guard for MCP access
# VERSION: 2026-01-25
#
# This script is intended to be used via authorized_keys forced command:
#   command="/usr/local/bin/ipr_mcp_guard.sh",no-pty,no-port-forwarding,no-agent-forwarding ssh-ed25519 AAAA...
#
# It restricts execution to allow-listed commands (default: dbg_* wrappers).
#
# Allow-list file:
#   /etc/ipr_mcp_allowlist.conf
#
# Logging:
#   /var/log/ipr_mcp_guard.log

set -euo pipefail

LOG="/var/log/ipr_mcp_guard.log"
ALLOW="/etc/ipr_mcp_allowlist.conf"

cmd="${SSH_ORIGINAL_COMMAND:-}"

ts="$(date -Is)"
echo "[$ts] user=${USER:-?} cmd=${cmd}" >>"$LOG" 2>/dev/null || true

# Reject empty command
if [[ -z "${cmd}" ]]; then
  echo "Denied: empty command"
  exit 1
fi

# Hard reject obvious shell metacharacters that enable chaining/escaping
# (MCP should call single commands; dbg_* scripts should encapsulate complex logic)
if echo "$cmd" | grep -Eq '[;&|`><]|\$\(|\)\s*$'; then
  echo "Denied: unsafe characters in command"
  exit 1
fi

# If allowlist file missing, deny by default
if [[ ! -f "$ALLOW" ]]; then
  echo "Denied: allowlist missing ($ALLOW)"
  exit 1
fi

# Normalize: some tools call "dbg_x.sh ..." without absolute path
# Permit both "dbg_*.sh" and "/usr/local/bin/dbg_*.sh"
normalized="$cmd"
if [[ "$cmd" =~ ^dbg_.*\.sh($|[[:space:]].*) ]]; then
  normalized="/usr/local/bin/$cmd"
fi

allowed=0
while IFS= read -r pat; do
  [[ -z "$pat" ]] && continue
  [[ "$pat" =~ ^# ]] && continue
  if [[ "$normalized" == $pat ]]; then
    allowed=1
    break
  fi
done <"$ALLOW"

if [[ "$allowed" -ne 1 ]]; then
  echo "Denied: command not in allowlist"
  exit 1
fi

# Execute safely (no extra shell expansions)
exec bash -lc "$normalized"
