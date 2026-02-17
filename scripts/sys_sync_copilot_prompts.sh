#!/usr/bin/env bash
#
# category: System Setup
# purpose: Sync and verify no-drift prompt mirrors from docs/copilot
# parameters: --sync,--check,--help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_DIR="${REPO_ROOT}/docs/copilot"
TARGET_DIRS=(
  "${REPO_ROOT}/.github/prompts/copilot"
  "${REPO_ROOT}/scripts/docs/copilot"
)

MODE="${1:---sync}"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/sys_sync_copilot_prompts.sh --sync   # copy source prompts and remove drift
  ./scripts/sys_sync_copilot_prompts.sh --check  # fail if any mirror drifts
EOF
}

require_source_dir() {
  if [[ ! -d "${SOURCE_DIR}" ]]; then
    echo "ERROR: source directory not found: ${SOURCE_DIR}" >&2
    exit 1
  fi
}

collect_source_files() {
  mapfile -t SOURCE_FILES < <(
    find "${SOURCE_DIR}" -maxdepth 1 -type f -name '*.md' -printf '%f\n' | sort
  )
  if [[ "${#SOURCE_FILES[@]}" -eq 0 ]]; then
    echo "ERROR: no source markdown files found under ${SOURCE_DIR}" >&2
    exit 1
  fi
}

in_source_set() {
  local name="$1"
  local src
  for src in "${SOURCE_FILES[@]}"; do
    [[ "${src}" == "${name}" ]] && return 0
  done
  return 1
}

sync_target_dir() {
  local target_dir="$1"
  mkdir -p "${target_dir}"

  local file
  for file in "${SOURCE_FILES[@]}"; do
    cp "${SOURCE_DIR}/${file}" "${target_dir}/${file}"
  done

  mapfile -t TARGET_MD_FILES < <(
    find "${target_dir}" -maxdepth 1 -type f -name '*.md' -printf '%f\n' | sort
  )
  for file in "${TARGET_MD_FILES[@]}"; do
    if ! in_source_set "${file}"; then
      rm -f "${target_dir}/${file}"
    fi
  done
}

check_target_dir() {
  local target_dir="$1"
  local has_drift=0
  local file

  if [[ ! -d "${target_dir}" ]]; then
    echo "DRIFT: missing target directory ${target_dir}"
    return 1
  fi

  for file in "${SOURCE_FILES[@]}"; do
    if [[ ! -f "${target_dir}/${file}" ]]; then
      echo "DRIFT: missing file ${target_dir}/${file}"
      has_drift=1
      continue
    fi
    if ! cmp -s "${SOURCE_DIR}/${file}" "${target_dir}/${file}"; then
      echo "DRIFT: content mismatch ${target_dir}/${file}"
      has_drift=1
    fi
  done

  mapfile -t TARGET_MD_FILES < <(
    find "${target_dir}" -maxdepth 1 -type f -name '*.md' -printf '%f\n' | sort
  )
  for file in "${TARGET_MD_FILES[@]}"; do
    if ! in_source_set "${file}"; then
      echo "DRIFT: extra file ${target_dir}/${file}"
      has_drift=1
    fi
  done

  [[ "${has_drift}" -eq 0 ]]
}

run_sync() {
  local target_dir
  for target_dir in "${TARGET_DIRS[@]}"; do
    sync_target_dir "${target_dir}"
  done
  echo "Synced prompt mirrors from ${SOURCE_DIR}"
}

run_check() {
  local target_dir
  local has_errors=0
  for target_dir in "${TARGET_DIRS[@]}"; do
    if ! check_target_dir "${target_dir}"; then
      has_errors=1
    fi
  done

  if [[ "${has_errors}" -ne 0 ]]; then
    echo "No-drift check failed."
    exit 1
  fi
  echo "No-drift check passed."
}

require_source_dir
collect_source_files

case "${MODE}" in
  --sync)
    run_sync
    run_check
    ;;
  --check)
    run_check
    ;;
  --help|-h)
    usage
    ;;
  *)
    echo "ERROR: unknown option ${MODE}" >&2
    usage
    exit 1
    ;;
esac
