#!/usr/bin/env bash
#
# scripts/lib/ssh_diag.sh
#
# Explain why a key login to a device failed, from what ssh wrote to stderr.
#
# The deploy scripts test the connection with `ssh -o BatchMode=yes ... true`.
# Discarding its stderr leaves only "it failed", and every cause -- device off,
# name not resolving, a reflashed device's new host key, the key not installed
# -- then looks like a missing key.  Capture stderr instead and pass it here:
#
#   SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   source "${SCRIPT_DIR}/../lib/ssh_diag.sh"
#   if ! err="$(ssh -o BatchMode=yes -o ConnectTimeout=8 "$host" true 2>&1 >/dev/null)"; then
#       ssh_explain_failure "$host" "$err"
#   fi
#
# category: Deploy
# purpose: Plain-language diagnosis of a failed ssh key login
# sudo: no

# ssh_explain_failure ALIAS STDERR
#   Prints the cause and the fix to stdout, one sentence per line.  Commands are
#   given with the ~/.ssh/config alias, never the bare address: an address skips
#   the alias's User line, so ssh-copy-id would log in as the local user.
ssh_explain_failure() {
    local alias="$1" err="$2" hn who last
    hn="$(ssh -G "$alias" 2>/dev/null | awk '/^hostname /{print $2; exit}')"
    who="$(ssh -G "$alias" 2>/dev/null | awk '/^user /{print $2; exit}')"
    last="$(printf '%s\n' "$err" | tr -d '\r' | grep -v '^[[:space:]]*$' | tail -1)"

    case "$err" in
        *"Host key verification failed"*|*"REMOTE HOST IDENTIFICATION HAS CHANGED"*)
            echo "The device presents a different host key than last time -- usually"
            echo "because it was reflashed or re-provisioned. Remove the old entry:"
            echo "  ssh-keygen -R $hn"
            ;;
        *"Could not resolve hostname"*|*"Name or service not known"*|*"Temporary failure in name resolution"*)
            echo "The name '$hn' does not resolve. The device is off or not on this network."
            if grep -qi microsoft /proc/version 2>/dev/null; then
                echo "In WSL2, .local names never resolve: run ./scripts/deploy/wsl_setup_ssh.sh"
                echo "while the device is on, so it can pin the address."
            fi
            ;;
        *"timed out"*|*"No route to host"*|*"Network is unreachable"*)
            echo "No answer from $hn. The device is off, still booting, or its address changed."
            ;;
        *"Connection refused"*)
            echo "$hn answers, but SSH is not running there yet. A device on its first boot"
            echo "takes a few minutes; otherwise check that SSH is enabled on the image."
            ;;
        *"Permission denied"*)
            echo "The device rejected the key for user '$who'. Install it with:"
            echo "  ssh-copy-id -i ~/.ssh/ipr_rpi.pub $alias"
            echo "Use the alias '$alias', not the address: the address skips User $who."
            ;;
        *)
            echo "ssh said: ${last:-nothing (exit without a message)}"
            ;;
    esac
}
