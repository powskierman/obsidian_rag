# SSH MCP Setup Guide

This guide helps you set up MCP access from your MacBook to Canmore's Obsidian vault via SSH.

## Problem

When connecting from MacBook to Canmore via SSH/MCP:
- ✅ MCP can read the vector index (metadata + snippets)
- ❌ MCP cannot read full note content from iCloud Drive

## Root Cause

The Obsidian vault is stored in iCloud Drive:
```
/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel
```

SSH access to iCloud Drive can fail due to:
1. **Cloud-only files** - Files not downloaded locally
2. **Permission issues** - SSH user lacks access to iCloud directory
3. **User context** - SSH session runs as different user

## Quick Diagnosis

**On Canmore**, run the diagnostic:
```bash
cd /Users/michel/dev/obsidian_rag
./diagnose_mcp_access.sh
```

This checks:
- Vault directory existence
- File permissions
- iCloud sync status
- Python file access

## Solutions

### Solution 1: Download iCloud Files Locally (Recommended First Step)

```bash
cd /Users/michel/dev/obsidian_rag
./fix_mcp_permissions.sh
```

This script will:
- Download all vault files from iCloud to local storage
- Check and fix file permissions
- Optionally create a symlink for easier access

### Solution 2: Use a Symlink

Create a symlink outside the iCloud directory:

```bash
# On Canmore:
ln -s "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel" \
     /Users/michel/obsidian_vault
```

Update `.env`:
```bash
OBSIDIAN_VAULT_PATH="/Users/michel/obsidian_vault"
```

### Solution 3: Configure SSH MCP Properly

When setting up MCP on MacBook to connect to Canmore, ensure proper configuration.

**On MacBook** - MCP Client Configuration:

For ChatGPT Desktop App (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "obsidian-rag": {
      "command": "ssh",
      "args": [
        "michel@canmore",
        "/Users/michel/dev/obsidian_rag/venv/bin/python",
        "/Users/michel/dev/obsidian_rag/src/mcp/obsidian_rag_unified_mcp.py",
        "--log-level",
        "INFO"
      ],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel",
        "MCP_GATEWAY_URL": "http://localhost:4000",
        "API_GATEWAY_URL": "http://localhost:4000"
      }
    }
  }
}
```

**Important**: Ensure SSH key authentication is set up:

```bash
# On MacBook:
ssh-copy-id michel@canmore

# Test passwordless login:
ssh michel@canmore 'whoami'
```

### Solution 4: Port Forward API Gateway

If the MCP server needs to access the API Gateway on Canmore:

```bash
# On MacBook, create SSH tunnel:
ssh -L 4000:localhost:4000 michel@canmore -N -f
```

Or configure the MCP client to use the remote URL:
```json
"env": {
  "MCP_GATEWAY_URL": "http://canmore.local:4000"
}
```

### Solution 5: Move Vault Out of iCloud (Last Resort)

If iCloud continues to cause issues:

```bash
# On Canmore:
# 1. Copy vault to local directory
sudo mkdir -p /usr/local/obsidian_vault
sudo chown michel:staff /usr/local/obsidian_vault
rsync -av --progress \
  "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/" \
  /usr/local/obsidian_vault/

# 2. Update .env
# OBSIDIAN_VAULT_PATH="/usr/local/obsidian_vault"

# 3. Reconfigure Obsidian to use new location
```

⚠️ **Warning**: This breaks iCloud sync. You'll need to set up alternative sync (Git, Syncthing, etc.)

## Testing the Setup

### Test 1: Local Access on Canmore

```bash
cd /Users/michel/dev/obsidian_rag
source venv/bin/activate

# Test vault access
python -c "
import os
from pathlib import Path
vault = Path(os.getenv('OBSIDIAN_VAULT_PATH', '')).expanduser()
print(f'Vault exists: {vault.exists()}')
md_files = list(vault.rglob('*.md'))
print(f'Found {len(md_files)} markdown files')
if md_files:
    with open(md_files[0]) as f:
        print(f'Can read: {md_files[0].name}')
"
```

### Test 2: SSH Access from MacBook

```bash
# On MacBook:
ssh michel@canmore "cd /Users/michel/dev/obsidian_rag && \
  source venv/bin/activate && \
  python -c \"import os; from pathlib import Path; print(list(Path(os.getenv('OBSIDIAN_VAULT_PATH', '')).rglob('*.md'))[:5])\""
```

### Test 3: MCP Tools

After configuring MCP client, test with Claude:

```
Use the search_vault tool to search for "test"
```

Claude should be able to:
1. Search the vector index ✅
2. Retrieve full note content ✅
3. Read PDF attachments ✅

## Common Issues

### Issue: "Permission Denied"

**Cause**: SSH user doesn't have read permissions on iCloud directory

**Fix**:
```bash
# On Canmore:
chmod -R u+r "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
```

### Issue: "File Not Found" despite vault existing

**Cause**: Files are cloud-only (not downloaded)

**Fix**:
```bash
# Download all files
cd "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
find . -type f -name "*.md" -exec brctl download {} \; 2>/dev/null
```

### Issue: MCP can't reach API Gateway

**Cause**: Network routing between MacBook and Canmore

**Fix**:
- Use SSH tunnel (see Solution 4)
- Or expose API Gateway on Canmore's network interface
- Or run MCP server directly on Canmore (access via HTTP MCP transport)

### Issue: Slow Performance

**Cause**: Network latency over SSH

**Consider**:
- Running Claude Desktop directly on Canmore
- Using HTTP MCP transport instead of SSH stdio
- Enabling MCP caching

## Alternative: HTTP MCP Transport

Instead of SSH stdio, you can expose MCP over HTTP:

**On Canmore** - Start HTTP MCP server:
```bash
cd /Users/michel/dev/obsidian_rag
source venv/bin/activate

# Create HTTP MCP wrapper
python src/mcp/obsidian_rag_unified_mcp.py --http --port 5000
```

**On MacBook** - Configure MCP client for HTTP:
```json
{
  "mcpServers": {
    "obsidian-rag": {
      "url": "http://canmore.local:5000/mcp"
    }
  }
}
```

## Verification Checklist

- [ ] Diagnostic script runs without errors
- [ ] Python can list vault files
- [ ] Python can read vault files
- [ ] SSH connection works passwordless
- [ ] MCP tools respond in Claude
- [ ] Full note content is retrieved (not just snippets)
- [ ] PDF attachments can be read

## Support

If issues persist:
1. Run `./diagnose_mcp_access.sh` and share output
2. Check MCP logs: `~/Library/Logs/Claude/mcp*.log`
3. Check API Gateway logs: `docker logs obsidian-api-gateway`
