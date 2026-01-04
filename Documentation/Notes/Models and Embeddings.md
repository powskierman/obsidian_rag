---
aliases: 
created: 2026-01-04 12:45
tags: #rag #llm #embeddings
Backlink: "[[System Overview]]"
---
### Main Idea
- A diversified stack of AI models tailored for specific roles: indexing (extraction), reasoning (synthesis), and embedding (similarity).

### References
- [[SYSTEM_OVERVIEW_2025.md]]

### Notes
- **Indexing Models**:
    - **LightRAG**: Kimi K2 (`moonshotai/kimi-k2-0905`) - optimized for entity/relationship extraction.
    - **NetworkX**: GPT-4o-mini - used for fast note-level structural analysis.
- **Retrieval & Reasoning**:
    - **Claude**: Sonnet 4.5 - the gold standard for high-fidelity synthesis.
    - **DeepSeek**: R1 - specialized for deep reasoning tasks.
    - **Ollama**: Llama 3.2 / Qwen 2.5 - fully offline/private local options.
- **Embeddings**: `nomic-embed-text` (local) with OpenAI fallback.
- **Memory**: Powered by `mem0` for persistent user-context learning.

### Related Notes
- [[System Overview]]
- [[Deep Thinking Agent]]
- [[Vector Search Service]]

### Questions / Ideas for Further Exploration
- 

### To-Do
- 

### Smart Connections Insights
- 
