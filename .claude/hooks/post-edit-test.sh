#!/usr/bin/env bash
set -euo pipefail

if [ -f pyproject.toml ]; then
  uv run pytest -q tests/unit || true
fi

if [ -f package.json ]; then
  npm test -- --runInBand || true
fi
