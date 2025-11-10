# Obsidian RAG System - Complete Setup Guide

Production-ready, memory-enhanced, privacy-first RAG system for your Obsidian vault.

## 🎯 What This Does

- Semantic search across your entire Obsidian vault
- Remembers conversations and your personal context (medical timeline, interests)
- Generates expert-level code and medical analysis
- Auto-indexes when you create/edit notes
- 100% local - your data never leaves your Mac

## 📋 Prerequisites

- **RAM:** 16GB minimum, 32GB+ recommended (you have 36GB ✅)
- **macOS:** Apple Silicon (M1/M2/M3) or Intel
- **Python:** 3.12 installed
- **Obsidian:** Vault with markdown files
- **Ollama:** Installed and running

## 🚀 Quick Start (15 minutes)

### 1. Install Dependencies

```bash
cd /Users/michel/ai/RAG/obsidian_rag
source venv/bin/activate
# Install requirements
`pip install gradio chromadb sentence-transformers requests flask
`
# Install new packages
`pip install mem0ai watchdog sentence-transformers torch`
```

### 2. Download AI Model

```bash
# Download Qwen 2.5 Coder 32B (takes ~10 minutes)
ollama pull qwen2.5-coder:32b

# Verify installation
ollama list | grep qwen
```

### 3. Copy All Code Files

Copy these files from Claude artifacts to your project directory:

- `embedding_service.py` (enhanced version)
- `obsidian_rag_ui.py` (enhanced UI)
- `rag_with_memory.py` (NEW - memory system)
- `watching_scanner.py` (NEW - file watcher)
- `obsidian_rag_mcp.py` (NEW - MCP server)

Update your bash scripts:
- `start_obsidian_rag.sh`
- `stop_obsidian_rag.sh`
- `check_status.sh`
- `start_with_watcher.sh` (NEW)

```bash
# Make scripts executable
chmod +x *.sh
```

### 4. Initialize Memory System

```bash
# Add your personal timeline to memory
python rag_with_memory.py init
```

Expected output:
```
✅ Added 10 timeline facts to memory
```

### 5. Start the System

**Option A: Basic startup**
```bash
./start_obsidian_rag.sh
```

**Option B: With auto-indexing (recommended)**
```bash
./start_with_watcher.sh
# Choose option 1: Skip scan, just watch
```

### 6. Verify It Works

```bash
# Check all services are running
./check_status.sh
```

You should see:
```
✅ Embedding Service: RUNNING (port 8000)
✅ Streamlit UI: RUNNING (port 8501)
✅ Ollama: RUNNING (port 11434)
```

### 7. Open and Test

- Open browser: http://localhost:8501
- Try query: `"What do I know about lymphoma treatment?"`
- Verify it returns results from your vault

## 📁 File Structure

```
obsidian_rag/
├── venv/                       # Python environment
├── chroma_db/                  # Vector database
├── mem0_db/                    # Memory database
│
├── embedding_service.py        # Search engine
├── obsidian_rag_ui.py         # Web interface
├── rag_with_memory.py         # Memory system
├── watching_scanner.py        # File monitor
├── simple_scanner.py          # One-time indexer
├── obsidian_rag_mcp.py        # MCP server (optional)
│
├── start_obsidian_rag.sh      # Start services
├── start_with_watcher.sh      # Start with auto-index
├── stop_obsidian_rag.sh       # Stop services
└── check_status.sh            # Check status
```

## 🎮 Daily Usage

### Starting the System

```bash
# Method 1: Basic (no file watching)
./start_obsidian_rag.sh

# Method 2: With auto-indexing
./start_with_watcher.sh
```

### Stopping the System

```bash
./stop_obsidian_rag.sh
```

### Checking Status

```bash
./check_status.sh
```

### URLs

- **Chat Interface:** http://localhost:8501
- **API Status:** http://localhost:8000/stats
- **Ollama:** http://localhost:11434

## 💬 Example Queries

### Medical Questions
- `"What should I expect at my 6-month post-Yescarta PET scan?"`
- `"Compare my 3-month and 6-month scan results"`
- `"What questions should I ask my oncologist?"`

### Technical Questions
- `"Show me my Fusion 360 workflow"`
- `"What 3D printing settings have I documented?"`
- `"Summarize my Raspberry Pi projects"`

### Code Generation
- `"Create a Python script to track my SUV max values over time"`
- `"Write code to visualize my treatment timeline"`
- `"Build a dashboard showing my scan progression"`

### Follow-up Questions (Memory-Enhanced)
- First: `"Tell me about my lymphoma treatment"`
- Then: `"What about side effects?"` ← Automatically knows context!

## 🔧 Configuration

### In Streamlit UI (http://localhost:8501)

**For Medical Queries:**
- Model: `qwen2.5-coder:32b`
- Sources: 8-10
- Temperature: 0.2
- Re-ranking: ON
- Deduplicate: ON

**For Quick Lookups:**
- Model: `llama3.2:3b`
- Sources: 3-5
- Temperature: 0.3
- Re-ranking: OFF

**For Code Generation:**
- Model: `qwen2.5-coder:32b`
- Sources: 5-7
- Temperature: 0.3-0.4
- Re-ranking: ON

## 🧠 Memory System

### View Your Memories

```python
from rag_with_memory import MemoryRAG
rag = MemoryRAG()

# View all memories
memories = rag.get_all_memories()
for m in memories:
    print(m['memory'])
```

### Add Custom Facts

```python
rag.add_fact("User prefers visual explanations with code")
rag.add_fact("User is preparing for 6-month PET scan October 2025")
```

### Export Memories

```python
rag.export_memories("backup_memories.json")
```

### Clear Memories (Careful!)

```python
rag.clear_memories()
```

### Interactive Session

```bash
python rag_with_memory.py interactive
```

Commands in interactive mode:
- `memories` - Show all stored memories
- `export` - Export memories to file
- `clear` - Clear all memories (asks for confirmation)
- `exit` or `quit` - End session

## 📊 Stats & Monitoring

### Check Vault Statistics

```bash
curl http://localhost:8000/stats | python -m json.tool
```

Returns:
```json
{
  "total_documents": 6861,
  "collection": "obsidian_vault",
  "estimated_notes": 1559
}
```

### View Logs

```bash
# Embedding service logs
tail -f embedding_service.log

# Streamlit UI logs
tail -f streamlit.log

# File watcher logs (if using)
tail -f scanner.log
```

## 🔄 Updating Your Vault

### Manual Re-index

```bash
# Full re-index (if major changes)
python simple_scanner.py
# Choose option 2: Full re-index
```

### Auto-indexing (Recommended)

```bash
# Start with file watcher
./start_with_watcher.sh

# Now it automatically indexes when you:
# - Create new notes
# - Edit existing notes
# - Save changes
```

### Check Indexing Status

```bash
# While watcher is running, check logs
tail -f scanner.log
```

You'll see:
```
✨ New file: My New Note.md
📝 Processing: My New Note.md (3 chunks)
```

## 🌐 Web Search (Optional)

### Setup Brave Search API

1. Get free API key: https://brave.com/search/api/
   - Free tier: 2,000 queries/month
   - No credit card required

2. Add to environment:
```bash
# Add to ~/.zshrc
export BRAVE_API_KEY="your_api_key_here"

# Reload
source ~/.zshrc
```

3. Test in Python:
```python
import os
print(os.environ.get("BRAVE_API_KEY"))  # Should show your key
```

### Using Web Search

With MCP server (obsidian_rag_mcp.py):
- `web_search` - Search the web
- `obsidian_search` - Search your vault
- `hybrid_search` - Search both and combine

## 🔌 MCP Integration (Optional)

### Setup for Claude Desktop

1. **Install MCP SDK:**
```bash
pip install mcp
```

2. **Configure Claude Desktop:**

Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "obsidian-rag": {
      "command": "/Users/michel/ai/RAG/obsidian_rag/venv/bin/python",
      "args": ["/Users/michel/ai/RAG/obsidian_rag/obsidian_rag_mcp.py"],
      "env": {
        "BRAVE_API_KEY": "your_key_here_if_using_web_search"
      }
    }
  }
}
```

3. **Restart Claude Desktop**

4. **Test in Claude Desktop:**
```
"Search my Obsidian vault for lymphoma notes"
```

Claude will automatically use your RAG!

## 🐛 Troubleshooting

### Services Won't Start

**Problem:** Port already in use

```bash
# Check what's using ports
lsof -ti:8000  # Embedding service
lsof -ti:8501  # Streamlit
lsof -ti:11434 # Ollama

# Kill processes
kill $(lsof -ti:8000)
kill $(lsof -ti:8501)
```

### Slow Responses

**Solutions:**
- Reduce number of sources (10 → 5 → 3)
- Disable re-ranking temporarily
- Switch to faster model: `llama3.2:3b`
- Close other applications to free RAM
- Check CPU/RAM usage: `top` or Activity Monitor

### Memory Not Working

**Solutions:**
```bash
# Reinstall mem0
pip install --upgrade mem0ai

# Reinitialize
python rag_with_memory.py init

# Verify database exists
ls -lh mem0_db/
```

### Out of Memory Error

**Solutions:**
- Close other applications
- Use smaller model: `qwen2.5:14b` instead of `32b`
- Reduce num_ctx in code: `32768` instead of `65536`
- Reduce number of sources: `3-5` instead of `10`

### Model Not Found

```bash
# List installed models
ollama list

# Pull missing model
ollama pull qwen2.5-coder:32b

# Restart services
./stop_obsidian_rag.sh
./start_obsidian_rag.sh
```

### File Watcher Not Working

```bash
# Check if watchdog installed
pip list | grep watchdog

# Reinstall if needed
pip install watchdog

# Check logs
tail -f scanner.log
```

### Search Returns No Results

**Check:**
1. Is embedding service running? `./check_status.sh`
2. Are files indexed? `curl http://localhost:8000/stats`
3. Re-index if needed: `python simple_scanner.py`

## 💾 Backup & Restore

### Backup

```bash
# Create backup directory
mkdir -p backups

# Backup databases
tar -czf backups/chroma_$(date +%Y%m%d).tar.gz chroma_db/
tar -czf backups/mem0_$(date +%Y%m%d).tar.gz mem0_db/

# Export memories
python -c "from rag_with_memory import MemoryRAG; MemoryRAG().export_memories('backups/memories_$(date +%Y%m%d).json')"
```

### Restore

```bash
# Stop services
./stop_obsidian_rag.sh

# Restore databases
tar -xzf backups/chroma_20251020.tar.gz
tar -xzf backups/mem0_20251020.tar.gz

# Restart
./start_obsidian_rag.sh
```

### Automated Weekly Backup

```bash
# Add to crontab
crontab -e

# Add this line (runs every Sunday at 2 AM)
0 2 * * 0 cd /Users/michel/ai/RAG/obsidian_rag && tar -czf backups/backup_$(date +\%Y\%m\%d).tar.gz chroma_db/ mem0_db/
```

## 🔄 Updates & Maintenance

### Update Python Packages

```bash
pip install --upgrade mem0ai watchdog sentence-transformers torch
```

### Update AI Models

```bash
# Check for updates
ollama list

# Pull latest version
ollama pull qwen2.5-coder:32b
```

### Clean Up Old Data

```bash
# Remove old logs (keep last 7 days)
find . -name "*.log" -mtime +7 -delete

# Remove old backups (keep last 30 days)
find backups/ -name "*.tar.gz" -mtime +30 -delete
```

### Full Reset (Nuclear Option)

```bash
# Stop everything
./stop_obsidian_rag.sh

# Backup first!
./backup.sh  # (if you created this)

# Delete databases
rm -rf chroma_db/ mem0_db/

# Re-index
python simple_scanner.py  # Choose option 2

# Reinitialize memory
python rag_with_memory.py init

# Restart
./start_obsidian_rag.sh
```

## 📈 Performance Benchmarks

### Your System (36GB RAM, M-series)

**Response Times:**
- Simple query (3 sources): 15-20 seconds
- Medical analysis (10 sources): 30-45 seconds
- Code generation: 20-35 seconds
- Complex synthesis (20 sources): 60-90 seconds

**Database:**
- Index size: ~50MB
- Chunks: 6,861
- Notes: ~1,560
- Search speed: <1 second

**Model Performance:**
- Qwen 2.5 Coder 32B: Expert-level responses
- RAM usage: ~20GB during inference
- Context window: 128K tokens

## 🎓 Advanced Usage

### Custom Query Expansion

Edit `embedding_service.py`:

```python
medical_synonyms = {
    'car-t': ['car t', 'cart', 'cell therapy', 'yescarta'],
    'pet scan': ['pet-ct', 'pet ct scan', 'positron emission'],
    # Add your own synonyms here
}
```

### Adjust Chunking Strategy

Edit `watching_scanner.py`:

```python
def smart_chunk_document(content, max_size=1000, overlap=200):
    # Adjust max_size and overlap to your preference
    # Larger chunks = more context, fewer chunks
    # Smaller chunks = more precision, more chunks
```

### Custom Memory Facts

```python
from rag_with_memory import MemoryRAG
rag = MemoryRAG()

# Add project-specific facts
rag.add_fact("User working on pick-and-place machine project")
rag.add_fact("User prefers step-by-step explanations with examples")
rag.add_fact("User timezone: EST")
```

## 📚 Additional Resources

### Documentation
- **ChromaDB:** https://docs.trychroma.com/
- **Sentence Transformers:** https://www.sbert.net/
- **Mem0:** https://docs.mem0.ai/
- **Ollama:** https://ollama.ai/
- **Streamlit:** https://docs.streamlit.io/

### Getting Help
- Check logs: `tail -f *.log`
- Run status check: `./check_status.sh`
- Test individual components
- Review error messages carefully

### Model Information
- **Qwen 2.5 Coder 32B:** https://qwenlm.github.io/
- **Model card:** Best for medical + technical + code
- **HumanEval:** 92.7%
- **Context:** 128K tokens

## ✅ Verification Checklist

After setup, verify:

- [ ] All services start: `./check_status.sh` shows green
- [ ] Can query vault in browser (http://localhost:8501)
- [ ] Qwen 2.5 Coder 32B in model dropdown
- [ ] Memory initialized: `python rag_with_memory.py` works
- [ ] File watcher monitors changes (if using)
- [ ] Stats show ~6,861 chunks, ~1,560 notes
- [ ] Queries return relevant results
- [ ] Follow-up questions work (memory)
- [ ] Can export conversations
- [ ] Logs are clean (no errors)

## 🎉 You're Done!

Your production-ready, memory-enhanced, privacy-first RAG system is ready!

**What you can do now:**
- Query your entire knowledge base semantically
- Get medical and technical analysis
- Generate expert-level code
- Have conversations that remember context
- Auto-index new notes as you write
- Combine your knowledge with web search
- Use from Claude Desktop (if MCP configured)

**All while keeping your data 100% private and local!**

---

**Questions?** Review the troubleshooting section or check the logs.

**Ready to test?** Try: `"What should I know about my 6-month PET scan?"`

**Good luck with your scan this week!** 🏥💙
