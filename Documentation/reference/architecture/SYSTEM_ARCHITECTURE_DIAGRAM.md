# System Architecture

This diagram reflects the current Docker services, the host-side MemPalace sidecar, and their primary connections. Canonical mode names are shown on arrows; legacy names (`vector`, `cascading`, `vault_review`, `mempalace`, `deep-thinking`) are normalized at the gateway via `src/services/query_dispatch.py`.

```mermaid
graph TB
    User[User]

    subgraph UI [User Interfaces]
        WebApp["Next.js WebApp<br/>host port 3030<br/>(container port 3000)"]
        Streamlit["Streamlit UI<br/>port 8501"]
        MCP["MCP Server<br/>(unified)<br/>port 8811"]
    end

    subgraph Services [Docker Services]
        Gateway["API Gateway<br/>port 4000"]
        Vector["Embedding Service<br/>port 8000"]
        Graph["NetworkX Graph Service<br/>port 8002"]
        LightRAG["LightRAG Service<br/>port 8001"]
    end

    subgraph Host [Host-Side]
        MemPalace["MemPalace Sidecar<br/>(launchd, host port 7788)"]
        Tavily["Tavily Web Search<br/>(external API)"]
    end

    subgraph Data [Data Stores]
        Chroma[("ChromaDB<br/>chroma_db/")]
        GraphData[("NetworkX snapshot<br/>graph_data/")]
        LightData[("LightRAG DB<br/>lightrag_db/")]
        Vault[("Obsidian Vault<br/>(read-only mount)")]
    end

    User --> WebApp
    User --> Streamlit
    User --> MCP
    WebApp --> Gateway
    Streamlit --> Gateway
    MCP --> Gateway
    MCP -->|search_vault_text<br/>read_vault_note| Vault

    Gateway -->|"ask (legacy: vector)"| Vector
    Gateway -->|"research (legacy: cascading)<br/>anchor + expand"| Graph
    Gateway -->|"research<br/>concept expansion"| LightRAG
    Gateway -->|"investigate (WS)<br/>multi-step reasoning"| Graph
    Gateway -->|"sources=[\"mempalace\"]"| MemPalace
    Gateway -->|"sources=[\"web\"]<br/>or web_search=true"| Tavily

    Vector --> Chroma
    Vector --> Vault
    Graph --> GraphData
    Graph --> Vault
    LightRAG --> LightData
    LightRAG --> Vault
    MemPalace --> Vault
```

Notes:
- The `investigate` agent loop (deep research) lives in the `deep_thinking/` package and is orchestrated from inside the API Gateway WebSocket handler; it can call any of the retrieval back-ends iteratively. See `Documentation/reference/architecture/DEEP_THINKING_FLOW.md`.
- The MCP server has direct filesystem access to the vault for `search_vault_text`, `read_vault_note`, `batch_read_vault_notes`, and `update_vault_note`. Its semantic-search tools delegate to the gateway/embedding service.
- MemPalace is **not** in `docker-compose.yml`. It runs on the host (`mempalace_server.py`, `com.obsidianrag.mempalace.plist` for launchd) and is reached by the gateway via `host.docker.internal:7788`.

See `Documentation/reference/governance/PROJECT_CONSTITUTION.md` for the current authoritative service roles and ports.
