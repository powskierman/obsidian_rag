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
**GraphRAG-Local Service** (Docker Container) - Port 8003
   - Microsoft GraphRAG with specialized Ollama integration
   - Advanced knowledge graph construction and community detection
   - Medical terminology optimization
   - Global and local search capabilities
   - GPT-OSS + nomic-embed-text integration
**Streamlit UI** (Docker Container) - Port 8501
   - Natural language queries
   - Source citations with relevance scores
   - Adjustable parameters (sources, temperature)
   - Model selection interface
**LLM** (Ollama Host) - Port 11434
   - **Primary Model:** GPT-OSS (GraphRAG-Local optimized)
   - Qwen 2.5 Coder 14B (traditional RAG default)
   - DeepSeek R1:14b (reasoning model alternative)
   - nomic-embed-text (GraphRAG embeddings)
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
