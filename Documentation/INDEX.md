# Obsidian RAG Documentation

Complete guide to the Obsidian RAG system with Deep Thinking agent capabilities.

## 📖 Quick Navigation

### Getting Started
- **[README.md](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/README.md)** - Project overview and main entry point
- **[Quickstart Guide](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/setup/QUICKSTART.md)** - Fast setup for new users (5 minutes)
- **[Getting Started](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/setup/GETTING_STARTED.md)** - Detailed first-time setup guide

---

## 🏗️ Architecture

### System Design
- **[Deep Thinking Flow](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/architecture/DEEP_THINKING_FLOW.md)** - Complete multi-agent reasoning pipeline with diagrams
  - 5 specialized agents (Planner, Supervisor, Reflector, Policy, Synthesizer)
  - Execution flow with vault + web search integration
  - Image embedding for hardware/technical queries
  
- **[System Analysis](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/architecture/obsidian_rag_analysis.md)** - In-depth technical architecture analysis

---

## ⚙️ Setup & Configuration

### Initial Setup
- **[Quickstart](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/setup/QUICKSTART.md)** - Docker-based quick start (recommended)
- **[Getting Started](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/setup/GETTING_STARTED.md)** - Manual setup with detailed explanations
- **[GraphRAG Setup](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/setup/GRAPHRAG_SETUP.md)** - Knowledge graph configuration

### Integration Setup
- **[Claude Code Web Setup](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/setup/CLAUDE_CODE_WEB_SETUP.md)** - Integrate with Claude desktop app via MCP

### Environment Variables
Required API keys and service URLs:
```bash
ANTHROPIC_API_KEY=sk-ant-...     # For Deep Thinking agents
TAVILY_API_KEY=tvly-...          # For web search with images
EMBEDDING_SERVICE_URL=http://localhost:8000
CLAUDE_GRAPH_SERVICE_URL=http://localhost:8002
OBSIDIAN_VAULT_PATH=/path/to/vault
```

---

## 🔧 Troubleshooting

### Common Issues
- **[Docker Troubleshooting](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/troubleshooting/DOCKER_TROUBLESHOOTING.md)** - Container rebuild, orphaned containers, env vars
- **[API Key Validation](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/troubleshooting/API_KEY_VALIDATION_GUIDE.md)** - Verify API keys are configured correctly
- **[Streamlit Model Error](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/troubleshooting/TROUBLESHOOTING_STREAMLIT_MODEL_ERROR.md)** - Fix Streamlit UI model loading issues
- **[ChromaDB Corruption](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/Troubleshooting/CHROMADB_CORRUPTION_FIX.md)** - Repair corrupted vector database

### Debug Checklist
1. ✅ Check environment variables loaded (`docker exec obsidian-ui env | grep TAVILY`)
2. ✅ Verify services running (`docker-compose ps`)
3. ✅ Check logs (`docker logs obsidian-ui --tail 50`)
4. ✅ Rebuild containers after code changes (`docker-compose build --no-cache`)
5. ✅ Test locally with `reproduce_issue.py` script

---

## 📚 User Guides

### Using the System
- **[CLI Search Guide](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/guides/README_CLI_SEARCH.md)** - Command-line search interface
- **[Claude Code Web Instructions](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/guides/CLAUDE_CODE_WEB_INSTRUCTIONS.md)** - Using Claude desktop integration
- **[Testing Guide](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/guides/TESTING.md)** - Running test suites and verification

### Development & Maintenance
- **[Service Capabilities](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/guides/SERVICE_CAP_INFO.md)** - What each service provides
- **[Push Instructions](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/guides/PUSH_INSTRUCTIONS.md)** - Git workflow and deployment
- **[Code Restructure Plan](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/guides/CODE_RESTRUCTURE_PLAN.md)** - Planned improvements

---

## 🔍 Deep Thinking Features

### What is Deep Thinking RAG?
An **agentic multi-step reasoning system** that combines your personal Obsidian vault with external web knowledge.

### Key Capabilities
1. **Intelligent Query Decomposition** - Breaks complex questions into research steps
2. **Multi-Source Search** - Combines vault (vector/graph) + web (Tavily) results
3. **Image Embedding** - Automatically includes pinouts, diagrams, schematics
4. **Iterative Refinement** - Can revise research plan if gaps detected
5. **Source Attribution** - Every fact cites vault note `[[Note]]` or web URL

### When to Use Deep Thinking
- ✅ Technical "how-to" questions (e.g., hardware wiring, software config)
- ✅ Medical queries needing external context (treatment protocols, side effects)
- ✅ Research requiring both personal notes AND authoritative sources
- ❌ Simple fact lookups (use fast vector search instead)

### Example Query Execution
```
Query: "How do I connect a nextion display to an esp32 using esphome"

Plan: 4 steps
  1. [vault]  What Nextion projects exist in my vault?
  2. [web]    Official ESPHome Nextion documentation
  3. [web]    ESP32 UART wiring diagrams  
  4. [web]    Troubleshooting common issues

Result: 95% confidence
  - 3 vault notes cited
  - 7 web URLs cited
  - 2 pinout images embedded
```

---

## 🐳 Docker Quick Reference

### Start Services
```bash
docker-compose up -d
```

### Rebuild After Code Changes
```bash
docker-compose build --no-cache
docker-compose up -d
```

### View Logs
```bash
docker logs obsidian-ui --tail 50 -f
```

### Remove Orphaned Containers
```bash
docker-compose down --remove-orphans
```

---

## 📂 Project Structure

```
obsidian_rag/
├── deep_thinking/          # Agentic reasoning components
│   ├── orchestrator.py     # Main loop coordination
│   ├── planner.py          # Query decomposition
│   ├── supervisor.py       # Search execution (vault + web)
│   ├── reflector.py        # Insight extraction
│   ├── policy.py           # Loop control logic
│   └── synthesizer.py      # Final answer generation
├── src/
│   ├── ui/                 # Streamlit interfaces
│   └── services/           # ChromaDB, LightRAG services
├── Documentation/          # This documentation
├── tests/                  # Test suites
├── docker-compose.yml      # Service orchestration
└── requirements.txt        # Python dependencies
```

---

## 🔄 Recent Improvements

### November 2024
- ✅ **Web Search Migration**: Switched from DuckDuckGo to Tavily for better LLM-optimized results
- ✅ **Image Support**: Automatic embedding of pinouts, diagrams, schematics in answers
- ✅ **Vault Retrieval Fix**: Keyword-based search to avoid generic term matching
- ✅ **Docker Environment**: Fixed TAVILY_API_KEY not being passed to containers
- ✅ **Planner Intelligence**: Explicit rules for when to use web vs vault searches

### Performance Gains
- Confidence: **40% → 95%** (with web enrichment)
- Vault retrieval precision: **0 docs → 5 docs** (keyword fix)
- Web search trigger rate: **0% → 75%** (planner rules)

---

## 📞 Support & Resources

### Testing Script
Use [`reproduce_issue.py`](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/reproduce_issue.py) to test the full RAG pipeline locally:
```bash
./venv/bin/python reproduce_issue.py
```

### Additional Documentation
- **[MCP Setup](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/MCP/)** - Model Context Protocol integration
- **[Graph](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/Graph/)** - Knowledge graph optimization guides
- **[Setup](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/Setup/)** - Cost decisions and next steps

---

## 🎯 Quick Links

| Need to... | Go to |
|------------|-------|
| Set up system | [Quickstart](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/setup/QUICKSTART.md) |
| Understand architecture | [Deep Thinking Flow](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/architecture/DEEP_THINKING_FLOW.md) |
| Fix Docker issues | [Docker Troubleshooting](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/troubleshooting/DOCKER_TROUBLESHOOTING.md) |
| Run tests | [Testing Guide](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/guides/TESTING.md) |
| Configure API keys | [API Key Validation](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/Documentation/troubleshooting/API_KEY_VALIDATION_GUIDE.md) |

---

**Last Updated**: November 2024  
**Version**: 2.0 (Deep Thinking + Image Support)
