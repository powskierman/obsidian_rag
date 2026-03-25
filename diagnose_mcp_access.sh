#!/bin/bash
# MCP iCloud Access Diagnostic Script

echo "=== MCP iCloud Access Diagnostics ==="
echo

# Load environment
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

VAULT_PATH="${OBSIDIAN_VAULT_PATH}"
echo "1. Vault Path Configuration"
echo "   OBSIDIAN_VAULT_PATH: $VAULT_PATH"
echo

# Check if vault directory exists
echo "2. Vault Directory Existence"
if [ -d "$VAULT_PATH" ]; then
    echo "   ✓ Vault directory exists"
else
    echo "   ✗ Vault directory does NOT exist"
    exit 1
fi
echo

# Check permissions
echo "3. Permissions Check"
echo "   Current user: $(whoami)"
echo "   User ID: $(id -u)"
echo "   Group ID: $(id -g)"
ls -ld "$VAULT_PATH"
echo

# Check if we can list files
echo "4. Directory Listing Test"
FILE_COUNT=$(find "$VAULT_PATH" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
if [ "$FILE_COUNT" -gt 0 ]; then
    echo "   ✓ Can list files: $FILE_COUNT markdown files found"
else
    echo "   ✗ Cannot list files or no files found"
fi
echo

# Check if we can read a sample file
echo "5. File Read Test"
SAMPLE_FILE=$(find "$VAULT_PATH" -name "*.md" 2>/dev/null | head -n 1)
if [ -n "$SAMPLE_FILE" ]; then
    echo "   Testing file: $SAMPLE_FILE"
    if [ -r "$SAMPLE_FILE" ]; then
        echo "   ✓ Can read file"
        FILE_SIZE=$(wc -c < "$SAMPLE_FILE" 2>/dev/null)
        echo "   File size: $FILE_SIZE bytes"
    else
        echo "   ✗ Cannot read file"
        ls -l "$SAMPLE_FILE"
    fi
else
    echo "   ✗ No sample file found"
fi
echo

# Check iCloud status
echo "6. iCloud Status"
if command -v brctl &> /dev/null; then
    echo "   Checking iCloud sync status..."
    brctl log --wait --shorten 2>/dev/null | head -n 5 || echo "   (brctl command available but no immediate status)"
else
    echo "   brctl not available (this is OK on older macOS)"
fi
echo

# Check for cloud-only files
echo "7. Cloud-Only Files Check"
if [ -d "$VAULT_PATH" ]; then
    CLOUD_ONLY=$(find "$VAULT_PATH" -name "*.md" -type f -print0 2>/dev/null | xargs -0 mdls -name kMDItemFSName -name kMDItemUseCount 2>/dev/null | grep -c "^kMDItemUseCount = 0$" || echo "0")
    echo "   Checking for files that may not be downloaded..."
    echo "   (This check is approximate)"
fi
echo

# MCP test
echo "8. MCP Environment"
echo "   API Gateway: ${API_GATEWAY_URL:-http://localhost:4000}"
echo "   MCP Gateway: ${MCP_GATEWAY_URL:-http://localhost:4000}"
echo

# Test Python file access
echo "9. Python File Access Test"
python3 << 'PYTHON_TEST'
import os
import sys
from pathlib import Path

vault_path = os.getenv("OBSIDIAN_VAULT_PATH", "")
if not vault_path:
    print("   ✗ OBSIDIAN_VAULT_PATH not set")
    sys.exit(1)

vault = Path(vault_path).expanduser().resolve()
print(f"   Resolved path: {vault}")

if not vault.exists():
    print("   ✗ Path does not exist")
    sys.exit(1)

try:
    md_files = list(vault.rglob("*.md"))
    print(f"   ✓ Python can list files: {len(md_files)} markdown files")

    if md_files:
        sample = md_files[0]
        try:
            with open(sample, 'r', encoding='utf-8') as f:
                content = f.read(100)
            print(f"   ✓ Python can read files")
            print(f"   Sample: {sample.name}")
        except Exception as e:
            print(f"   ✗ Python cannot read file: {e}")
except Exception as e:
    print(f"   ✗ Error: {e}")
PYTHON_TEST

echo
echo "=== Diagnostics Complete ==="
