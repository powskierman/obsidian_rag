---
aliases: 
created: 2026-01-04 12:45
tags: #rag #ops #maintenance
Backlink: "[[System Overview]]"
---
### Main Idea
- A set of operational procedures for managing automation, monitoring system health, and rebuilding knowledge indices.

### References
- [[SYSTEM_OVERVIEW_2025.md]]

### Notes
- **Automation**:
    - **Watcher**: `watching_scanner.py` for real-time vector indexing.
    - **Launcher**: `Launch Obsidian RAG.command` for Docker orchestration.
- **Monitoring**:
    - Gateway Health: `localhost:4000/api/v1/health`
    - Graph Stats: `localhost:8001/stats`
- **Indexing**:
    - **Fast Rebuild**: `Scripts/index_with_kimi.sh` (Minutes).
    - **Deep Rebuild**: LightRAG `/index-vault` (Hours).
- **Data Safety**:
    - **SOTA Mode**: Separate environment for experimental graph testing (configured in `.env`).

### Related Notes
- [[System Overview]]
- [[Vector Search Service]]
- [[API Gateway]]

### Questions / Ideas for Further Exploration
- 

### To-Do
- 

### Smart Connections Insights
- 
