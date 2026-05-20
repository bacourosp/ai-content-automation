#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  echo "run as root"
  exit 1
fi

APP_DIR="${APP_DIR:-/opt/ai-content-automation}"
ENV_DIR="/etc/xai-automation"
ENV_FILE="$ENV_DIR/xai.env"

mkdir -p "$ENV_DIR"

if [ ! -f "$ENV_FILE" ]; then
  if [ -f "$APP_DIR/.env" ]; then
    cp "$APP_DIR/.env" "$ENV_FILE"
  else
    touch "$ENV_FILE"
  fi
  chmod 600 "$ENV_FILE"
fi

install -m 0644 "$APP_DIR/scripts/systemd/xai-automation-run.service" /etc/systemd/system/xai-automation-run.service
install -m 0644 "$APP_DIR/scripts/systemd/xai-automation-run.timer" /etc/systemd/system/xai-automation-run.timer
install -m 0644 "$APP_DIR/scripts/systemd/xai-automation-publish.service" /etc/systemd/system/xai-automation-publish.service
install -m 0644 "$APP_DIR/scripts/systemd/xai-automation-publish.timer" /etc/systemd/system/xai-automation-publish.timer
install -m 0644 "$APP_DIR/scripts/systemd/xai-automation-assets.service" /etc/systemd/system/xai-automation-assets.service

systemctl daemon-reload
systemctl enable --now xai-automation-run.timer
systemctl enable --now xai-automation-publish.timer
systemctl enable --now xai-automation-assets.service

exit 0
