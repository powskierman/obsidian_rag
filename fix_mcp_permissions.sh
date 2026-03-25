#!/bin/bash
# Fix MCP iCloud Access Issues

set -e

echo "=== MCP iCloud Access Fix Script ==="
echo

# Load environment
if [ -f .env ]; then
    source .env
fi

VAULT_PATH="${OBSIDIAN_VAULT_PATH}"

if [ -z "$VAULT_PATH" ]; then
    echo "❌ OBSIDIAN_VAULT_PATH not set in .env"
    exit 1
fi

echo "Current vault path: $VAULT_PATH"
echo

# Option 1: Download all iCloud files
echo "Option 1: Download all iCloud files locally"
echo "This ensures all vault files are available locally, not just in iCloud."
echo
read -p "Download all iCloud vault files? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Downloading files... (this may take a while)"
    cd "$VAULT_PATH"

    # Count files first
    TOTAL_FILES=$(find . -type f \( -name "*.md" -o -name "*.pdf" \) | wc -l | tr -d ' ')
    echo "Found $TOTAL_FILES files to download"

    if command -v brctl &> /dev/null; then
        find . -type f \( -name "*.md" -o -name "*.pdf" \) -print0 | while IFS= read -r -d '' file; do
            brctl download "$file" 2>/dev/null || true
        done
        echo "✓ Download complete"
    else
        echo "⚠️  brctl command not available. Files will download on access."
    fi
fi

echo

# Option 2: Create a symlink
echo "Option 2: Create a symlink for easier access"
echo "This creates /Users/michel/obsidian_vault -> iCloud vault"
echo
read -p "Create symlink? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SYMLINK_PATH="/Users/michel/obsidian_vault"

    if [ -L "$SYMLINK_PATH" ]; then
        echo "Symlink already exists: $SYMLINK_PATH"
    elif [ -e "$SYMLINK_PATH" ]; then
        echo "❌ Path already exists and is not a symlink: $SYMLINK_PATH"
    else
        ln -s "$VAULT_PATH" "$SYMLINK_PATH"
        echo "✓ Created symlink: $SYMLINK_PATH -> $VAULT_PATH"
        echo
        echo "Update your .env file to use:"
        echo 'OBSIDIAN_VAULT_PATH="/Users/michel/obsidian_vault"'
    fi
fi

echo

# Option 3: Fix permissions
echo "Option 3: Check and fix permissions"
echo
read -p "Check permissions? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Current permissions:"
    ls -ld "$VAULT_PATH"

    echo
    echo "Checking file permissions..."

    # Find files with restricted permissions
    RESTRICTED=$(find "$VAULT_PATH" -type f \( -name "*.md" -o -name "*.pdf" \) ! -perm -u=r 2>/dev/null | wc -l | tr -d ' ')

    if [ "$RESTRICTED" -gt 0 ]; then
        echo "Found $RESTRICTED files with restricted read permissions"
        read -p "Fix permissions? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            find "$VAULT_PATH" -type f \( -name "*.md" -o -name "*.pdf" \) ! -perm -u=r -exec chmod u+r {} \;
            echo "✓ Fixed permissions"
        fi
    else
        echo "✓ All files have read permissions"
    fi
fi

echo
echo "=== Fix Script Complete ==="
echo
echo "Next steps:"
echo "1. Run ./diagnose_mcp_access.sh to verify the fixes"
echo "2. Test MCP connection from your MacBook"
echo "3. If issues persist, consider moving the vault out of iCloud"
