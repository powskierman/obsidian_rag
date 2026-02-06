#!/bin/bash
# Package essential files for AirDrop to Mac Mini
#
# This creates a compressed archive with everything needed for Mac Mini setup,
# avoiding the wait for iCloud sync.

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║          Package Files for AirDrop to Mac Mini          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Create package directory name with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PACKAGE_NAME="obsidian_rag_mac_mini_${TIMESTAMP}"
PACKAGE_DIR="/tmp/${PACKAGE_NAME}"

echo "📦 Creating package directory..."
mkdir -p "$PACKAGE_DIR"

echo "✅ Package directory: $PACKAGE_DIR"
echo ""

# Current project directory
PROJECT_DIR="/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"
cd "$PROJECT_DIR"

echo "📂 Copying essential files..."
echo ""

# 1. LightRAG database (most important!)
echo "  1/8 Copying lightrag_db/ (152 MB - this may take a minute)..."
cp -R lightrag_db "$PACKAGE_DIR/"
echo "      ✅ Database copied"

# 2. Scripts
echo "  2/8 Copying Scripts/..."
cp -R Scripts "$PACKAGE_DIR/"
echo "      ✅ Scripts copied"

# 3. Source code
echo "  3/8 Copying src/integrations/..."
mkdir -p "$PACKAGE_DIR/src/integrations"
cp src/integrations/lightrag_service.py "$PACKAGE_DIR/src/integrations/"
echo "      ✅ LightRAG service copied"

# 4. Docker files
echo "  4/8 Copying Docker configuration..."
cp Dockerfile.lightrag "$PACKAGE_DIR/"
mkdir -p "$PACKAGE_DIR/config/docker"
cp config/docker/docker-compose.yml "$PACKAGE_DIR/config/docker/"
if [ -f "config/docker/Dockerfile.gateway" ]; then
    cp config/docker/Dockerfile.gateway "$PACKAGE_DIR/config/docker/" 2>/dev/null || true
fi
echo "      ✅ Docker files copied"

# 5. Documentation
echo "  5/8 Copying documentation..."
cp MAC_MINI_QUICK_START.md "$PACKAGE_DIR/" 2>/dev/null || echo "      ⚠️  MAC_MINI_QUICK_START.md not found"
mkdir -p "$PACKAGE_DIR/Documentation"
cp Documentation/DUAL_GRAPH_ARCHITECTURE.md "$PACKAGE_DIR/Documentation/" 2>/dev/null || true
echo "      ✅ Documentation copied"

# 6. Environment file (if exists)
echo "  6/8 Copying .env file (if present)..."
if [ -f ".env" ]; then
    cp .env "$PACKAGE_DIR/"
    echo "      ✅ .env file copied"
else
    echo "      ⚠️  No .env file found - you'll need to set API keys manually"
fi

# 7. .gitignore (for reference)
echo "  7/8 Copying .gitignore..."
cp .gitignore "$PACKAGE_DIR/" 2>/dev/null || true
echo "      ✅ .gitignore copied"

# 8. Create README for Mac Mini
echo "  8/8 Creating extraction instructions..."
cat > "$PACKAGE_DIR/README_MAC_MINI.txt" << 'EOF'
╔══════════════════════════════════════════════════════════╗
║              Obsidian RAG - Mac Mini Setup               ║
╚══════════════════════════════════════════════════════════╝

This package contains everything needed to run LightRAG indexing
on your Mac Mini.

QUICK START
═══════════

1. Extract this folder to your Desktop
   (AirDrop should have already done this)

2. Run the setup script:

   cd ~/Desktop/obsidian_rag_mac_mini_*/
   chmod +x Scripts/setup_mac_mini.sh
   ./Scripts/setup_mac_mini.sh

3. Follow the prompts!

The setup script will:
  ✓ Check prerequisites (Docker, Ollama)
  ✓ Build Docker images
  ✓ Load your database
  ✓ Verify everything works

After setup completes, run indexing:

   ./Scripts/index_lightrag_with_kimi.sh

═══════════════════════════════════════════════════════════

MANUAL EXTRACTION (if needed)
══════════════════════════════

If you want to extract to the standard iCloud location:

1. Create the directory:
   mkdir -p "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"

2. Copy files:
   cd ~/Desktop/obsidian_rag_mac_mini_*/
   cp -R * "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/"

3. Run setup:
   cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"
   ./Scripts/setup_mac_mini.sh

═══════════════════════════════════════════════════════════

WHAT'S INCLUDED
═══════════════

✓ lightrag_db/           - Your knowledge graph database (152 MB)
✓ Scripts/               - Setup and indexing scripts
✓ src/integrations/      - LightRAG service code
✓ Dockerfile.lightrag    - Docker build configuration
✓ config/docker/         - Docker Compose setup
✓ Documentation/         - System architecture docs
✓ .env                   - Environment variables (if present)

═══════════════════════════════════════════════════════════

TROUBLESHOOTING
═══════════════

If setup fails:
  1. Check Docker is installed and running
  2. Check Ollama is installed: brew install ollama
  3. Read: MAC_MINI_QUICK_START.md

For detailed help, see:
  open MAC_MINI_QUICK_START.md

═══════════════════════════════════════════════════════════
Package created: $(date)
EOF

echo "      ✅ README created"
echo ""

# Create compressed archive
echo "📦 Creating compressed archive..."
cd /tmp

# Use tar.gz for better compatibility
tar -czf "${PACKAGE_NAME}.tar.gz" "$PACKAGE_NAME"

ARCHIVE_SIZE=$(du -sh "${PACKAGE_NAME}.tar.gz" | cut -f1)
echo "✅ Archive created: ${PACKAGE_NAME}.tar.gz"
echo "📊 Archive size: $ARCHIVE_SIZE"
echo ""

# Move to Desktop for easy AirDrop
DESKTOP="$HOME/Desktop"
mv "${PACKAGE_NAME}.tar.gz" "$DESKTOP/"

echo "📍 Archive location: $DESKTOP/${PACKAGE_NAME}.tar.gz"
echo ""

# Cleanup temp directory
rm -rf "$PACKAGE_DIR"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║                  ✅ Package Ready!                        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "📤 Next steps:"
echo ""
echo "  1. Find the archive on your Desktop:"
echo "     ${PACKAGE_NAME}.tar.gz"
echo ""
echo "  2. AirDrop to Mac Mini:"
echo "     • Right-click the .tar.gz file"
echo "     • Select 'Share' → 'AirDrop'"
echo "     • Choose your Mac Mini"
echo ""
echo "  3. On Mac Mini, extract the archive:"
echo "     • File will arrive in Downloads folder"
echo "     • Double-click to extract"
echo "     • Or: tar -xzf ${PACKAGE_NAME}.tar.gz"
echo ""
echo "  4. Run the setup script:"
echo "     cd ~/Downloads/${PACKAGE_NAME}/"
echo "     ./Scripts/setup_mac_mini.sh"
echo ""
echo "💡 Alternative: Create uncompressed folder for AirDrop"
echo "   (Better if AirDrop struggles with .tar.gz files)"
echo ""

# Ask if user wants uncompressed version too
read -p "Create uncompressed folder version too? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "📦 Creating uncompressed folder..."
    cp -R "/tmp/${PACKAGE_NAME}" "$DESKTOP/"
    echo "✅ Uncompressed folder created on Desktop"
    echo ""
    echo "You can now AirDrop either:"
    echo "  • ${PACKAGE_NAME}.tar.gz (compressed, smaller)"
    echo "  • ${PACKAGE_NAME}/ (folder, easier to extract)"
fi

echo ""
echo "🎉 Ready to AirDrop to Mac Mini!"
echo ""
