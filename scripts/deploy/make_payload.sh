#!/usr/bin/env bash
#
# make_payload.sh
#
# Build a deployment payload containing only the files the target device needs.
#
# The repository holds roughly 29 MB once .git, .venv, docs, tests and local
# logs are counted.  The device needs about 1 MB of that.  Transferring the
# whole tree is not just wasteful: it also carries config.json, users.json,
# secret_key.txt and admin_initial_password.txt — gitignored, device-specific
# files that would overwrite the target's own configuration and place this
# machine's session key and a plaintext admin password on it — plus .venv/,
# which is built for the wrong CPU architecture.
#
# This script is the single source of truth for that file list.  The
# administrator manual (section 3.3) documents the procedure; when the list
# changes, change it here and update the manual's table to match.
#
# Runs on the administrator PC (Git Bash, WSL or Linux), not on the device.
#
# Usage:
#   ./scripts/deploy/make_payload.sh                    # -> /tmp/ipr-deploy.tgz
#   ./scripts/deploy/make_payload.sh -o ipr.tgz         # custom output path
#   ./scripts/deploy/make_payload.sh --with-tests       # include tests/ (dev device)
#   ./scripts/deploy/make_payload.sh --list             # print the file list and exit
#
# category: Deploy
# purpose: Pack only the files the device needs into a transferable archive
# sudo: no

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ---------------------------------------------------------------------------
# The payload — the single source of truth
#
# Every entry is justified; do not add anything here without a reason the
# device actually needs at provisioning or run time.
# ---------------------------------------------------------------------------
PAYLOAD=(
    "src"                  # the package, including web/templates and web/static
    "provision"            # provisioning steps 00-07
    "scripts"              # deploy, service, ble and headless scripts
    "pyproject.toml"       # required by 'uv pip install -e .'
    "README.md"            # pyproject.toml sets readme = "README.md"; the
                           # editable install fails without it
    "config.default.json"  # read at run time by utils/helpers.py
    "users.default.json"   # read at run time by web/auth.py
    "uv.lock"              # only needed if 'uv sync' is run on the device
)

# Optional, dev device only: lets test-on-rpi run pytest on the target.
PAYLOAD_TESTS=("tests")

# Never allowed in the archive.  Checked after packing, so a careless edit to
# PAYLOAD cannot leak them silently.
FORBIDDEN=(
    "config.json"
    "users.json"
    "secret_key.txt"
    "admin_initial_password.txt"
    ".venv"
    ".git"
    "logs"
)

OUTPUT="/tmp/ipr-deploy.tgz"
WITH_TESTS=false
LIST_ONLY=false

log() { echo "[make_payload] $*"; }
die() { echo "[make_payload] ERROR: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        -o|--output)  OUTPUT="$2"; shift 2 ;;
        --with-tests) WITH_TESTS=true; shift ;;
        --list)       LIST_ONLY=true; shift ;;
        -h|--help)    sed -n '2,29p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *)            die "Unknown argument: $1" ;;
    esac
done

$WITH_TESTS && PAYLOAD+=("${PAYLOAD_TESTS[@]}")

if $LIST_ONLY; then
    printf '%s\n' "${PAYLOAD[@]}"
    exit 0
fi

cd "$REPO_ROOT"

# ---------------------------------------------------------------------------
# Verify every entry exists before packing, so a rename fails loudly here
# rather than producing a quietly incomplete archive.
# ---------------------------------------------------------------------------
missing=()
for item in "${PAYLOAD[@]}"; do
    [[ -e "$item" ]] || missing+=("$item")
done
if [[ ${#missing[@]} -gt 0 ]]; then
    die "Missing from $REPO_ROOT: ${missing[*]}"
fi

log "Packing ${#PAYLOAD[@]} entries from $REPO_ROOT ..."
tar -czf "$OUTPUT" "${PAYLOAD[@]}"

# ---------------------------------------------------------------------------
# Safety net: refuse to hand over an archive containing device-specific state
# ---------------------------------------------------------------------------
contents="$(tar tzf "$OUTPUT")"
leaked=()
for bad in "${FORBIDDEN[@]}"; do
    if grep -qE "(^|/)${bad//./\\.}(/|$)" <<<"$contents"; then
        leaked+=("$bad")
    fi
done
if [[ ${#leaked[@]} -gt 0 ]]; then
    rm -f "$OUTPUT"
    die "Archive contained forbidden entries and was deleted: ${leaked[*]}"
fi

size="$(du -h "$OUTPUT" | cut -f1)"
files="$(wc -l <<<"$contents")"
log "Wrote $OUTPUT  ($size, $files entries)"
log ""
log "Transfer and unpack:"
log "  scp $OUTPUT <host>:/tmp/"
log "  ssh <host> \"mkdir -p ~/dev/ipr-keyboard && \\"
log "    tar xzf /tmp/$(basename "$OUTPUT") -C ~/dev/ipr-keyboard && \\"
log "    rm /tmp/$(basename "$OUTPUT")\""
log ""
log "Windows has no execute bit — restore it on the device afterwards:"
log "  ssh <host> \"find ~/dev/ipr-keyboard/scripts ~/dev/ipr-keyboard/provision \\"
log "    \\( -name '*.sh' -o -name '*.py' \\) -exec chmod +x {} +\""
