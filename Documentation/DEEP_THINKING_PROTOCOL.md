
# Deep Thinking & Search Protocol

## Overview
This document defines the protocols for the **Reasoning Engine (Track 2)** and **Search Implementations**.

## 1. Gateway Response Schema
The API Gateway (`/api/v1/query`) returns different JSON structures based on `mode`. Clients and Agents MUST handle these variations.

### Vector Mode (`mode="vector"`)
Wrapper around ChromaDB response.
```json
{
  "query": "user query",
  "mode": "vector",
  "results": {
      "documents": [["doc1...", "doc2..."]],
      "metadatas": [[{"filename": "foo.md"}, ...]],
      "distances": [[0.4, 0.5]]
  },
  "metadata": {"source": "ChromaDB Vectors"}
}
```
*Note: Has no top-level `answer` key.*

### Graph/Hybrid Modes (`mode="hybrid" | "notes" | "cascading"`)
Returns synthesized answer and flattened sources.
```json
{
  "query": "user query",
  "mode": "hybrid",
  "answer": "Synthesized text...",
  "sources": [
      {"filename": "foo.md", "snippet": "...", "relevance": 85.0}
  ],
  "extracted_entities": ["Entity1", "Entity2"]
}
```

## 2. Deep Thinking (WebSocket)
Endpoint: `ws://localhost:4000/api/v1/deep-research`

### Protocol
1. **Send**: `{"query": "...", "mode": "deep-thinking", "parameters": {"max_depth": 1}}`
2. **Receive (Stream)**:
   - `{"type": "status", "message": "Planning..."}`
   - `{"type": "thought", "content": "Planner decided to..."}`
   - `{"type": "answer", "content": "Final answer..."}`
   - `{"status": "complete"}`

## 3. Audit Procedures
Run `python Scripts/debug/audit_search_modes.py` to verify all modes.
- **Pass Criteria**: `status=PASS` AND `source_count > 0` (for non-chat modes).
- **Latency Targets**: 
    - Vector: < 1s
    - Graph: < 5s
    - Hybrid: < 8s
    - Deep Thinking: < 120s
