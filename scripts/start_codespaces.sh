#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ ! -x .codespaces-venv/bin/python ]]; then
  echo '먼저 python3 scripts/setup_codespaces.py 를 실행하세요.' >&2
  exit 1
fi
exec .codespaces-venv/bin/python -m media_clarity.codespaces --start
