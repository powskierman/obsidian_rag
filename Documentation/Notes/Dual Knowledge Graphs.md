---
aliases: 
created: 2026-01-04 12:45
tags: #rag #graph #knowledge
Backlink: "[[System Overview]]"
---
### Main Idea
- The system uses two complementary graphs (LightRAG and NetworkX) to provide both semantic concept extraction and structural vault analysis.

### References
- [[SYSTEM_OVERVIEW_2025.md]]

### Notes
- **LightRAG Service** (Port 8001): Entity-Centric Semantic Knowledge. Focuses on AI-extracted concepts and implicit relationships.
- **NetworkX Graph Service** (Port 8002): Note-Centric Vault Structure. Focuses on explicit wiki-links and your intentional organization.
- **Synergy**:
    - LightRAG finds hidden connections you didn't link.
    - NetworkX preserves your manual hierarchy and architecture.

| Feature | [[LightRAG Service]] | [[NetworkX Graph Service]] |
|---------|-----------------|-----------------|
| **Granularity** | Concepts/entities | Note files |
| **Relationships** | AI-extracted semantic | Explicit wiki-links |
| **Coverage** | Implicit knowledge | Intentional structure |

### Related Notes
- [[LightRAG Service]]
- [[NetworkX Graph Service]]
- [[System Overview]]

### Questions / Ideas for Further Exploration
- 

### To-Do
- 

### Smart Connections Insights
- 
