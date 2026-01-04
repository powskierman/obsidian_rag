---
aliases: 
created: 2026-01-04 12:45
tags: #rag #vector #chromadb
Backlink: "[[System Overview]]"
---
### Main Idea
- The foundational semantic search layer using ChromaDB and high-dimensional embeddings for similarity matching.

### References
- [[SYSTEM_OVERVIEW_2025.md]]
- Port 8000; Container: `obsidian-embedding`

### Notes
- **Tech Stack**:
    - **Database**: ChromaDB (local persistence).
    - **Embeddings**: `nomic-embed-text` (768-dim, via Ollama).
- **Key Features**:
    - **Reranking**: Improves output quality by scoring results with cross-encoders.
    - **HyDE**: Uses "Hypothetical Document Embeddings" to bridge the gap between query and source text.
    - **Folder Filtering**: Restricts search to specific Obsidian directories if requested.
- **Best For**: Fast, broad semantic discovery and finding "notes like this."

### Related Notes
- [[System Overview]]
- [[Models and Embeddings]]
- [[Operations and Maintenance]]

### Questions / Ideas for Further Exploration
- 

### To-Do
- 

### Smart Connections Insights
- 
