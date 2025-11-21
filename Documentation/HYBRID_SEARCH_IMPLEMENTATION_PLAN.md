# Hybrid Search Mode

**Status**: ✅ Implemented  
**Last Updated**: 2025-11-21

## Overview

Hybrid search combines **graph-based entity discovery** with **vector search** to provide the best of both worlds:
- Rich document content from vector search
- Relationship context from knowledge graph

## How It Works

1. **Query Graph** → Identifies relevant entities and relationships
2. **Extract Entities** → Pulls key terms from graph results
3. **Enhanced Vector Search** → Uses entities to improve document retrieval
4. **Combined Results** → Returns graph context + detailed document chunks

## Usage

1. Select **"Hybrid"** from search mode dropdown (default)
2. Ask your question
3. Get results with both graph relationships and document details

## Comparison

| Mode | Speed | Detail | Relationships |
|------|-------|--------|---------------|
| Vector | ⚡ Fast | ✅ Full | ❌ None |
| Graph | 🔄 Moderate | ⚠️ Summary | ✅ Excellent |
| **Hybrid** | 🔄 Moderate | ✅ Full | ✅ Excellent |

## Performance

- Query time: 2-5 seconds (makes 2 API calls)
- Fallback: Automatically uses vector-only if graph service unavailable
- Default mode: Hybrid (best overall results)

## Technical Details

- **File**: `streamlit_ui_docker.py`
- **Entity Extraction**: Regex-based with stopword filtering (top 10 entities)
- **Services**: Embedding (8000) + Graph (8002)

## Example

**Query**: "Tell me about my lymphoma journey"

**Hybrid Result**:
- Graph context showing CAR-T → Lymphoma → Treatment relationships
- Detailed PET scan results from notes
- Dr. Slaby's clinical observations
- Treatment timeline with dates

---

**See Also**: `Documentation/KET_RAG_ANALYSIS.md` for advanced graph-RAG analysis
