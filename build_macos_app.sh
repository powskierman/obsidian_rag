#!/bin/bash

APP_NAME="Obsidian RAG"
APP_DIR="${APP_NAME}.app"
CONTENTS_DIR="${APP_DIR}/Contents"
MACOS_DIR="${CONTENTS_DIR}/MacOS"
RESOURCES_DIR="${CONTENTS_DIR}/Resources"
START_SCRIPT="scripts/start_obsidian_rag.sh"
ICON_SOURCE="/Users/michel/.gemini/antigravity/brain/bfd492fd-2c46-4d52-a9a9-6ba330c7bf6a/obsidian_rag_icon_v1_1766690976080.png"
ICON_DEST="${RESOURCES_DIR}/applet.icns"

echo "🏗️ Building ${APP_NAME}.app..."

# 1. Create Directory Structure
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR"

# 2. Create Info.plist
cat > "${CONTENTS_DIR}/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>applet</string>
    <key>CFBundleIdentifier</key>
    <string>com.michel.obsidianrag</string>
    <key>CFBundleName</key>
    <string>${APP_NAME}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.10</string>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
EOF

# 3. Create Launcher Script (The generic binary equivalent)
# We use a shell script wrapper as the executable
cat > "${MACOS_DIR}/launcher" <<EOF
#!/bin/bash
# Get the absolute path to the project root (where the app is likely located, or hardcode it)
# Assuming the App is placed in the project root for now, or we hardcode the path.
# Better yet, let's point to the absolute path of the start script we know.

PROJECT_ROOT="/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"
START_SCRIPT="\$PROJECT_ROOT/scripts/start_obsidian_rag.sh"

if [ -f "\$START_SCRIPT" ]; then
    # Open Terminal and run the script
    osascript -e "tell application \"Terminal\" to do script \"'\$START_SCRIPT'\""
    osascript -e "tell application \"Terminal\" to activate"
else
    osa_script='display dialog "Startup script not found at:\n'
    osa_script+=\$START_SCRIPT
    osa_script+='"\n\nPlease ensure the project is at the correct location." buttons {"OK"} default button "OK" with icon stop with title "Error"'
    osascript -e "\$osa_script"
fi
EOF

chmod +x "${MACOS_DIR}/launcher"

# 4. Create ICNS Icon from PNG
if [ -f "$ICON_SOURCE" ]; then
    echo "🎨 Creating icon..."
    # Create a temporary iconset directory
    ICONSET_DIR="ObsidianRAG.iconset"
    mkdir -p "$ICONSET_DIR"

    # Create various sizes (sips is standard on macOS)
    sips -s format png -z 16 16     "$ICON_SOURCE" --out "${ICONSET_DIR}/icon_16x16.png" > /dev/null
    sips -s format png -z 32 32     "$ICON_SOURCE" --out "${ICONSET_DIR}/icon_16x16@2x.png" > /dev/null
    sips -s format png -z 32 32     "$ICON_SOURCE" --out "${ICONSET_DIR}/icon_32x32.png" > /dev/null
    sips -s format png -z 64 64     "$ICON_SOURCE" --out "${ICONSET_DIR}/icon_32x32@2x.png" > /dev/null
    sips -s format png -z 128 128   "$ICON_SOURCE" --out "${ICONSET_DIR}/icon_128x128.png" > /dev/null
    sips -s format png -z 256 256   "$ICON_SOURCE" --out "${ICONSET_DIR}/icon_128x128@2x.png" > /dev/null
    sips -s format png -z 256 256   "$ICON_SOURCE" --out "${ICONSET_DIR}/icon_256x256.png" > /dev/null
    sips -s format png -z 512 512   "$ICON_SOURCE" --out "${ICONSET_DIR}/icon_256x256@2x.png" > /dev/null
    sips -s format png -z 512 512   "$ICON_SOURCE" --out "${ICONSET_DIR}/icon_512x512.png" > /dev/null
    sips -s format png -z 1024 1024 "$ICON_SOURCE" --out "${ICONSET_DIR}/icon_512x512@2x.png" > /dev/null

    # Convert iconset to icns
    iconutil -c icns "$ICONSET_DIR" -o "$ICON_DEST"
    
    # Cleanup
    rm -rf "$ICONSET_DIR"
    echo "✅ Icon created at $ICON_DEST"
else
    echo "⚠️ Icon source not found at $ICON_SOURCE"
fi

echo "✅ App created at $(pwd)/${APP_NAME}.app"
echo "You can move this to your /Applications folder or Desktop."
