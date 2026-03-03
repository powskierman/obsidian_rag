#!/bin/bash

# Define variables
LABEL="com.obsidianrag.unified"
PLIST_NAME="${LABEL}.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$PLIST_NAME"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
APP_SUPPORT_DIR="$HOME/Library/Application Support/obsidian_rag"
WRAPPER_SCRIPT="$APP_SUPPORT_DIR/start_obsidian_rag_launchd.sh"
TERMINAL_SCRIPT="$APP_SUPPORT_DIR/start_obsidian_rag_terminal.command"

# Ensure LaunchAgents directory exists
mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$LOG_DIR"
mkdir -p "$APP_SUPPORT_DIR"

cat <<EOF > "$TERMINAL_SCRIPT"
#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$PROJECT_ROOT"
exec /bin/bash "\$PROJECT_ROOT/Scripts/setup/start_obsidian_rag.sh"
EOF

cat <<EOF > "$WRAPPER_SCRIPT"
#!/bin/bash
set -euo pipefail

TERMINAL_SCRIPT="$TERMINAL_SCRIPT"

open -a Terminal "\$TERMINAL_SCRIPT"
EOF

chmod 755 "$WRAPPER_SCRIPT" "$TERMINAL_SCRIPT"

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
        <string>/bin/bash</string>
        <string>$WRAPPER_SCRIPT</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/launch_agent.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/launch_agent.error.log</string>
    <key>WorkingDirectory</key>
    <string>$APP_SUPPORT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>OLLAMA_HOST</key>
        <string>0.0.0.0:11434</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Created LaunchAgent at $PLIST_PATH"
echo "✅ Installed launch wrapper at $WRAPPER_SCRIPT"
echo "✅ Installed Terminal bootstrap at $TERMINAL_SCRIPT"

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
