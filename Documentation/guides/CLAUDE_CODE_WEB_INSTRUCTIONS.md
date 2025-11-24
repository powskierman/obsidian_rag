# GraphRAG Indexing with Claude Code Web - Step-by-Step Instructions

## Overview
Use your $250 Claude Code web credits to run GraphRAG indexing in a cloud VM with local models (no API costs).

## Prerequisites
- GitHub repository with this project
- Access to Claude Code web interface
- Your Obsidian vault files accessible

---

## Phase 1: Repository Setup (Do This First)

### Step 1: Commit Current Work
```bash
# In your local terminal:
cd "/Users/michel/iCloud Drive/ai/RAG/obsidian_rag"
git add .
git commit -m "GraphRAG 2.7.0 setup ready for Claude Code web execution"
git push origin main
```

### Step 2: Create Instruction File for Claude
The file `CLAUDE_CODE_WEB_SETUP.md` below contains everything Claude Code web needs to know.

---

## Phase 2: Claude Code Web Execution

### Step 1: Start Claude Code Web Session
1. Go to Claude Code web interface
2. Connect to your GitHub repository: `obsidian_rag`
3. Wait for repository to be cloned to the VM

### Step 2: Give Claude This Exact Prompt
```
I need you to set up and run GraphRAG 2.7.0 indexing using local models in this VM. Please follow the instructions in CLAUDE_CODE_WEB_SETUP.md exactly. The goal is to index my Obsidian vault files into a knowledge graph using only local models (no API costs). Make sure to use the latest GraphRAG 2.7.0 with LiteLLM for local model support.
```

### Step 3: Claude Will Execute Automatically
Claude Code web will:
- Read the setup instructions
- Install Ollama and models
- Configure GraphRAG 2.7.0
- Process your vault files
- Generate the complete knowledge graph
- Report results

---

## Expected Results
- ✅ Complete GraphRAG knowledge graph index
- ✅ Entity extraction from all vault files
- ✅ Relationship detection and mapping
- ✅ Community detection and clustering
- ✅ Queryable knowledge base
- ✅ Zero API costs (only VM time from your $250 credits)

---

## Files Claude Code Web Will Create
- `output/[timestamp]/artifacts/` - GraphRAG knowledge graph files
- `cache/` - Processing cache
- `logs/` - Execution logs
- `test_queries.py` - Script to test the generated index

---

## Troubleshooting
If Claude Code web encounters issues:
1. Check the error logs it provides
2. Ask it to try alternative model configurations
3. Request it to use smaller models if memory issues occur
4. Have it verify Ollama installation and model downloads

---

## Cost Estimate
- **VM Time**: ~1-3 hours for 1,607 files
- **Model Downloads**: ~5-10 GB (llama3.1:8b + nomic-embed-text)
- **Processing**: Depends on file complexity
- **Total**: Should use a small portion of your $250 credits

---

## Next Steps After Completion
Once Claude Code web finishes:
1. Download the generated knowledge graph files
2. Test queries against the index
3. Integrate with your local setup if desired
4. Create a pull request with the results