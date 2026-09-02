#!/usr/bin/env bash
#
# host_push_to_device.sh
#
# Everything the ADMINISTRATOR PC has to do to get a device ready for
# provisioning: pack the payload, copy it across with the environment file and
# the diagnostics public key, unpack it on the device and restore the execute
# bits that Windows cannot carry.
#
# Run this from Git Bash or WSL on the PC — NOT on the Raspberry Pi, and not
# from PowerShell (it is a bash script; PowerShell has no bash).  From
# PowerShell, call it as:
#
#   bash ./scripts/deploy/host_push_to_device.sh ipr-prod
#
# Afterwards, continue on the device with:
#
#   ssh <host>
#   sudo ~/dev/ipr-keyboard/scripts/deploy/device_bootstrap.sh
#
# Usage:
#   ./scripts/deploy/host_push_to_device.sh [HOST] [options]
#
#   HOST                 ssh target; an alias from ~/.ssh/config is strongly
#                        preferred over a full hostname, because a pattern like
#                        'Host ipr-prod ipr-prod-zero2' does not match
#                        'ipr-prod-zero2.local' and the key would be skipped.
#                        Default: ipr-prod
#
#   --env FILE           environment file to install as /opt/ipr_common.env.
#                        Default: provision/common.env
#   --pubkey FILE        public key placed at /tmp/copilot_pubkey.txt for
#                        provisioning step 05.  Default: ~/.ssh/copilotdiag_rpi.pub
#   --remote-dir DIR     where the repository lands on the device.
#                        Default: ~/dev/ipr-keyboard
#   --with-tests         include tests/ in the payload (development device)
#   --skip-env           do not transfer the environment file
#   --skip-pubkey        do not transfer the public key
#   --dry-run            show what would happen, change nothing
#
# category: Deploy
# purpose: One-command transfer of code, environment and key from PC to device
# sudo: no

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

HOST="ipr-prod"
ENV_FILE="$REPO_ROOT/provision/common.env"
PUBKEY="$HOME/.ssh/copilotdiag_rpi.pub"
REMOTE_DIR="~/dev/ipr-keyboard"
PAYLOAD_ARGS=()
SKIP_ENV=false
SKIP_PUBKEY=false
DRY_RUN=false

log()  { echo "[host_push] $*"; }
warn() { echo "[host_push] WARNING: $*" >&2; }
die()  { echo "[host_push] ERROR: $*" >&2; exit 1; }

run() {
    if $DRY_RUN; then
        echo "[host_push] would run: $*"
    else
        "$@"
    fi
}

# Positional HOST may come before or after the options.
while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)         ENV_FILE="$2"; shift 2 ;;
        --pubkey)      PUBKEY="$2"; shift 2 ;;
        --remote-dir)  REMOTE_DIR="$2"; shift 2 ;;
        --with-tests)  PAYLOAD_ARGS+=("--with-tests"); shift ;;
        --skip-env)    SKIP_ENV=true; shift ;;
        --skip-pubkey) SKIP_PUBKEY=true; shift ;;
        --dry-run)     DRY_RUN=true; shift ;;
        -h|--help)     sed -n '2,45p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        -*)            die "Unknown option: $1" ;;
        *)             HOST="$1"; shift ;;
    esac
done

# ---------------------------------------------------------------------------
# Preflight — fail here rather than half way through a transfer
# ---------------------------------------------------------------------------
log "Target host: $HOST"

case "$HOST" in
    *.local|*.*.*.*)
        warn "'$HOST' looks like a hostname or IP rather than an ~/.ssh/config alias."
        warn "Host patterns such as 'Host ipr-prod ipr-prod-zero2' do not match a"
        warn ".local suffix, so IdentityFile is skipped and ssh falls back to asking"
        warn "for a password. Prefer the alias, e.g. 'ipr-prod'."
        ;;
esac

log "Checking SSH connectivity ..."
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$HOST" true 2>/dev/null; then
    # Every step below needs this connection.  Continuing would mean a
    # password prompt per transfer at best, and a chain of failures at worst,
    # so stop here with a diagnosis instead.
    hn="$(ssh -G "$HOST" 2>/dev/null | awk '/^hostname /{print $2; exit}')"
    who="$(ssh -G "$HOST" 2>/dev/null | awk '/^user /{print $2; exit}')"

    echo "[host_push] ERROR: cannot log in to '$HOST' with a key." >&2
    echo "       ssh resolves it to: $who@$hn" >&2
    echo >&2

    if [[ "$hn" == "$HOST" ]]; then
        echo "       That is the alias itself, so ~/.ssh/config has no entry for it." >&2
    fi

    if grep -qi microsoft /proc/version 2>/dev/null && [[ ! -d "$HOME/.ssh" ]]; then
        echo "       You are in WSL and $HOME/.ssh does not exist. WSL does not share" >&2
        echo "       the Windows user's keys or config. Set it up once with:" >&2
        echo >&2
        echo "         ./scripts/deploy/wsl_setup_ssh.sh" >&2
    elif grep -qi microsoft /proc/version 2>/dev/null; then
        echo "       In WSL, .local names do not resolve and the Windows keys are not" >&2
        echo "       shared. If you have not done so on this distribution, run:" >&2
        echo >&2
        echo "         ./scripts/deploy/wsl_setup_ssh.sh" >&2
    else
        echo "       Install your key on the device with:" >&2
        echo "         ssh-copy-id -i ~/.ssh/ipr_rpi.pub $HOST" >&2
    fi

    echo >&2
    echo "       Then verify with:  ssh $HOST true" >&2
    exit 1
fi
log "SSH connectivity ok."

if ! $SKIP_ENV; then
    if [[ ! -f "$ENV_FILE" ]]; then
        die "Environment file not found: $ENV_FILE
       The repository ships only the template. Create your copy first:
         cp provision/common.env.example provision/common.env
       then edit DEVICE_TYPE, HOSTNAME and BT_DEVICE_NAME for this device.
       (Or pass --skip-env to transfer the code only.)"
    fi
    log "Environment file: $ENV_FILE"
fi

if ! $SKIP_PUBKEY && [[ ! -f "$PUBKEY" ]]; then
    # Under WSL the key usually exists on the Windows side but has not been
    # copied in yet.  Fall back to it rather than silently skipping the key.
    if grep -qi microsoft /proc/version 2>/dev/null; then
        win_user="$(powershell.exe -NoProfile -Command '$env:USERNAME' 2>/dev/null | tr -d '\r' || true)"
        win_pub="/mnt/c/Users/$win_user/.ssh/$(basename "$PUBKEY")"
        if [[ -n "$win_user" && -f "$win_pub" ]]; then
            warn "$PUBKEY not found in WSL; using the Windows copy at $win_pub."
            warn "Run ./scripts/deploy/wsl_setup_ssh.sh to sync keys into WSL properly."
            PUBKEY="$win_pub"
        fi
    fi
fi

if ! $SKIP_PUBKEY; then
    if [[ ! -f "$PUBKEY" ]]; then
        warn "Public key not found: $PUBKEY — skipping it."
        warn "Provisioning step 05 will then prompt for the key interactively."
        SKIP_PUBKEY=true
    else
        log "Diagnostics public key: $PUBKEY"
    fi
fi

# ---------------------------------------------------------------------------
# 1. Pack
# ---------------------------------------------------------------------------
PAYLOAD="${TMPDIR:-/tmp}/ipr-deploy.tgz"
log "Packing payload ..."
run "$SCRIPT_DIR/make_payload.sh" -o "$PAYLOAD" ${PAYLOAD_ARGS[@]+"${PAYLOAD_ARGS[@]}"}

# ---------------------------------------------------------------------------
# 2. Transfer
# ---------------------------------------------------------------------------
log "Transferring payload to $HOST ..."
run scp "$PAYLOAD" "$HOST:/tmp/ipr-deploy.tgz"

$SKIP_ENV    || run scp "$ENV_FILE" "$HOST:/tmp/ipr_common.env"
$SKIP_PUBKEY || run scp "$PUBKEY"   "$HOST:/tmp/copilot_pubkey.txt"

# ---------------------------------------------------------------------------
# 3. Unpack and repair permissions on the device
#
# Windows has no execute bit, so anything that travelled through a Windows
# filesystem arrives without +x.  Only scripts/ and provision/ need it; modules
# under src/ are imported, never executed directly.
# ---------------------------------------------------------------------------
log "Unpacking on $HOST and restoring execute bits ..."
run ssh "$HOST" "
    set -e
    mkdir -p $REMOTE_DIR
    tar xzf /tmp/ipr-deploy.tgz -C $REMOTE_DIR
    rm -f /tmp/ipr-deploy.tgz
    find $REMOTE_DIR/scripts $REMOTE_DIR/provision \
        \\( -name '*.sh' -o -name '*.py' \\) -exec chmod +x {} +
"

if ! $SKIP_ENV; then
    log "Installing /opt/ipr_common.env (requires sudo on the device) ..."
    run ssh -t "$HOST" "
        sudo mv /tmp/ipr_common.env /opt/ipr_common.env
        sudo chmod 0600 /opt/ipr_common.env
    "
fi

$DRY_RUN && { log "Dry run complete — nothing was changed."; exit 0; }

log ""
log "Done. Continue on the device:"
log "  ssh $HOST"
log "  sudo $REMOTE_DIR/scripts/deploy/device_bootstrap.sh"
