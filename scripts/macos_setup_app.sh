#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

PY="${PYTHON_BIN:-python3}"

if ! command -v "$PY" >/dev/null 2>&1; then
  echo "python3 not found. Install Python 3.11+ (brew install python) or use /usr/bin/python3 if available."
  exit 1
fi

"$PY" -m venv .venv
source .venv/bin/activate
"$PY" -m pip install -q --upgrade pip
"$PY" -m pip install -q -r requirements.txt
"$PY" -m pip install -q -r requirements-dev.txt
"$PY" -m pip install -q -e .

xai-automation init-db
