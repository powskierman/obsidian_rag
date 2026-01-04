---
aliases: 
created: 2026-01-04 12:45
tags: #rag #api #gateway
Backlink: "[[System Overview]]"
---
### Main Idea
- The API Gateway acts as the central brain, orchestrating queries across different search services and managing LLM providers.

### References
- [[SYSTEM_OVERVIEW_2025.md]]
- Port 4000; Container: `obsidian-api-gateway`

### Notes
- **Core Responsibilities**:
    - **Routing**: Points queries to [[Vector Search Service]], [[LightRAG Service]], or [[NetworkX Graph Service]].
    - **Orchestration**: Powers complex modes like `hybrid`, `cascading`, and `dual-graph`.
    - **LLM Selection**: Routes to Claude, Gemini, Kimi, or local Ollama.
    - **WebSocket**: Interface for real-time [[Deep Thinking Agent]] status.
- **Common Modes**:
    - `hybrid`: Synthesis of all 3 main retrieval sources.
    - `dual-graph`: Merged results from both graph services.

### Related Notes
- [[System Overview]]
- [[Deep Thinking Agent]]
- [[Query Strategy Matrix]]

### Questions / Ideas for Further Exploration
- 

### To-Do
- 

### Smart Connections Insights
- 
