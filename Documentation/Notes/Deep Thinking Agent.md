---
aliases: 
created: 2026-01-04 12:45
tags: #rag #agent #reasoning
Backlink: "[[API Gateway]]"
---
### Main Idea
- A multi-step reasoning agent that decomposes complex user queries into sub-questions and routes them to optimal retrieval strategies.

### References
- [[SYSTEM_OVERVIEW_2025.md]]
- WebSocket: `ws://localhost:4000/api/v1/deep-research`

### Notes
- **Process Workflow**:
    1. **Decomposition**: Questions are split into simpler logic steps.
    2. **Adaptive Routing**: Strategically chooses Vector, Graph, or Web search per step.
    3. **Reranking**: Uses cross-encoder models to filter the top 15 most relevant results.
    4. **Memory Integration**: Uses `mem0` to search and update personal interaction context.
    5. **Synthesis**: Final LLM generation combining all retrieved evidence.
- **Example Use Case**: Connecting unrelated topics like "CAR-T therapy" and "garage automation" by identifying shared concepts in the knowledge graph.

### Related Notes
- [[System Overview]]
- [[API Gateway]]
- [[Models and Embeddings]]

### Questions / Ideas for Further Exploration
- 

### To-Do
- 

### Smart Connections Insights
- 
