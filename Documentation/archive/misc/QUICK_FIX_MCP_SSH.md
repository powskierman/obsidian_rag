# Quick Fix: MCP SSH Access to iCloud Vault

## TL;DR

Your MacBook MCP client can access the vector index on Canmore but not the full note content because the vault is in iCloud Drive and files may not be downloaded locally or have permission issues.

## Quick Fix (Choose One)

### Option A: Download All iCloud Files (Easiest)

**On Canmore:**
```bash
cd /Users/michel/dev/obsidian_rag
./fix_mcp_permissions.sh
```

Select "Download all iCloud files" when prompted.

### Option B: Use Symlink (Recommended)

**On Canmore:**
```bash
# Create symlink
ln -s "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel" \
     /Users/michel/obsidian_vault

# Update .env
sed -i.bak 's|OBSIDIAN_VAULT_PATH=.*|OBSIDIAN_VAULT_PATH="/Users/michel/obsidian_vault"|' .env
```

### Option C: Force Download via brctl

**On Canmore:**
```bash
cd "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
find . -type f \( -name "*.md" -o -name "*.pdf" \) -exec brctl download {} \; 2>/dev/null
```

## Verify the Fix

**On Canmore:**
```bash
cd /Users/michel/dev/obsidian_rag
./diagnose_mcp_access.sh
```

All checks should pass ✅

## Test from MacBook

```bash
# SSH test
ssh michel@canmore 'cd /Users/michel/dev/obsidian_rag && ./diagnose_mcp_access.sh'

# MCP test (in Claude)
# Ask: "Search my vault for 'test'"
```

## Full Documentation

See `Documentation/SSH_MCP_SETUP.md` for complete details and troubleshooting.

## Still Having Issues?

1. **Permissions**: `chmod -R u+r "$OBSIDIAN_VAULT_PATH"`
2. **SSH Keys**: `ssh-copy-id michel@canmore`
3. **API Gateway**: Ensure Docker services are running on Canmore
4. **Network**: Check MacBook can reach `canmore.local:4000`

---

**Created**: 2026-03-25
**Last Updated**: 2026-03-25
