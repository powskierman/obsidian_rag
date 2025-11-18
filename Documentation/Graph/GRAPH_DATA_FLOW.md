# Knowledge Graph Data Flow & Storage

## Overview: Two Separate Systems

Your system has **two independent databases** that serve different purposes:

1. **ChromaDB** - Vector embeddings for semantic search
2. **Knowledge Graph** - Entity/relationship graph (NetworkX)

They are **NOT connected** - the graph is built FROM ChromaDB chunks, but stored separately.

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR OBSIDIAN VAULT                      │
│         (1,644 markdown files with your notes)              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ Indexed by
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    CHROMADB (Vector DB)                     │
│  Purpose: Semantic search (find similar text)               │
│  Storage: chroma_db/ directory                              │
│  Format: SQLite + binary index files                        │
│  Content: Text chunks with embeddings                       │
│                                                              │
│  Status: ⚠️ CORRUPTED (version mismatch)                    │
│  Fallback: Reading vault files directly                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ Used as SOURCE for
                        │ (reads chunks from here)
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              GRAPH BUILDER (Python Script)                  │
│  1. Reads chunks from ChromaDB OR vault files               │
│  2. Sends each chunk to Claude API                          │
│  3. Claude extracts entities & relationships                 │
│  4. Builds NetworkX graph in memory                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ Saves to
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              KNOWLEDGE GRAPH (NetworkX)                     │
│  Purpose: Entity/relationship queries                       │
│  Storage: graph_data/knowledge_graph_full.pkl              │
│  Format: Pickle file (Python NetworkX graph)                │
│  Content:                                                    │
│    - Nodes: 23,926 entities (Home Assistant, ESP32, etc.)  │
│    - Edges: 35,030 relationships (connects entities)        │
│                                                              │
│  Status: ✅ WORKING (independent of ChromaDB)               │
└─────────────────────────────────────────────────────────────┘
```

---

## Where Information is Stored

### 1. ChromaDB (Vector Database)
**Location**: `chroma_db/` directory
- `chroma.sqlite3` - SQLite database (metadata)
- `a58db7b8-.../` - Binary index files (vector embeddings)

**Purpose**: 
- Fast semantic search ("find notes about X")
- Used by embedding service for vector search
- **NOT used for graph queries**

**Status**: ⚠️ Corrupted (but not needed for graph building)

### 2. Knowledge Graph (Entity/Relationship Database)
**Location**: `graph_data/` directory
- `knowledge_graph_full.pkl` - **Main graph file** (NetworkX pickle)
- `knowledge_graph_full.json` - JSON export (for visualization)
- `graph_checkpoint_*.pkl` - Progress checkpoints

**Purpose**:
- Entity/relationship queries ("How does X relate to Y?")
- Used by graph query service
- **Independent of ChromaDB**

**Status**: ✅ Working

---

## Why It's Processing Every Chunk

### The Problem

1. **Original graph was built from ChromaDB chunks**
   - ChromaDB had ~7,113 pre-chunked pieces of text
   - Graph was built from those chunks
   - Chunk hashes were not saved

2. **Now using vault files**
   - Vault files are chunked on-the-fly (different boundaries)
   - Different chunk format = different hashes
   - Script can't match old chunks to new chunks

3. **No tracking of processed chunks**
   - Original graph builder didn't save which chunks were processed
   - Script sees all chunks as "new"

### Why This Happens

```
Original Build (from ChromaDB):
  File: "Medical/Lymphoma/4th PET Scan.md"
  → ChromaDB chunked it into 3 chunks:
    - Chunk 1: "First paragraph about scan..."
    - Chunk 2: "Second paragraph..."
    - Chunk 3: "Third paragraph..."

Current Retry (from vault files):
  Same file: "Medical/Lymphoma/4th PET Scan.md"
  → Vault loader chunks it differently:
    - Chunk 1: "First paragraph + part of second..."
    - Chunk 2: "Rest of second + third..."
  
Result: Different chunk boundaries = different hashes = all appear "new"
```

---

## What Gets Stored Where

### ChromaDB Stores:
- ✅ Text chunks (for semantic search)
- ✅ Embeddings (vector representations)
- ✅ Metadata (filename, dates, etc.)
- ❌ NOT entities/relationships
- ❌ NOT graph structure

### Knowledge Graph Stores:
- ✅ Entities (nodes): "Home Assistant", "ESP32", "CAR-T Therapy"
- ✅ Relationships (edges): "ESP32" → "uses" → "Arduino"
- ✅ Entity properties: types, descriptions, sources
- ✅ Relationship properties: strength, temporal info
- ❌ NOT the original text chunks
- ❌ NOT embeddings

---

## The Graph Building Process

### Step-by-Step:

1. **Load Chunks** (from ChromaDB or vault files)
   ```python
   chunks = [
       {'text': '...', 'metadata': {'filename': '...'}},
       {'text': '...', 'metadata': {'filename': '...'}},
       ...
   ]
   ```

2. **For Each Chunk:**
   - Send to Claude API: "Extract entities and relationships"
   - Claude returns JSON:
     ```json
     {
       "entities": [
         {"name": "Home Assistant", "type": "technology", ...},
         {"name": "ESP32", "type": "hardware", ...}
       ],
       "relationships": [
         {"source": "ESP32", "target": "Home Assistant", "type": "used_in", ...}
       ]
     }
     ```

3. **Add to Graph** (NetworkX in memory)
   - Entities → Nodes
   - Relationships → Edges
   - Merge duplicates automatically

4. **Save Graph** (to pickle file)
   ```python
   pickle.dump({
       'graph': networkx_graph,
       'stats': {...},
       'timestamp': '...'
   }, file)
   ```

---

## Why ChromaDB Corruption Doesn't Matter

### For Graph Building:
- ✅ Can read from vault files instead
- ✅ Graph is stored separately
- ✅ No dependency on ChromaDB

### For Vector Search:
- ⚠️ ChromaDB is needed for semantic search
- ⚠️ But you can rebuild it later
- ✅ Graph queries work independently

---

## Current Situation

**What's happening:**
- Script processes every chunk because it can't match old (ChromaDB) chunks to new (vault) chunks
- This is **normal and expected** when switching from ChromaDB to vault files

**What gets stored:**
- Graph data → `graph_data/knowledge_graph_full.pkl`
- Entities/relationships → Inside the NetworkX graph object
- **NOT in ChromaDB** - completely separate storage

**Why it's okay:**
- Graph builder merges duplicate entities automatically
- You won't get duplicate nodes, just more relationships
- Processing all chunks ensures you catch previously failed ones

---

## Summary

| Component | Purpose | Storage | Status |
|-----------|---------|---------|--------|
| **ChromaDB** | Vector search | `chroma_db/` | ⚠️ Corrupted (not needed for graph) |
| **Vault Files** | Source content | Obsidian vault | ✅ Working (used as fallback) |
| **Knowledge Graph** | Entity queries | `graph_data/*.pkl` | ✅ Working (independent) |

**Key Point**: ChromaDB is just a **source of chunks** for graph building. The graph itself is stored in `graph_data/` and is completely independent. ChromaDB corruption doesn't affect the graph!


