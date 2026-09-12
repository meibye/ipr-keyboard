#!/usr/bin/env bash
#
# wsl_setup_ssh.sh
#
# Give WSL its own working SSH setup, copied from Windows.
#
# WSL does not share the Windows user's ~/.ssh.  A fresh WSL distribution has
# no keys and no config at all, so `ssh ipr-prod` resolves to the literal
# hostname "ipr-prod" as the WSL user, and every transfer fails or falls back
# to a password prompt.
#
# Symlinking to /mnt/c/Users/<user>/.ssh does not work: files on the Windows
# drive appear as mode 0777 and ssh refuses a private key that permissive.  The
# keys must be copied into the Linux filesystem and given correct permissions.
#
# This script also works around a second WSL limitation: mDNS.  Under WSL2's
# NAT networking, <host>.local does not resolve, so the .local names in the
# Windows config are useless here.  Windows itself resolves them fine, so the
# addresses are looked up through Windows interop at sync time and written as
# a WSL-only override block.  Re-run after a DHCP lease change.
#
# Run inside WSL:
#   ./scripts/deploy/wsl_setup_ssh.sh
#
# Usage:
#   ./scripts/deploy/wsl_setup_ssh.sh [options]
#
#   --win-user NAME   Windows account name. Default: detected via interop.
#   --host NAME       Host alias to pin to an address. Repeatable.
#                     Default: ipr-prod ipr-prod-zero2 ipr-prod-zero ipr-dev-pi4
#   --host-ip A=IP    Pin alias A to IP directly, instead of resolving it
#                     through Windows. Repeatable. Needed when Windows
#                     interop is unavailable in this distribution.
#   --no-pin          Copy keys and config only; write no address overrides.
#   --force           Overwrite existing files in ~/.ssh.
#
# category: Deploy
# purpose: Copy Windows SSH keys and config into WSL with correct permissions
# sudo: no

set -euo pipefail

SSH_DIR="$HOME/.ssh"
MARKER_BEGIN="# --- BEGIN wsl_setup_ssh.sh generated overrides ---"
MARKER_END="# --- END wsl_setup_ssh.sh generated overrides ---"

WIN_USER=""
HOSTS=()
PIN=true
FORCE=false
declare -A HOST_IP=()
INTEROP=true

log()  { echo "[wsl_setup_ssh] $*"; }
warn() { echo "[wsl_setup_ssh] WARNING: $*" >&2; }
die()  { echo "[wsl_setup_ssh] ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --win-user) WIN_USER="$2"; shift 2 ;;
        --host)     HOSTS+=("$2"); shift 2 ;;
        --host-ip)  HOST_IP["${2%%=*}"]="${2#*=}"; shift 2 ;;
        --no-pin)   PIN=false; shift ;;
        --force)    FORCE=true; shift ;;
        -h|--help)  sed -n '2,35p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)          die "Unknown argument: $1" ;;
    esac
done

[[ ${#HOSTS[@]} -gt 0 ]] || HOSTS=(ipr-prod ipr-prod-zero2 ipr-prod-zero ipr-dev-pi4)

grep -qi microsoft /proc/version 2>/dev/null || \
    warn "This does not look like WSL. Continuing anyway."

# ---------------------------------------------------------------------------
# Locate the Windows .ssh directory
# ---------------------------------------------------------------------------
# Windows interop is not guaranteed.  A distribution with systemd enabled can
# end up without the WSLInterop binfmt handler registered, and then every .exe
# fails with "Exec format error".  Probe once and degrade instead of failing.
if ! powershell.exe -NoProfile -Command '$null' >/dev/null 2>&1; then
    INTEROP=false
    warn "Windows interop is not working in this distribution."
    warn "  (.exe files fail with 'Exec format error' — the WSLInterop binfmt"
    warn "   handler is not registered. Often seen with systemd=true.)"
    warn "Falling back to filesystem detection; addresses cannot be resolved"
    warn "through Windows, so use --host-ip ALIAS=IP if pinning is needed."
fi

if [[ -z "$WIN_USER" ]] && $INTEROP; then
    WIN_USER="$(powershell.exe -NoProfile -Command '$env:USERNAME' 2>/dev/null | tr -d '\r' || true)"
fi

if [[ -z "$WIN_USER" ]]; then
    # Fall back to the filesystem: a Windows profile that has an .ssh directory
    # is almost certainly the one we want.  Only accept an unambiguous match.
    mapfile -t candidates < <(ls -d /mnt/c/Users/*/.ssh 2>/dev/null || true)
    if [[ ${#candidates[@]} -eq 1 ]]; then
        WIN_USER="$(basename "$(dirname "${candidates[0]}")")"
        log "Detected Windows user from ${candidates[0]}"
    elif [[ ${#candidates[@]} -gt 1 ]]; then
        warn "Several Windows profiles have an .ssh directory:"
        for c in "${candidates[@]}"; do warn "  $c"; done
    fi
fi

[[ -n "$WIN_USER" ]] || die "Could not detect the Windows user. Pass --win-user NAME."

WIN_SSH="/mnt/c/Users/$WIN_USER/.ssh"
[[ -d "$WIN_SSH" ]] || die "Windows SSH directory not found: $WIN_SSH
       Pass --win-user with the correct account name."

log "Windows user:    $WIN_USER"
log "Windows ~/.ssh:  $WIN_SSH"
log "WSL ~/.ssh:      $SSH_DIR"

# ---------------------------------------------------------------------------
# Remember addresses pinned by an earlier run
#
# This must happen before the config is copied: that copy replaces
# ~/.ssh/config with the Windows original and destroys the generated block.
# Resolution later on can fail for reasons unrelated to the host being wrong —
# interop dropping out, the device asleep — and the last known good address is
# then a far better answer than no override, which leaves an unresolvable
# .local name behind.
# ---------------------------------------------------------------------------
declare -A PREV_IP=()
if [[ -f "$SSH_DIR/config" ]]; then
    prev_host=""
    while read -r key value _; do
        case "$key" in
            Host)     prev_host="$value" ;;
            HostName) [[ -n "$prev_host" ]] && PREV_IP["$prev_host"]="$value" ;;
        esac
    done < <(sed -n "/^${MARKER_BEGIN}\$/,/^${MARKER_END}\$/p" "$SSH_DIR/config")
    [[ ${#PREV_IP[@]} -eq 0 ]] || log "Previously pinned: ${!PREV_IP[*]}"
fi

# ---------------------------------------------------------------------------
# Copy keys and config
#
# Only private keys that have a matching .pub are taken, which skips
# authorized_keys, known_hosts and stray backups.
# ---------------------------------------------------------------------------
mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

copied=0
skipped=0
for pub in "$WIN_SSH"/*.pub; do
    [[ -e "$pub" ]] || continue
    priv="${pub%.pub}"
    [[ -f "$priv" ]] || continue
    name="$(basename "$priv")"

    if [[ -e "$SSH_DIR/$name" ]] && ! $FORCE; then
        skipped=$((skipped + 1))
        continue
    fi
    cp "$priv" "$SSH_DIR/$name"
    cp "$pub"  "$SSH_DIR/$name.pub"
    chmod 600  "$SSH_DIR/$name"
    chmod 644  "$SSH_DIR/$name.pub"
    copied=$((copied + 1))
done
log "Keys copied: $copied  (already present, left alone: $skipped)"
$FORCE || [[ $skipped -eq 0 ]] || log "Use --force to overwrite existing keys."

if [[ -f "$WIN_SSH/config" ]]; then
    if [[ -e "$SSH_DIR/config" ]] && ! $FORCE; then
        log "~/.ssh/config already exists — left alone. Use --force to replace it."
    else
        # Strip CRLF: a config written on Windows otherwise yields
        # "Bad configuration option" on the first parsed line.
        tr -d '\r' < "$WIN_SSH/config" > "$SSH_DIR/config"
        chmod 600 "$SSH_DIR/config"
        log "Copied ~/.ssh/config (CRLF stripped)"
    fi
else
    warn "No config found at $WIN_SSH/config — host aliases will not work."
fi

# ---------------------------------------------------------------------------
# Pin addresses, because .local does not resolve under WSL2
# ---------------------------------------------------------------------------
if $PIN; then
    log "Resolving host addresses ..."
    overrides=""
    for h in "${HOSTS[@]}"; do
        # Ask ssh what the config maps this alias to, then resolve that name
        # on the Windows side where mDNS works.
        target="$(ssh -G "$h" 2>/dev/null | awk '/^hostname /{print $2; exit}')"
        [[ -n "$target" ]] || target="$h"

        # An address given on the command line always wins.
        if [[ -n "${HOST_IP[$h]:-}" ]]; then
            log "  $h -> ${HOST_IP[$h]} (from --host-ip)"
            overrides+="Host $h"$'\n'"    HostName ${HOST_IP[$h]}"$'\n'
            continue
        fi

        if getent hosts "$target" >/dev/null 2>&1; then
            log "  $h -> $target (resolves in WSL already, no override needed)"
            continue
        fi

        if ! $INTEROP; then
            if [[ -n "${PREV_IP[$h]:-}" ]]; then
                log "  $h -> ${PREV_IP[$h]} (kept from previous run; interop unavailable)"
                overrides+="Host $h"$'\n'"    HostName ${PREV_IP[$h]}"$'\n'
            else
                warn "  $h -> $target — cannot resolve: .local needs mDNS (absent in"
                warn "     WSL2) and Windows interop is unavailable. Re-run with:"
                warn "       --host-ip $h=<address>"
            fi
            continue
        fi

        ip="$(powershell.exe -NoProfile -Command \
              "(Resolve-DnsName -Name $target -Type A -ErrorAction SilentlyContinue).IPAddress" \
              2>/dev/null | tr -d '\r' | head -1)"

        if [[ "$ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            log "  $h -> $target -> $ip"
            overrides+="Host $h"$'\n'"    HostName $ip"$'\n'
        elif [[ -n "${PREV_IP[$h]:-}" ]]; then
            log "  $h -> ${PREV_IP[$h]} (kept from previous run; lookup failed)"
            overrides+="Host $h"$'\n'"    HostName ${PREV_IP[$h]}"$'\n'
        else
            warn "  $h -> $target — could not resolve. Is the device powered on?"
        fi
    done

    if [[ -n "$overrides" ]]; then
        tmp="$(mktemp)"
        # Remove any previous generated block, then prepend the new one.
        # ssh uses the first value it obtains for each keyword, so the block
        # must come before the copied Windows blocks to take effect.
        if [[ -f "$SSH_DIR/config" ]]; then
            sed "/^${MARKER_BEGIN}\$/,/^${MARKER_END}\$/d" "$SSH_DIR/config" > "$tmp.rest"
        else
            : > "$tmp.rest"
        fi
        {
            echo "$MARKER_BEGIN"
            echo "# .local names do not resolve under WSL2; addresses resolved via Windows."
            echo "# Re-run scripts/deploy/wsl_setup_ssh.sh after a DHCP lease change."
            echo "$overrides"
            echo "$MARKER_END"
            echo
            cat "$tmp.rest"
        } > "$tmp"
        mv "$tmp" "$SSH_DIR/config"
        chmod 600 "$SSH_DIR/config"
        rm -f "$tmp.rest"
        log "Address overrides written to ~/.ssh/config"
    fi
fi

# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------
echo
log "Verifying ..."
failed=0
for h in "${HOSTS[@]}"; do
    user="$(ssh -G "$h" 2>/dev/null | awk '/^user /{print $2; exit}')"
    hn="$(ssh -G "$h" 2>/dev/null | awk '/^hostname /{print $2; exit}')"
    if ssh -o BatchMode=yes -o ConnectTimeout=8 "$h" true 2>/dev/null; then
        echo "  ok    $h  ($user@$hn) — key login works"
    else
        echo "  FAIL  $h  ($user@$hn)"
        failed=$((failed + 1))
    fi
done

if [[ $failed -gt 0 ]]; then
    echo
    warn "$failed host(s) did not accept a key login."
    warn "If the device is off or on another network, that is expected."
    warn "Otherwise install the key:  ssh-copy-id -i ~/.ssh/ipr_rpi.pub <host>"
    exit 1
fi

echo
log "WSL SSH is ready. You can now run:"
log "  ./scripts/deploy/host_push_to_device.sh ipr-prod --dry-run"
