#!/bin/bash
# Install a LaunchAgent that periodically heals MLX and api-gateway on Canmore.

set -euo pipefail

LABEL="com.obsidianrag.recovery"
PLIST_NAME="${LABEL}.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$PLIST_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
RECOVERY_SCRIPT="$SCRIPT_DIR/recover_api_gateway_and_mlx.sh"
INTERVAL_SECONDS="${1:-60}"

mkdir -p "$LAUNCH_AGENTS_DIR" "$LOG_DIR"

cat <<EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$RECOVERY_SCRIPT</string>
        <string>--watchdog</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>$INTERVAL_SECONDS</integer>
    <key>WorkingDirectory</key>
    <string>$PROJECT_ROOT</string>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/recovery.launchd.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/recovery.launchd.error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

chmod 755 "$RECOVERY_SCRIPT"

launchctl bootout gui/$(id -u) "$PLIST_PATH" 2>/dev/null || true
launchctl bootstrap gui/$(id -u) "$PLIST_PATH"

echo "✅ Installed recovery LaunchAgent: $PLIST_PATH"
echo "⏱️  Check interval: ${INTERVAL_SECONDS}s"
echo "📝 Logs:"
echo "   $LOG_DIR/recovery.log"
echo "   $LOG_DIR/recovery.launchd.log"
echo "   $LOG_DIR/recovery.launchd.error.log"
echo "🔍 Status: launchctl list | grep $LABEL"
echo "🗑️  Uninstall: launchctl bootout gui/$(id -u) $PLIST_PATH && rm $PLIST_PATH"
