#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-}"

case "$TARGET" in
  *.env|*secrets*|*terraform.tfstate|*generated/*)
    echo "Editing protected or generated material is blocked by repository policy."
    exit 2
    ;;
esac
