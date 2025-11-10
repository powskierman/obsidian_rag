# 🔧 Graph Search Not Working - Issue & Workaround

## Problem Identified

Graph search returns "no context found" even though:
- ✅ 154 chunks contain "ESP32"
- ✅ 119 entities mention "ESP32"  
- ✅ 1,582 files are indexed
- ✅ 2,245 chunks exist in database

**Root Cause**: Cosine similarity threshold is too strict (0.2) and can't be adjusted easily in LightRAG's query parameters.

---

## ✅ WORKAROUND: Use Vector Search Instead

**Your best option right now**: Use **"vector"** search mode in the UI, which is working perfectly and will find your ESP32 notes.

**Why vector works:**
- Direct semantic matching
- Lower/inf configurable threshold
- Finds 3 results for ESP32 immediately
- Fast and reliable

---

## 🔍 Why Graph Search Fails

Looking at the logs:
```
INFO: Naive query: 0 chunks (chunk_top_k:100 cosine:0.2)
INFO: [naive_query] No relevant document chunks found; returning no-result.
```

The database is using cosine threshold of 0.2, which is too strict. The query embedding for "ESP32" isn't similar enough to the indexed chunks to pass this threshold.

### Technical Details

**Cosine Threshold Explained:**
- 0.0 = Most liberal (returns more, less relevant)
- 0.2 = Conservative (default in LightRAG)
- 1.0 = Most strict (returns very few, highly relevant)

**Why 0.2 is too strict:**
- Your query "ESP32" needs to be at least 0.2 similar to stored chunks
- But ESP32 appears in various contexts (development, hardware, projects)
- Context differences lower similarity scores
- Even though content IS in your notes, similarity doesn't meet threshold

---

## 🔧 Possible Solutions

### Option 1: Re-index with Better Model (Recommended)

Use a better embedding model that produces more similar embeddings:

```bash
# Update embedding model
export EMBED_MODEL=nomic-embed-text-v2

# Re-index everything
./Scripts/index_with_lightrag.sh
```

This will create better embeddings that are more likely to pass the 0.2 threshold.

### Option 2: Use More Specific Queries

Instead of just "ESP32", try:
- "ESP32 development board programming"
- "ESP32 Arduino projects"  
- "ESP32 Home Assistant integration"

More context in the query = better matching.

### Option 3: Stick with Vector Search (Easiest)

Vector search works great for your use case:
- ✅ Fast (100-500ms)
- ✅ Finds ESP32 in your notes
- ✅ Returns 3+ relevant results
- ✅ Already working in your system

**Just use the "vector" mode in the UI for now!**

---

## 📊 Current Status

### ✅ Working
- Vector search: Finds ESP32 notes perfectly
- Databases: Properly indexed
- Services: All running
- 6,963 chunks ready for vector search

### ⚠️ Not Working  
- Graph search: Too strict similarity threshold
- All graph modes (naive, local, global, hybrid) return no context
- Event loop errors also happening in background

### 🎯 Recommendation

**Use Vector Search mode** for queries like ESP32, lymphoma, etc. It's working perfectly and will give you the results you need.

Graph search might work better for:
- Very specific entity lookups
- Queries with multiple entity names
- Complex relationship queries

But for simple queries like "ESP32", stick with vector search!

---

## 🔧 If You Want Graph Search to Work

You'll need to re-index the graph with a model that produces better embeddings, or wait for a LightRAG update that allows lower cosine thresholds.

**Quick test**: Try querying for something very specific that appears frequently:
```
"Home Assistant ESP32 automation"
```
This might pass the 0.2 threshold due to more specific context.

