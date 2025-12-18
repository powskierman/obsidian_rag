# Slim Down Repository for GitHub Push

## Problem
Repository is 2.28 GiB (4.5GB .git directory), causing GitHub 500 errors on push.

## Solution Options

### Option 1: Fresh Start (Recommended for New Repos)
Since this appears to be a relatively new repository, the cleanest approach is:

1. **Create a fresh repository:**
```bash
# Backup current work
cp -r . ../obsidian_rag_backup

# Remove .git and start fresh
rm -rf .git

# Initialize new repo
git init
git add .
git commit -m "Initial commit - cleaned repository"

# Add remote
git remote add origin https://github.com/powskierman/obsidian_rag.git

# Force push (this will overwrite remote)
git push -u origin main --force
```

### Option 2: Continue Git Filter-Branch (If you need history)
If you need to preserve commit history:

1. **Complete the cleanup:**
```bash
# Set environment variable to suppress warning
export FILTER_BRANCH_SQUELCH_WARNING=1

# Run cleanup (takes 10-30 minutes)
./cleanup_git_history.sh

# After completion, force push
git push origin main --force
```

### Option 3: Use BFG Repo-Cleaner (Fastest)
BFG is faster than git filter-branch:

```bash
# Install BFG (requires Java)
brew install bfg

# Remove large files
bfg --delete-files "*.pkl" --delete-files "*.json" --no-blob-protection

# Clean up
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push
git push origin main --force
```

## Files Already Excluded in .gitignore
- `graph_data/**/*.pkl`
- `graph_data/**/*.json`
- `chroma_db_backup_*/`
- `lightrag_db_backup_*/`
- `graphrag_claude_db/`
- `graphrag_db/`
- `Archive/old_databases/`

## Recommendation
**Use Option 1 (Fresh Start)** if:
- You don't need the full commit history
- The repository is relatively new
- You want the fastest solution

**Use Option 3 (BFG)** if:
- You need to preserve history
- You want the fastest cleanup method

**Use Option 2 (Filter-Branch)** if:
- BFG is not available
- You prefer built-in git tools

