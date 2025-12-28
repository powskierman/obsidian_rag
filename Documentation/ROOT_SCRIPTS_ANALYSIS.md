# Root Directory Scripts Analysis

**Analysis Date**: December 28, 2025
**Files Reviewed**: 8 shell scripts, 4 Python files
**Status**: 🔍 Detailed Review Complete

---

## Executive Summary

The root directory contains **8 shell scripts** and **4 Python files** that were used during early development. Most are now **obsolete** or **superseded** by:
- Docker-based deployment (preferred method)
- Scripts moved to `Scripts/` directory
- Services moved to `src/` directory

**Recommendation**: Move to `Archive/` or delete most root scripts.

---

## Shell Scripts Analysis

### 1. run.sh (2.3K, Nov 21) ⚠️ **OBSOLETE**

**Purpose**: Start embedding service and Streamlit UI locally (no Docker)

**What it does**:
- Loads `.env.local`
- Checks Ollama connectivity
- Starts `embedding_service.py` in background
- Runs `streamlit run streamlit_ui_enhanced.py`

**Issues**:
1. References `embedding_service.py` in root (doesn't exist)
2. References `streamlit_ui_enhanced.py` in root (doesn't exist)
3. Files moved to `src/services/` and `src/ui/`
4. Uses `.env.local` (project uses `.env` now)

**Superseded by**:
- `Scripts/start_obsidian_rag.sh` - Updated version
- Docker Compose setup (preferred)

**Recommendation**: ❌ **DELETE** or move to Archive
- This script is broken (references non-existent files)
- Docker is now the standard deployment method
- If local run needed, use `Scripts/start_obsidian_rag.sh`

---

### 2. setup.sh (5.2K, Nov 21) ⚠️ **PARTIALLY OBSOLETE**

**Purpose**: Initial setup script for new users

**What it does**:
- Checks Python/pip installation
- Creates `.env.local` with template
- Installs Python dependencies
- Checks Docker/Ollama availability
- Provides next steps

**Issues**:
1. Creates `.env.local` (project uses `.env`)
2. References old model: `qwen2.5-coder:14b`
3. Points to old scripts: `./run.sh`, `./Scripts/docker_start.sh`
4. References non-existent files: `QUICKSTART.md`, `Documentation/TROUBLESHOOTING.md`

**Current Setup Process**:
1. User pulls repo
2. Runs `docker-compose up` (simplest)
3. OR uses `Launch Obsidian RAG.command` (macOS app launcher)

**Value**:
- Still useful as a general setup guide
- Could be updated to reflect current deployment

**Recommendation**: ⚠️ **UPDATE OR ARCHIVE**
- If keeping: Update to use `.env`, current models, correct file references
- Otherwise: Move to `Archive/` and create simpler `SETUP.md` doc

---

### 3. save_notes.sh (9.2K, Nov 21) ⚠️ **OBSOLETE**

**Purpose**: Save Obsidian notes about the RAG system to user's vault

**What it does**:
- Creates 5 notes in `$VAULT_PATH/Tech/AI/RAG/`
- Hardcoded path: `/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel`
- Generates MoC, Quick Start, Memory System, LightRAG, and Building notes

**Issues**:
1. Hardcoded path specific to one user (Michel)
2. Creates documentation IN the vault (mixing docs with knowledge)
3. Statistics are outdated (Oct 2025, references old models)
4. One-time use script (already executed)

**Value**:
- Historical documentation of system development
- Could be useful template for users to create their own docs

**Recommendation**: ❌ **MOVE TO ARCHIVE**
- Not needed for ongoing operations
- One-time documentation generation
- Outdated statistics and model references
- Move to `Scripts/archive/save_notes.sh`

---

### 4. run_claude_index.sh (380B, Nov 21) ⚠️ **BROKEN**

**Purpose**: Run Claude-based indexing

**What it does**:
- Activates venv
- Checks for `ANTHROPIC_API_KEY`
- Runs `python3 index_with_claude_direct.py`

**Issues**:
1. References `index_with_claude_direct.py` in root (doesn't exist in root)
2. File exists in `Scripts/archive/index_with_claude_direct.py`
3. Uses venv activation (Docker deployment doesn't need this)
4. Claude indexing likely replaced by Kimi-based graph building

**Current Approach**:
- Graph indexing done with Kimi K2: `src/services/kimi_graph_builder.py`
- Run via Docker services, not direct scripts

**Recommendation**: ❌ **DELETE**
- Broken reference (file not in root)
- Functionality replaced by Kimi graph builder
- Docker handles service orchestration now

---

## Python Files Analysis

### 5. obsidian_rag_mcp_fixed.py (8.3K, Nov 21) ⚠️ **SUPERSEDED**

**Purpose**: MCP server for Claude Desktop integration

**What it does**:
- Exposes `obsidian_simple_search` and `obsidian_deep_query` tools
- Hardcoded path: `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag`
- Connects to embedding service (localhost:8000) and LightRAG (localhost:8001)

**Issues**:
1. Hardcoded absolute path
2. Superseded by files in `src/mcp/`
3. "Fixed" version implies there's an unfixed version somewhere

**Current MCP Setup**:
Check `src/mcp/` directory for current MCP server implementation

**Recommendation**: ⚠️ **VERIFY THEN DELETE**
1. Check if `src/mcp/` has updated MCP server
2. If yes, delete this root file
3. If this is still the active version, move to `src/mcp/`

---

### 6. obsidian_rag_unified_mcp.py (8.3K, Nov 22) ⚠️ **DUPLICATE**

**Purpose**: Another MCP server variant ("unified")

**Issues**:
1. Almost identical to `obsidian_rag_mcp_fixed.py`
2. **Already in .gitignore** (line 70)
3. Created day after "fixed" version (incremental improvement?)
4. Duplicate functionality

**Recommendation**: ❌ **DELETE**
- Already marked for ignore in .gitignore
- Duplicate of obsidian_rag_mcp_fixed.py
- Superseded by src/mcp/ implementation

---

### 7. openrouter_client.py (372B, Dec 23) ✅ **UTILITY**

**Purpose**: Simple OpenRouter API client wrapper

**What it does**:
```python
def kimi_chat(messages, model="moonshotai/kimi-k2-0905"):
    # Wraps OpenAI client for OpenRouter
```

**Used by**:
- `src/services/kimi_graph_builder.py` uses similar pattern
- Could be imported as utility

**Issues**:
- Very minimal (16 lines)
- Could be moved to `src/utils/`

**Recommendation**: ⚠️ **MOVE TO src/utils/**
- Small utility function
- Could be useful for other OpenRouter integrations
- Better organized in `src/utils/openrouter_client.py`

---

### 8. test_openrouter.py (955B, Dec 23) ✅ **TEST UTILITY**

**Purpose**: Test OpenRouter connectivity

**What it does**:
- Tests connection to OpenRouter API
- Uses Kimi K2 model
- Simple connectivity check

**Value**:
- Useful for debugging
- Quick API key verification
- Small, focused test

**Recommendation**: ⚠️ **MOVE TO tests/**
- This is a test file
- Belongs in `tests/integration/test_openrouter.py`
- Or keep in root as `test_openrouter.py` (acceptable for quick tests)

**Alternative**: Could also move to `Scripts/test_openrouter.py` with other utilities

---

## File Status Summary

| File | Size | Date | Status | Recommendation |
|------|------|------|--------|----------------|
| run.sh | 2.3K | Nov 21 | ⚠️ Broken | ❌ DELETE |
| setup.sh | 5.2K | Nov 21 | ⚠️ Outdated | ⚠️ UPDATE or ARCHIVE |
| save_notes.sh | 9.2K | Nov 21 | ⚠️ One-time | ❌ ARCHIVE |
| run_claude_index.sh | 380B | Nov 21 | ❌ Broken | ❌ DELETE |
| obsidian_rag_mcp_fixed.py | 8.3K | Nov 21 | ⚠️ Superseded | ⚠️ VERIFY & DELETE |
| obsidian_rag_unified_mcp.py | 8.3K | Nov 22 | ❌ Duplicate | ❌ DELETE |
| openrouter_client.py | 372B | Dec 23 | ✅ Utility | ⚠️ MOVE to src/utils |
| test_openrouter.py | 955B | Dec 23 | ✅ Test | ⚠️ MOVE to tests/ |

---

## Recommended Actions

### Phase 1: Safe Deletions (No Dependencies)

```bash
cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"

# Delete broken/obsolete scripts
rm -f run.sh
rm -f run_claude_index.sh
rm -f obsidian_rag_unified_mcp.py  # Already in .gitignore

echo "✅ Deleted 3 obsolete files"
```

**Space saved**: ~11 KB

### Phase 2: Archive Historical Scripts

```bash
# Create archive if needed
mkdir -p Archive/

# Move historical documentation generator
mv save_notes.sh Archive/

echo "✅ Archived 1 file"
```

### Phase 3: Reorganize Useful Files

```bash
# Move utility to proper location
mkdir -p src/utils/
mv openrouter_client.py src/utils/

# Move test to proper location
mkdir -p tests/integration/
mv test_openrouter.py tests/integration/

echo "✅ Reorganized 2 files"
```

### Phase 4: Verify & Clean MCP Files

```bash
# Check if src/mcp/ has MCP server
ls -la src/mcp/

# If yes, delete root MCP files
rm -f obsidian_rag_mcp_fixed.py

echo "✅ Cleaned MCP files"
```

### Phase 5: Update or Archive setup.sh

**Option A**: Update setup.sh to reflect current Docker-based setup
**Option B**: Move to Archive and create simple SETUP.md

```bash
# Option B (simpler)
mv setup.sh Archive/

# Create simple setup doc
cat > SETUP.md << 'EOF'
# Obsidian RAG - Quick Setup

## Prerequisites
- Docker & Docker Compose
- Obsidian vault
- API keys (Anthropic, OpenRouter, etc.)

## Setup Steps

1. Clone repository
2. Copy `.env.example` to `.env`
3. Edit `.env` and add your API keys
4. Run: `docker-compose up`

That's it! Access at http://localhost:3000 (Next.js) or http://localhost:8501 (Streamlit)

For more details, see Documentation/
EOF

echo "✅ Created SETUP.md"
```

---

## Current vs. Old Architecture

### Old Architecture (Nov 2025)
```
Root directory:
├── run.sh                    # Manual service start
├── setup.sh                  # Manual setup
├── embedding_service.py      # In root
├── streamlit_ui_enhanced.py  # In root
└── .env.local                # Environment

Deployment: Manual Python processes
```

### Current Architecture (Dec 2025)
```
Organized structure:
├── src/
│   ├── services/
│   │   ├── embedding_service.py      # Moved here
│   │   ├── graph_query_service.py
│   │   └── kimi_graph_builder.py
│   ├── ui/
│   │   ├── streamlit_ui_docker.py    # Moved here
│   │   └── streamlit_ui_enhanced.py
│   └── mcp/                          # MCP servers
├── webapp/                            # Next.js app
├── Scripts/                           # Utility scripts
├── config/docker/                     # Docker configs
└── .env                              # Environment

Deployment: Docker Compose (preferred) or macOS app launcher
```

---

## Broken References

### Files Referenced But Don't Exist in Root

1. **run.sh** references:
   - `embedding_service.py` (moved to `src/services/`)
   - `streamlit_ui_enhanced.py` (moved to `src/ui/`)
   - `.env.local` (project uses `.env`)

2. **run_claude_index.sh** references:
   - `index_with_claude_direct.py` (in `Scripts/archive/`)

3. **setup.sh** references:
   - `QUICKSTART.md` (doesn't exist)
   - `Documentation/TROUBLESHOOTING.md` (doesn't exist)
   - `./Scripts/docker_start.sh` (check if exists)

---

## What Should Be in Root?

### Keep in Root
1. **Configuration**:
   - `.env` (environment variables)
   - `.gitignore` (git configuration)
   - `.dockerignore` (docker configuration)
   - `docker-compose.yml` (or symlink to config/)

2. **Documentation**:
   - `README.md` (project overview)
   - `SETUP.md` (quick setup guide)

3. **Entry Points**:
   - `Launch Obsidian RAG.command` (macOS launcher)

4. **Python Metadata**:
   - `requirements.txt` (Python dependencies)
   - `pytest.ini` (test configuration)

### Move Out of Root
1. **Scripts** → `Scripts/`
2. **Services** → `src/services/`
3. **Tests** → `tests/`
4. **Utilities** → `src/utils/`
5. **MCP Servers** → `src/mcp/`

---

## Cleanup Script

Complete cleanup script for all recommendations:

```bash
#!/bin/bash
# cleanup_root_scripts.sh - Clean up root directory scripts

set -e

cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"

echo "🧹 Root Scripts Cleanup"
echo "======================"
echo ""

# Create directories if needed
mkdir -p Archive/
mkdir -p src/utils/
mkdir -p tests/integration/

# Phase 1: Delete obsolete files
echo "Phase 1: Deleting obsolete files..."
rm -f run.sh
rm -f run_claude_index.sh
rm -f obsidian_rag_unified_mcp.py
echo "   ✅ Deleted 3 obsolete files"

# Phase 2: Archive historical files
echo "Phase 2: Archiving historical files..."
mv save_notes.sh Archive/ 2>/dev/null || echo "   (save_notes.sh already moved)"
mv setup.sh Archive/ 2>/dev/null || echo "   (setup.sh already moved)"
echo "   ✅ Archived historical files"

# Phase 3: Reorganize utilities
echo "Phase 3: Reorganizing utilities..."
mv openrouter_client.py src/utils/ 2>/dev/null || echo "   (openrouter_client.py already moved)"
mv test_openrouter.py tests/integration/ 2>/dev/null || echo "   (test_openrouter.py already moved)"
echo "   ✅ Reorganized utilities"

# Phase 4: Check MCP files
echo "Phase 4: Checking MCP files..."
if [ -d "src/mcp" ] && [ -n "$(ls -A src/mcp 2>/dev/null)" ]; then
    echo "   Found MCP files in src/mcp/"
    read -p "   Delete root MCP file (obsidian_rag_mcp_fixed.py)? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -f obsidian_rag_mcp_fixed.py
        echo "   ✅ Deleted root MCP file"
    fi
else
    echo "   ⚠️  No src/mcp/ directory - keeping root MCP file for now"
fi

echo ""
echo "✅ Cleanup complete!"
echo ""
echo "Summary:"
echo "  - Deleted: run.sh, run_claude_index.sh, obsidian_rag_unified_mcp.py"
echo "  - Archived: save_notes.sh, setup.sh"
echo "  - Moved: openrouter_client.py → src/utils/"
echo "  - Moved: test_openrouter.py → tests/integration/"
echo ""
```

---

## Verification After Cleanup

After running cleanup, verify:

```bash
# Check root is clean
ls -la *.sh *.py 2>/dev/null

# Should only see:
# - Launch Obsidian RAG.command (macOS launcher)
# - search_vault (if exists)
# - obsidian_rag_mcp_fixed.py (if src/mcp/ doesn't exist)

# Verify moves worked
ls -la src/utils/openrouter_client.py
ls -la tests/integration/test_openrouter.py
ls -la Archive/save_notes.sh
ls -la Archive/setup.sh
```

---

## Conclusion

**Current State**: Root directory has 8 obsolete/misplaced scripts

**After Cleanup**:
- ✅ 3 obsolete files deleted
- ✅ 2 historical files archived
- ✅ 2 utilities moved to proper locations
- ✅ 1 MCP file verified/cleaned
- ✅ Clean, organized root directory

**Benefits**:
- Clearer project structure
- Less confusion about which files to use
- Easier onboarding for new contributors
- Better separation of concerns

**Space Saved**: ~21 KB (minimal, but structure matters more than size)

**Next Step**: Run the cleanup script or manually execute the recommended actions.
