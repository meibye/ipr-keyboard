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
#                        Targets: ipr-prod (Zero 2 W, 64-bit) or
#                                 ipr-prod-zero (Zero W, 32-bit).
#                        Default: ipr-prod
#
#   --env FILE           environment file to install as /opt/ipr_common.env.
#                        Default: provision/common.env
#   --pubkey FILE        public key placed at /tmp/copilot_pubkey.txt for
#                        provisioning step 05.  Default: ~/.ssh/copilotdiag_rpi.pub
#   --remote-dir DIR     where the repository lands on the device.
#                        Default: ~/dev/ipr-keyboard
#   --with-tests         include tests/ in the payload (development device)
#   --clean              DELETE the remote directory before unpacking, for a
#                        genuine from-scratch install.  The payload is a tar
#                        archive, so it adds and overwrites but never removes:
#                        a file deleted in the repository lingers on the device
#                        forever without this.  Destructive -- it also removes
#                        config.json, users.json and any logs living there.
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
CLEAN=false
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
        --clean)       CLEAN=true; shift ;;
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
# /tmp is cleared on boot and provisioning reboots twice before step 05 reads
# this, so stage it in /tmp and have the device move it somewhere persistent.
$SKIP_PUBKEY || run scp "$PUBKEY"   "$HOST:/tmp/copilot_pubkey.txt"

# ---------------------------------------------------------------------------
# 3. Unpack and repair permissions on the device
#
# Windows has no execute bit, so anything that travelled through a Windows
# filesystem arrives without +x.  Only scripts/ and provision/ need it; modules
# under src/ are imported, never executed directly.
# ---------------------------------------------------------------------------
if $CLEAN; then
    warn "--clean: removing $REMOTE_DIR on $HOST before unpacking."
    warn "This also deletes config.json, users.json and anything else living there."

    # Refuse if anything is mounted underneath.  The IrisPen scanner is mounted
    # from a path configured in config.json, and a cache directory under the
    # project root is a plausible choice -- rm -rf would then recurse into the
    # mount and delete the user's scans.  Never risk that to save a reinstall.
    mounted=$(ssh "$HOST" "d=\$(eval echo $REMOTE_DIR); findmnt -rno TARGET 2>/dev/null | grep -F \"\$d\" || true")
    if [[ -n "$mounted" ]]; then
        die "Refusing --clean: something is mounted under $REMOTE_DIR on $HOST:
$mounted
       Unmount it first, or re-run without --clean."
    fi

    # Provisioning creates root-owned directories inside the project (the
    # scanner cache, for one), so the user alone cannot remove the tree.
    if [[ -t 0 ]] || ssh -o BatchMode=yes "$HOST" "sudo -n true" 2>/dev/null; then
        run ssh -t "$HOST" "d=\$(eval echo $REMOTE_DIR); sudo rm -rf \"\$d\""
    else
        warn "No terminal available and passwordless sudo is not configured, so"
        warn "root-owned files under $REMOTE_DIR cannot be removed from here."
        warn "Removing what is possible; run this yourself for a full wipe:"
        warn "  ssh $HOST \"sudo rm -rf $REMOTE_DIR\""
        run ssh "$HOST" "d=\$(eval echo $REMOTE_DIR); rm -rf \"\$d\" 2>/dev/null || true"
    fi
fi

log "Unpacking on $HOST and restoring execute bits ..."
run ssh "$HOST" "
    set -e
    mkdir -p $REMOTE_DIR
    tar xzf /tmp/ipr-deploy.tgz -C $REMOTE_DIR
    rm -f /tmp/ipr-deploy.tgz
    find $REMOTE_DIR/scripts $REMOTE_DIR/provision \
        \\( -name '*.sh' -o -name '*.py' \\) -exec chmod +x {} +
"

# Move the diagnostics key somewhere that survives the provisioning reboots.
# /opt/ipr_state is created by step 00 and persists; /tmp is cleared on boot,
# and provisioning reboots twice before step 05 reads the key -- which is why
# that step used to stop and ask for it interactively.
if ! $SKIP_PUBKEY; then
    if ssh -o BatchMode=yes "$HOST" "sudo -n true" 2>/dev/null; then
        run ssh "$HOST" "sudo mkdir -p /opt/ipr_state && sudo cp /tmp/copilot_pubkey.txt /opt/ipr_state/copilot_pubkey.txt"
    else
        warn "Cannot stage the diagnostics key persistently without sudo."
        warn "It is at /tmp/copilot_pubkey.txt, which a reboot clears. To keep it:"
        warn "  ssh $HOST \"sudo mkdir -p /opt/ipr_state && sudo cp /tmp/copilot_pubkey.txt /opt/ipr_state/\""
    fi
fi

if ! $SKIP_ENV; then
    # This is the only step that needs sudo on the device.  ssh -t can only
    # allocate a terminal when this script itself has one; run from a pipeline,
    # a CI job or an agent, sudo has nowhere to ask for a password and fails
    # with "a terminal is required to read the password".  Detect that up front
    # and hand the command over rather than failing at the last step with
    # everything else already transferred.
    if [[ -t 0 ]] || ssh -o BatchMode=yes "$HOST" "sudo -n true" 2>/dev/null; then
        log "Installing /opt/ipr_common.env (requires sudo on the device) ..."
        run ssh -t "$HOST" "
            sudo mv /tmp/ipr_common.env /opt/ipr_common.env
            sudo chmod 0600 /opt/ipr_common.env
        "
    else
        warn "No terminal available, and passwordless sudo is not configured on"
        warn "$HOST, so /opt/ipr_common.env cannot be installed from here."
        warn "The file has been transferred and is waiting at /tmp/ipr_common.env."
        warn "Finish it yourself with:"
        warn "  ssh $HOST \"sudo mv /tmp/ipr_common.env /opt/ipr_common.env && sudo chmod 0600 /opt/ipr_common.env\""
    fi
fi

$DRY_RUN && { log "Dry run complete — nothing was changed."; exit 0; }

log ""
log "Done. Continue on the device:"
log "  ssh $HOST"
log "  sudo $REMOTE_DIR/scripts/deploy/device_bootstrap.sh"
