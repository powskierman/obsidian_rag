#!/bin/bash
# Save all Obsidian notes to vault
# Run this to create all 5 notes in your vault

VAULT_PATH="/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
RAG_PATH="$VAULT_PATH/Tech/AI/RAG"

echo "📝 Saving Obsidian RAG notes to vault..."
echo ""

# Create directory if needed
mkdir -p "$RAG_PATH"

# 1. MoC (Map of Content)
cat > "$RAG_PATH/Obsidian RAG System MoC.md" << 'EOFMOC'
---
date: 2025-10-20
tags: AI, RAG, obsidian, MoC, knowledge-management
status: active
---

# Obsidian RAG System - Map of Content

## Backlink
[[AI Projects]] | [[Knowledge Management]] | [[Local AI]]

## Main Idea
Complete map of the Obsidian RAG system - a production-ready, memory-enhanced, privacy-first AI assistant for querying my entire knowledge base with semantic understanding.

---

## 🎯 System Overview

**Purpose:** Transform my Obsidian vault into an AI-powered knowledge assistant that understands context, remembers conversations, and provides insights I might miss manually.

**Status:** ✅ Production Ready  
**Started:** October 2025  
**Last Updated:** October 20, 2025

---

## 📚 Core Documentation

### Main Documentation
- [[Building a Local Obsidian RAG System]] - Complete project history
- [[Obsidian RAG Quick Start]] - Fast implementation guide
- [[RAG Memory System]] - Mem0 integration details
- [[LightRAG Knowledge Graphs]] - Graph-based enhancement

### Implementation Location
- **Project:** `/Users/michel/ai/RAG/obsidian_rag`
- **Code:** See artifacts in Claude
- **README:** In project directory

---

## 🛠️ Components

### Core Services
1. **Embedding Service** - Vector database + semantic search
2. **Chat Interface** - Streamlit web UI
3. **Memory System** - Mem0 cross-session context
4. **File Watcher** - Auto-indexing on save
5. **MCP Server** - Claude Desktop integration

### Scripts
- start_obsidian_rag.sh - Start system
- stop_obsidian_rag.sh - Stop services
- check_status.sh - Status check
- start_with_watcher.sh - Start with auto-indexing
- backup.sh - Backup databases

---

## 📊 System Statistics

**Current Setup:**
- Total chunks: 6,861
- Estimated notes: ~1,560
- Database size: ~60MB
- Model: Qwen 2.5 Coder 32B
- Context window: 128K tokens
- RAM usage: ~22GB

**Performance:**
- Simple query: 15-20 seconds
- Medical analysis: 30-45 seconds
- Code generation: 20-35 seconds

---

## 💡 Use Cases

### Medical Knowledge
- Medical timeline queries
- Scan result analysis
- Side effect tracking
- Doctor visit preparation

### Technical Projects
- 3D printing reference
- Fusion 360 workflows
- Raspberry Pi projects
- Code snippet retrieval

### Cross-Domain
- Applying engineering to medicine
- Data analysis for health
- Project planning

---

## 🎯 Quick Start

```bash
cd /Users/michel/ai/RAG/obsidian_rag
./start_obsidian_rag.sh
open http://localhost:8501
```

---

## 🔗 Related

- [[AI Projects]]
- [[Obsidian Workflow]]
- [[Knowledge Management Systems]]
- [[Local AI Tools]]

---

## Tags
#AI #RAG #obsidian #MoC #knowledge-management #production
EOFMOC

echo "✅ Created: Obsidian RAG System MoC.md"

# 2. Quick Start Note
cat > "$RAG_PATH/Obsidian RAG Quick Start.md" << 'EOFQUICK'
---
date: 2025-10-20
tags: AI, RAG, quickstart, setup
status: active
---

# Obsidian RAG Quick Start

## Backlink
[[Obsidian RAG System MoC]] | [[AI Projects]]

## Reference
- Complete guide: [[Building a Local Obsidian RAG System]]
- Project: `/Users/michel/ai/RAG/obsidian_rag`
- Code: See Claude artifacts

## Main Idea
Fast-track guide to get the Obsidian RAG system running in 20 minutes.

---

## Quick Setup (20 minutes)

### 1. Install Dependencies (3 min)
```bash
cd /Users/michel/ai/RAG/obsidian_rag
source venv/bin/activate
pip install mem0ai watchdog sentence-transformers torch
```

### 2. Download Model (10 min)
```bash
ollama pull qwen2.5-coder:32b
```

### 3. Copy Files from Artifacts (5 min)
- embedding_service.py
- obsidian_rag_ui.py
- rag_with_memory.py
- watching_scanner.py
- simple_scanner.py
- obsidian_rag_mcp.py
- extract_scripts.sh

### 4. Create Scripts (1 min)
```bash
chmod +x extract_scripts.sh
./extract_scripts.sh
```

### 5. Initialize Memory (1 min)
```bash
python rag_with_memory.py init
```

### 6. Start System
```bash
./start_obsidian_rag.sh
```

### 7. Test
Open: http://localhost:8501
Try: "What do I know about lymphoma treatment?"

---

## Daily Usage

**Start:** `./start_obsidian_rag.sh`  
**Stop:** `./stop_obsidian_rag.sh`  
**Status:** `./check_status.sh`

---

## Related
- [[Obsidian RAG System MoC]]
- [[RAG Memory System]]

---

## Tags
#AI #RAG #quickstart #setup
EOFQUICK

echo "✅ Created: Obsidian RAG Quick Start.md"

# 3. Memory System Note
cat > "$RAG_PATH/RAG Memory System.md" << 'EOFMEMORY'
---
date: 2025-10-20
tags: AI, RAG, memory, Mem0
status: active
---

# RAG Memory System (Mem0)

## Backlink
[[Obsidian RAG System MoC]] | [[AI Projects]]

## Reference
- Implementation: `rag_with_memory.py`
- Database: `./mem0_db/`
- Docs: https://docs.mem0.ai/

## Main Idea
Cross-session memory system that remembers conversations, user context, and personal timeline using Mem0.

---

## What It Does

**Transforms RAG from stateless to stateful:**
- Remembers past conversations
- Tracks personal timeline (medical journey)
- Maintains user preferences
- Enables natural follow-up questions

---

## Pre-seeded Facts

System knows:
- High-grade B-cell DLBCL (double-hit)
- R-CHOP → Yescarta timeline
- 3-month scan (July 2025)
- 6-month scan (October 2025)
- Technical interests (3D printing, Raspberry Pi)
- Privacy preferences (local-only)

---

## Usage

### Initialize
```bash
python rag_with_memory.py init
```

### Query with Memory
```python
from rag_with_memory import MemoryRAG
rag = MemoryRAG()
result = rag.query("What should I expect at my scan?")
```

### View Memories
```python
memories = rag.get_all_memories()
```

### Interactive Mode
```bash
python rag_with_memory.py interactive
```

---

## Example

**First conversation:**
```
You: "Tell me about my treatment"
RAG: [Full context about DLBCL, R-CHOP, Yescarta]
```

**Later:**
```
You: "What about side effects?"
RAG: [Knows you mean Yescarta, no re-explanation]
```

---

## Related
- [[Obsidian RAG System MoC]]
- [[Obsidian RAG Quick Start]]

---

## Tags
#AI #RAG #memory #Mem0
EOFMEMORY

echo "✅ Created: RAG Memory System.md"

# 4. LightRAG Note
cat > "$RAG_PATH/LightRAG Knowledge Graphs.md" << 'EOFLIGHTRAG'
---
date: 2025-10-20
tags: AI, RAG, LightRAG, knowledge-graph, testing
status: experimental
---

# LightRAG Knowledge Graphs

## Backlink
[[Obsidian RAG System MoC]] | [[AI Projects]]

## Reference
- Test: `test_lightrag.py`
- Compare: `compare_rag_systems.py`
- Repo: https://github.com/HKUDS/LightRAG

## Main Idea
Knowledge graph-based RAG enhancement for relationship queries, timelines, and multi-hop reasoning.

---

## What LightRAG Adds

### Current RAG
- Vector similarity search
- Good for: "Find docs about X"

### LightRAG
- Knowledge graph traversal
- Good for: "How does X relate to Y?"
- Better for: Timelines, relationships, causal chains

---

## Use Cases

### Timeline Reconstruction
```
Query: "Trace treatment from diagnosis to now"
Output: Complete timeline graph with relationships
```

### Multi-Hop Reasoning
```
Query: "Why do I need IVIG therapy?"
Output: Yescarta → B-cell aplasia → low IgG → IVIG
```

### Entity-Centric
```
Query: "Everything about Yescarta"
Output: Complete entity graph with all connections
```

---

## Test Setup

```bash
pip install lightrag-hku nano-vectordb networkx
ollama pull nomic-embed-text
python test_lightrag.py
```

---

## Decision

**Add if:** Relationship queries frequent  
**Skip if:** Simple lookups sufficient  
**Test:** 2-3 hours to evaluate

---

## Related
- [[Obsidian RAG System MoC]]
- [[RAG Memory System]]

---

## Tags
#AI #RAG #LightRAG #knowledge-graph #experimental
EOFLIGHTRAG

echo "✅ Created: LightRAG Knowledge Graphs.md"

# 5. Update main project note
cat >> "$RAG_PATH/../Open Source/Building a Local Obsidian RAG System.md" << 'EOFUPDATE'

---

## 📝 Obsidian Notes Created

Complete note system created with MoC template:

### Map of Content
- **[[Obsidian RAG System MoC]]** - Central navigation hub
  - System overview
  - Component links
  - Statistics
  - Use cases
  - Quick reference

### Topic Notes
- **[[Obsidian RAG Quick Start]]** - 20-minute setup
- **[[RAG Memory System]]** - Mem0 integration guide
- **[[LightRAG Knowledge Graphs]]** - Optional enhancement

All notes use your standard template format:
- YAML frontmatter (date, tags, status)
- Backlinks section
- Reference section  
- Main idea
- Content sections
- Related notes
- Tags at bottom

**Status:** ✅ Notes saved to vault  
**Location:** `Tech/AI/RAG/`
EOFUPDATE

echo ""
echo "======================================================================"
echo "✅ All Obsidian notes saved successfully!"
echo "======================================================================"
echo ""
echo "Location: $RAG_PATH/"
echo ""
echo "Notes created:"
echo "  1. Obsidian RAG System MoC.md (Map of Content)"
echo "  2. Obsidian RAG Quick Start.md"
echo "  3. RAG Memory System.md"
echo "  4. LightRAG Knowledge Graphs.md"
echo "  5. Updated: Building a Local Obsidian RAG System.md"
echo ""
echo "Open Obsidian to see the new notes!"
echo "Start with: [[Obsidian RAG System MoC]]"
