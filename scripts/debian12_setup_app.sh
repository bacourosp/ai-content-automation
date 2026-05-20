#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$APP_DIR"

python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -q --upgrade pip
python3 -m pip install -q -r requirements.txt
python3 -m pip install -q -r requirements-dev.txt
python3 -m pip install -q -e .

python3 -m xai_automation.cli init-db
