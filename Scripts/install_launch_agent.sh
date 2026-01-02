#!/bin/bash

# Define variables
LABEL="com.obsidianrag.webapp"
PLIST_NAME="${LABEL}.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$PLIST_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
START_SCRIPT="$SCRIPT_DIR/start_webapp.sh"

# Ensure LaunchAgents directory exists
mkdir -p "$LAUNCH_AGENTS_DIR"

# Create the plist content
cat <<EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$START_SCRIPT</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/logs/launch_agent.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/logs/launch_agent.error.log</string>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR/../webapp</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Created LaunchAgent at $PLIST_PATH"

# Load the LaunchAgent
# Unload first if it exists to ensure clean reload
launchctl bootout gui/$(id -u) "$PLIST_PATH" 2>/dev/null
launchctl bootstrap gui/$(id -u) "$PLIST_PATH"

if [ $? -eq 0 ]; then
    echo "🚀 Successfully loaded LaunchAgent. Webapp will start automatically on login."
    echo "To check status: launchctl list | grep $LABEL"
    echo "To uninstall: launchctl bootout gui/$(id -u) $PLIST_PATH && rm $PLIST_PATH"
else
    echo "❌ Failed to load LaunchAgent."
fi
