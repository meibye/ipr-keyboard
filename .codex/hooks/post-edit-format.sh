#!/usr/bin/env bash
set -euo pipefail

if [ -f package.json ]; then
  npm run format --if-present || true
fi

if [ -f pyproject.toml ]; then
  uv run ruff format . || true
fi
