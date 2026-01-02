This project's purpose is to provide local RAG service to query an Obsidian vault.
The search includes vector and graphic searches.
Docker containers are privileged whenever possible.  Docker model runner has priority
MCPs should be taken advantage of

Main parts:
- **Embedding Service** (Docker Container) - Port 8000
   - Sentence Transformers (`all-MiniLM-L6-v2`)
   - ChromaDB vector database
   - Handles indexing and semantic search
   - REST API for embedding and querying
- **Graph Query Service** (Docker Container) - Port 8002
   - NetworkX knowledge graph (note-centric wiki-links)
   - Graph querying and traversal
   - REST API for graph operations
- **LightRAG Service** (Docker Container) - Port 8001
   - Entity-centric semantic knowledge graph
   - Advanced entity extraction and relationship mapping
   - Hybrid search capabilities
- **Next.js Web UI** (Docker Container) - Port 3000
   - Modern React-based interface
   - 7-mode search system (Vector, Notes, Entities, Notes+Vector, Entities+Vector, Dual-Graph, Hybrid)
   - Deep thinking integration
   - Real-time chat with source citations
**LLM** (Ollama Host) - Port 11434
   - Qwen 2.5 Coder 14B (default model)
   - DeepSeek R1:14b (reasoning model alternative)
   - nomic-embed-text (embeddings)
   - Local inference, no API calls
**Scanner Scripts** (Python)
   - `simple_scanner.py` - Basic one-time indexing
   - `obsidian_scanner.py` - Advanced scanner with file watching
   - Chunks documents (1000 chars, 200 overlap)
   - Extracts YAML frontmatter metadata
**Environment**
- **Architecture:** Docker-based services (eliminates Python version issues)
- **Project Location:** `/Users/michel/iCloud Drive/ai/RAG/obsidian_rag`
- **Database:** `./chroma_db` (persistent, in Docker volume)
- **Vault Path:** `/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel`
