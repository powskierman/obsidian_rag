# System Architecture

This diagram reflects the current Docker services and their primary connections.

```mermaid
graph TB
    User[User]

    subgraph UI
        WebApp[Next.js WebApp
Port 3030]
    end

    subgraph Services
        Gateway[API Gateway
Port 4000]
        Vector[Embedding Service
Port 8000]
        Graph[Graph Service
Port 8002]
        LightRAG[LightRAG Service
Port 8001]
        MemPalace[MemPalace Sidecar
Port 7788]
    end

    subgraph Data
        Chroma[ChromaDB
chroma_db/]
        GraphData[Graph Data
data/graph_data/]
        LightData[LightRAG DB
lightrag_db/]
        Vault[Obsidian Vault]
    end

    User --> WebApp --> Gateway
    Gateway -->|Ask| Vector
    Gateway -->|Research| Graph
    Gateway -->|Research| LightRAG
    Gateway -->|Investigate WS| Graph
    Gateway -->|sources=mempalace| MemPalace

    Vector --> Chroma
    Vector --> Vault
    Graph --> GraphData
    Graph --> Vault
    LightRAG --> LightData
    LightRAG --> Vault
    MemPalace --> Vault
```

See `Documentation/reference/governance/PROJECT_CONSTITUTION.md` for the current authoritative service roles and ports.
