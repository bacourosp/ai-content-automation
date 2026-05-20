#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "run as root"
  exit 1
fi

apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates \
  python3 \
  python3-venv \
  python3-pip \
  sqlite3

exit 0
