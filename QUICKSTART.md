# 🚀 Obsidian RAG - Quick Start Guide

Get started with Obsidian RAG in 5 minutes!

## Prerequisites

- **Python 3.10+** - [Install Python](https://www.python.org/downloads/)
- **Ollama** (for local LLM) - [Install Ollama](https://ollama.ai)
- **Anthropic API Key** - [Get free API key](https://console.anthropic.com/account/keys)
- **Optional: Docker** - For containerized deployment

## Installation (One Time Setup)

### Step 1: Run Setup Script
```bash
./setup.sh
```

This script will:
- Check your Python installation
- Create `.env.local` for your API keys
- Install Python dependencies
- Verify Docker/Ollama availability

### Step 2: Edit `.env.local`
```bash
nano .env.local
```

Add your Anthropic API key:
```env
ANTHROPIC_API_KEY=sk-ant-your-key-here
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5-coder:14b
```

### Step 3: Start Ollama
In a separate terminal:
```bash
ollama serve
```

First time? Download the model:
```bash
ollama pull qwen2.5-coder:14b
```

## Running Obsidian RAG

### Option 1: Local (Recommended for Development)
```bash
./run.sh
```

Starts:
- Embedding Service (port 8000)
- Streamlit UI (port 8501)

Then open: **http://localhost:8501**

### Option 2: Docker (Recommended for Production)
```bash
./Scripts/docker_start.sh
```

Starts all services in Docker:
- Embedding Service
- LightRAG Service
- Streamlit UI
- Ollama integration

Then open: **http://localhost:8501**

## Usage

### 1. Connect to Obsidian Vault
In the Streamlit UI sidebar:
- Set vault path to your Obsidian folder
- Or use the file selector

### 2. Index Your Vault
Click the "📑 Index Vault" button to:
- Scan all markdown files
- Create vector embeddings
- Build knowledge graph (optional)

**First time:** 5-15 minutes for 1000 notes

### 3. Search & Query
- Type a question in the chat box
- Choose retrieval mode:
  - **Vector** - Fast semantic search
  - **Graph-Naive** - Entity lookups
  - **Graph-Local** - Entity + context
  - **Graph-Global** - Full knowledge reasoning

### 4. Rate Results
After each answer:
- Click 😊 or 😞 emoji to rate
- This helps improve future results
- Feedback is stored locally

## Project Structure

```
obsidian_rag/
├── setup.sh                    # First-time setup
├── run.sh                      # Start services locally
├── embedding_service.py        # Vector search backend
├── streamlit_ui_enhanced.py    # Web UI
├── query_feedback.py           # Feedback database
├── requirements.txt            # Python dependencies
├── .env.local                  # YOUR API KEYS (auto-created)
├── .env.local.example          # Template
├── chroma_db/                  # Vector database
├── feedback_db/                # User feedback
├── Scripts/
│   ├── docker_start.sh        # Docker deployment
│   ├── docker_stop.sh
│   └── index_with_graphrag.sh # Knowledge graph indexing
└── Documentation/
    ├── README.md              # Full documentation
    ├── TROUBLESHOOTING.md     # Common issues
    └── DATABASE_MANAGEMENT.md # Database info
```

## Common Tasks

### Stop Services
**Local:**
```bash
# Press Ctrl+C in the terminal
```

**Docker:**
```bash
./Scripts/docker_stop.sh
```

### View Service Logs
**Embedding Service (local):**
```bash
tail -f /tmp/embedding_service.log
```

**Docker:**
```bash
docker-compose logs -f
```

### Backup Your Data
```bash
./Scripts/backup.sh
```

Backs up:
- Embeddings database
- Feedback database
- Configuration

### Clean Up
```bash
./Scripts/clean.sh
```

Removes:
- Databases
- Cache files
- Temporary files

## Troubleshooting

### "Ollama is not running"
```bash
# In a new terminal:
ollama serve

# Or if Ollama isn't installed:
# Download from https://ollama.ai
```

### "Failed to load embedding model"
```bash
# Make sure dependencies are installed:
pip install -r requirements.txt

# Or reinstall:
pip install --upgrade sentence-transformers
```

### "Embedding Service won't start"
Check the log:
```bash
cat /tmp/embedding_service.log
```

### "Connection refused" on port 8000/8501
```bash
# Check if services are running:
./Scripts/check_status.sh

# Check port availability:
lsof -i :8000
lsof -i :8501
```

### API Key Not Being Loaded
```bash
# Verify .env.local exists:
ls -la .env.local

# Check file contents (first line should have your key):
head -1 .env.local

# Verify ANTHROPIC_API_KEY is exported:
echo $ANTHROPIC_API_KEY
```

## Environment Variables

All variables are loaded from `.env.local` automatically.

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Required | Your API key from Anthropic |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server address |
| `OLLAMA_MODEL` | `qwen2.5-coder:14b` | LLM model to use |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding model |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Logging level |

## Performance Tips

- **Faster indexing:** Use local Ollama instead of cloud APIs
- **Better results:** Use more sources (slider in sidebar)
- **Reduce latency:** Use vector search for quick lookups
- **More reasoning:** Use graph-global for complex questions

## Cost Estimation

**Per 1000 notes:**
- Ollama local: **$0** (runs locally)
- Claude Haiku: **$1-2**
- Claude Sonnet: **$10-20**

## Next Steps

- 📚 Read full [Documentation](./Documentation/README.md)
- 🔧 Learn about [Database Management](./Documentation/DATABASE_MANAGEMENT.md)
- 🐳 Try [Docker Deployment](./Scripts/docker_start.sh)
- 📊 Build a [Knowledge Graph](./Scripts/index_with_graphrag.sh)

## Support

- 📖 [Full Documentation](./Documentation/)
- 🐛 [Troubleshooting Guide](./Documentation/TROUBLESHOOTING.md)
- 💬 Check existing issues on GitHub

## Tips for Best Results

1. **Organize your vault** - Use consistent folder structure
2. **Add metadata** - Use frontmatter with tags, categories
3. **Create links** - Use wikilinks to connect related notes
4. **Rate responses** - Click emoji to help the system learn
5. **Use specific queries** - "What is CAR-T therapy?" works better than "tell me about my health"

Happy knowledge management! 🧠✨
