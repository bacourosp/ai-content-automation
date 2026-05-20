#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
LA_DIR="${HOME}/Library/LaunchAgents"

mkdir -p "$LA_DIR"

RUN_PLIST="${LA_DIR}/com.xai.automation.run.plist"
PUB_PLIST="${LA_DIR}/com.xai.automation.publish.plist"
ASSET_PLIST="${LA_DIR}/com.xai.automation.assets.plist"

cat >"$RUN_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.xai.automation.run</string>
  <key>WorkingDirectory</key><string>${APP_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>XAI_ENV_FILE</key><string>${APP_DIR}/.env</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>${APP_DIR}/.venv/bin/xai-automation</string>
    <string>run-once</string>
  </array>
  <key>StartInterval</key><integer>900</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>${APP_DIR}/out/logs/run.out.log</string>
  <key>StandardErrorPath</key><string>${APP_DIR}/out/logs/run.err.log</string>
  <key>ProcessType</key><string>Background</string>
</dict>
</plist>
EOF

cat >"$PUB_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.xai.automation.publish</string>
  <key>WorkingDirectory</key><string>${APP_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>XAI_ENV_FILE</key><string>${APP_DIR}/.env</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>${APP_DIR}/.venv/bin/xai-automation</string>
    <string>process-queue</string>
    <string>--limit</string>
    <string>10</string>
  </array>
  <key>StartInterval</key><integer>600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>${APP_DIR}/out/logs/publish.out.log</string>
  <key>StandardErrorPath</key><string>${APP_DIR}/out/logs/publish.err.log</string>
  <key>ProcessType</key><string>Background</string>
</dict>
</plist>
EOF

cat >"$ASSET_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.xai.automation.assets</string>
  <key>WorkingDirectory</key><string>${APP_DIR}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>XAI_ENV_FILE</key><string>${APP_DIR}/.env</string>
  </dict>
  <key>ProgramArguments</key>
  <array>
    <string>${APP_DIR}/.venv/bin/xai-automation</string>
    <string>serve-assets</string>
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>${APP_DIR}/out/logs/assets.out.log</string>
  <key>StandardErrorPath</key><string>${APP_DIR}/out/logs/assets.err.log</string>
  <key>ProcessType</key><string>Background</string>
</dict>
</plist>
EOF

mkdir -p "${APP_DIR}/out/logs"

launchctl unload "$RUN_PLIST" >/dev/null 2>&1 || true
launchctl unload "$PUB_PLIST" >/dev/null 2>&1 || true
launchctl unload "$ASSET_PLIST" >/dev/null 2>&1 || true

launchctl load "$RUN_PLIST"
launchctl load "$PUB_PLIST"
launchctl load "$ASSET_PLIST"

exit 0
