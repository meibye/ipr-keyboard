#!/usr/bin/env bash
# PostToolUse hook: format only the file that was just edited.
#
# Claude Code passes the tool call as JSON on stdin; the edited path is
# .tool_input.file_path.  Formatting the whole tree here used to dirty ~50
# unrelated (never formatted) files on every edit and made diffs unreviewable.
set -euo pipefail

# jq is not guaranteed (Windows Git Bash); python is, since the project needs it.
# Prefer the project venv: on Windows a bare "python3" may be the Store stub.
PY=""
for cand in .venv/bin/python .venv/Scripts/python.exe "$(command -v python || true)" "$(command -v python3 || true)"; do
  if [ -n "$cand" ] && [ -x "$cand" ] && "$cand" -c 'pass' >/dev/null 2>&1; then PY="$cand"; break; fi
done
[ -n "$PY" ] || exit 0
# Print the edited path only when it lies inside this repository (the hook's
# working directory).  Files elsewhere -- scratch scripts, other checkouts --
# must not be touched: formatting them corrupts patch scripts and the like.
HOOK_INPUT="$(cat)"
export HOOK_INPUT
FILE="$("$PY" -c '
import json, os, sys
try:
    path = json.loads(os.environ.get("HOOK_INPUT", "")).get("tool_input", {}).get("file_path", "")
except Exception:
    path = ""
if path:
    root = os.path.realpath(os.getcwd())
    full = os.path.realpath(path)
    try:
        inside = os.path.commonpath([root, full]) == root
    except ValueError:  # different drives on Windows
        inside = False
    print(full if inside else "")
' 2>/dev/null || true)"
[ -n "$FILE" ] || exit 0
[ -f "$FILE" ] || exit 0

case "$FILE" in
  *.py)
    if [ -f pyproject.toml ]; then
      uv run ruff format "$FILE" || true
    fi
    ;;
  *.js|*.jsx|*.ts|*.tsx|*.json|*.css|*.md)
    if [ -f package.json ] && command -v npx >/dev/null 2>&1; then
      npx --no-install prettier --write "$FILE" >/dev/null 2>&1 || true
    fi
    ;;
esac
