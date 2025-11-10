# 🚀 Quick Start Guide - Filesystem Edition

This version accesses your ChromaDB and vault directly from the filesystem - no HTTP services needed!

## ✅ What Changed

**Before:** Required embedding service to be running (HTTP requests)  
**Now:** Reads ChromaDB and vault files directly from disk

---

## 📋 Prerequisites

1. **API Key**: Anthropic API key
2. **Paths**: Know your paths to:
   - ChromaDB: `/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/chroma_db`
   - Vault: `/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel`

---

## 🏃 Quick Start (5 Minutes)

### Step 1: Install Dependencies

```bash
cd /Users/michel/Library/Mobile\ Documents/com\~apple\~CloudDocs/ai/RAG/obsidian_rag

# Activate venv
source venv/bin/activate

# Install requirements
pip install anthropic networkx tqdm chromadb
```

### Step 2: Set API Key

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

### Step 3: Run Test Mode

```bash
python build_knowledge_graph.py
```

**What it asks:**

1. **ChromaDB path** - Press Enter for default or paste your path
2. **Vault path** - Press Enter for default or paste your path  
3. **Choose option** - Type `1` for test mode (50 chunks)

**Test Mode Output:**
```
✅ Loaded 7113 chunks from ChromaDB
Test mode: limiting to 50 chunks
Processing chunk 1/50...
...
Graph built: 120 nodes, 250 edges
✅ Graph saved to: knowledge_graph_test.pkl
```

### Step 4: Query the Graph

```bash
python build_knowledge_graph.py
```

Choose option `4` for interactive mode:

```
🔍 Your query: What treatments are mentioned?
💡 Answer: Based on the knowledge graph, several treatments are mentioned...
```

---

## 🎯 Options Explained

When you run `python build_knowledge_graph.py`:

### Option 1: Test Mode (Recommended First)
- Processes: 50 chunks
- Time: 2-3 minutes
- Cost: ~$0.50
- Output: `knowledge_graph_test.pkl`
- Purpose: Validate the approach

### Option 2: Full Mode
- Processes: ALL chunks (~7,113)
- Time: 3-4 hours
- Cost: ~$25-30
- Output: `knowledge_graph_full.pkl`
- Purpose: Production graph

### Option 3: Test Queries
- Load existing graph
- Run predefined test queries
- See example outputs

### Option 4: Interactive Mode
- Load existing graph
- Ask questions interactively
- Explore entities and relationships

---

## 📂 How It Works

### Data Loading

```
1. Check ChromaDB first:
   ├─ Load chroma_db from disk
   ├─ Read all documents + metadata
   └─ Return as chunks

2. Fallback to Vault (if ChromaDB fails):
   ├─ Find all .md files
   ├─ Read content
   ├─ Split into chunks
   └─ Return as chunks
```

### Graph Building

```
For each chunk:
├─ Send to Claude API
├─ Extract entities + relationships
├─ Add to NetworkX graph
└─ Save checkpoint every 10 chunks
```

---

## 💡 Example Queries

### Medical
```
"What treatments are mentioned in my notes?"
"How are PET scans related to treatment decisions?"
"What's the timeline of my lymphoma treatment?"
```

### Technical
```
"What 3D printing projects have I documented?"
"How does Fusion 360 relate to my designs?"
"What technologies appear in my tech notes?"
```

### Cross-Domain
```
"How do my technical skills relate to medical device concepts?"
"What patterns exist across medical and technical notes?"
```

---

## 🔍 Path Detection

The script auto-detects your paths:

**Default ChromaDB:**
```
/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/chroma_db
```

**Default Vault:**
```
/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel
```

You can:
- Press Enter to use defaults
- Type custom paths if different
- Script validates paths exist

---

## 🐛 Troubleshooting

### "Neither path exists"

**Problem:** Paths not found  
**Solution:** 
```bash
# Find your ChromaDB
find ~ -name "chroma_db" -type d 2>/dev/null

# Find your vault
find ~ -name "Michel" -type d 2>/dev/null | grep -i obsidian
```

### "No chunks found"

**Problem:** ChromaDB empty or wrong path  
**Solution:** 
- Check path is correct
- Try vault path instead
- Verify ChromaDB has data: `ls -la /path/to/chroma_db`

### "Import error: chromadb"

**Problem:** ChromaDB not installed  
**Solution:**
```bash
pip install chromadb
```

---

## 📊 What to Expect

### Test Mode (50 chunks)
```
Processing: 2-3 minutes
Entities: ~100-150
Relationships: ~200-300
Graph file: knowledge_graph_test.pkl (10-50 KB)
JSON export: knowledge_graph_test.json (20-100 KB)
```

### Full Mode (7,113 chunks)
```
Processing: 3-4 hours
Entities: ~3,000-5,000
Relationships: ~10,000-15,000
Graph file: knowledge_graph_full.pkl (5-10 MB)
JSON export: knowledge_graph_full.json (10-20 MB)
```

---

## 🎨 Interactive Mode Commands

```bash
# Regular question
> What treatments are mentioned?

# View statistics
> stats

# Explore entity
> entity CAR-T Therapy

# Find connection
> path CAR-T to Lymphoma

# Exit
> quit
```

---

## 💰 Cost Summary

| Action | Time | Cost |
|--------|------|------|
| Test (50 chunks) | 3 min | $0.50 |
| Full (7,113 chunks) | 4 hrs | $25-30 |
| Query (simple) | 5 sec | $0.02 |
| Query (complex) | 10 sec | $0.05 |

**Monthly (50 queries/day):** ~$3-5

---

## ✅ Success Checklist

After test mode, you should have:

- ✅ `knowledge_graph_test.pkl` file created
- ✅ `knowledge_graph_test.json` file created  
- ✅ Graph statistics printed
- ✅ Top 10 entities listed
- ✅ Interactive queries work

---

## 🚀 Next Steps

1. ✅ Run test mode (option 1)
2. ✅ Try interactive queries (option 4)
3. ✅ Review entity quality
4. ✅ Test with your actual questions
5. ✅ If satisfied, run full mode (option 2)

---

## 📝 Files Created

After running:

```
knowledge_graph_test.pkl      # Pickled NetworkX graph
knowledge_graph_test.json     # JSON export for visualization
```

These files contain:
- All entities extracted
- All relationships discovered
- Source tracking (which notes)
- Entity properties and types

---

**You're ready to start!** 🎉

Run `python build_knowledge_graph.py` and choose option 1 to begin.
