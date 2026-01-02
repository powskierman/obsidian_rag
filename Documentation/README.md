# Obsidian RAG Documentation

Welcome to the comprehensive documentation for the Obsidian RAG Knowledge Graph System. This guide will help you navigate all available documentation and get the most out of your RAG system.

---

## 📚 Table of Contents

- [Quick Start](#quick-start)
- [Setup & Installation](#setup--installation)
- [Architecture & Design](#architecture--design)
- [Features & Capabilities](#features--capabilities)
- [Models & Configuration](#models--configuration)
- [Troubleshooting](#troubleshooting)
- [Development & Contributing](#development--contributing)
- [Additional Resources](#additional-resources)

---

## 🚀 Quick Start

**New to Obsidian RAG?** Start here:

- **[START_HERE.md](START_HERE.md)** - Complete getting started guide
- **[QUICKSTART.md](QUICKSTART.md)** - Fast setup for experienced users
- **[START_SERVICES.md](START_SERVICES.md)** - How to start the services

---

## ⚙️ Setup & Installation

### Docker Setup
- **[DOCKER_SETUP_SUMMARY.md](DOCKER_SETUP_SUMMARY.md)** - Comprehensive Docker deployment guide
- **[DOCKER_MODEL_RUNNER_INTEGRATION.md](DOCKER_MODEL_RUNNER_INTEGRATION.md)** - Integrating with Docker model runners
- **[Docker/](Docker/)** - Docker-specific configuration and guides

### Models & API Keys
- **[QUICKSTART_MODELS.md](QUICKSTART_MODELS.md)** - Model setup quickstart
- **[MODEL_SETUP_GUIDE.md](MODEL_SETUP_GUIDE.md)** - Detailed model configuration
- **[Setup/](Setup/)** - Additional setup guides
  - Cost decision guide
  - Next steps after installation
  - Configuration options

---

## 🏗️ Architecture & Design

### System Overview
- **[architecture/DEEP_THINKING_FLOW.md](architecture/DEEP_THINKING_FLOW.md)** - Deep thinking architecture flow
- **[Deep Thinking Implementation Plan.md](Deep%20Thinking%20Implementation%20Plan.md)** - Detailed implementation plan
- **[deep-thinking-rag-improvement-proposal.md](deep-thinking-rag-improvement-proposal.md)** - Enhancement proposals

### Data & Knowledge Graph
- **[KNOWLEDGE_GRAPH_STATISTICS.md](KNOWLEDGE_GRAPH_STATISTICS.md)** - Graph statistics and metrics
- **[Graph/](Graph/)** - Knowledge graph documentation
  - Graph builder guide
  - Quality improvements
  - Data flow diagrams
  - Transfer between machines

### Database Management
- **[DATABASE_MANAGEMENT.md](DATABASE_MANAGEMENT.md)** - Database operations guide

---

## ✨ Features & Capabilities

### Enhanced Search
- **[ENHANCED_SEARCH_PLAN.md](ENHANCED_SEARCH_PLAN.md)** - 3-section enhanced search (Vault + LLM + Web)
- **[KNOWLEDGE_GRAPH_TEST_PROMPTS.md](KNOWLEDGE_GRAPH_TEST_PROMPTS.md)** - Sample queries to test the system

### Embedding Features
- **[Embedding/](Embedding/)** - Embedding model guides
  - Model selection
  - Performance tuning
  - Integration guides

### Additional Features
- **[Features/](Features/)** - Feature-specific documentation

---

## 🤖 Models & Configuration

### LLM Providers
- **[Models/README.md](Models/README.md)** - Overview of supported models
- **[Models/SETUP.md](Models/SETUP.md)** - Model setup instructions

Supported providers:
- **Ollama** (Local, free)
- **Gemini Pro** (Google, API key required)
- **Claude Sonnet** (Anthropic, API key required)
- **GPT-OSS** (OpenAI-compatible)

### Embedding Models
- Sentence Transformers
- Nomic Embed
- Custom model integration

---

## 🔧 Troubleshooting

### Common Issues
- **[Troubleshooting/](Troubleshooting/)** - Comprehensive troubleshooting guides
  - **[API_KEY_VALIDATION_GUIDE.md](Troubleshooting/API_KEY_VALIDATION_GUIDE.md)** - API key issues
  - **[CHROMADB_CORRUPTION_FIX.md](Troubleshooting/CHROMADB_CORRUPTION_FIX.md)** - Database corruption fixes
  - **[DOCKER_TROUBLESHOOTING.md](Troubleshooting/DOCKER_TROUBLESHOOTING.md)** - Docker-specific issues
  - **[TROUBLESHOOTING_STREAMLIT_MODEL_ERROR.md](Troubleshooting/TROUBLESHOOTING_STREAMLIT_MODEL_ERROR.md)** - Streamlit errors
  - **[Queries.md](Troubleshooting/Queries.md)** - Query troubleshooting

### Specific Guides
- **[TROUBLESHOOTING_QUERY.md](TROUBLESHOOTING_QUERY.md)** - Query debugging

---

## 👨‍💻 Development & Contributing

### Development Guides
- **[Development-MOC.md](Development-MOC.md)** - Development map of content
- **[Tools-MOC.md](Tools-MOC.md)** - Tools and utilities guide
- **[guides/](guides/)** - Development guides
  - **[CODE_RESTRUCTURE_PLAN.md](guides/CODE_RESTRUCTURE_PLAN.md)** - Code organization
  - **[TESTING.md](guides/TESTING.md)** - Testing guidelines
  - **[PUSH_INSTRUCTIONS.md](guides/PUSH_INSTRUCTIONS.md)** - Git workflow

### MCP Integration
- **[MCP/](MCP/)** - Model Context Protocol integration
  - Setup instructions
  - Unified server configuration
  - Claude Desktop integration

### Claude Code Integration
- **[CLAUDE_CODE_WEB_SETUP.md](CLAUDE_CODE_WEB_SETUP.md)** - Claude Code web integration
- **[CLAUDE_CODE_WEB_INSTRUCTIONS.md](CLAUDE_CODE_WEB_INSTRUCTIONS.md)** - Usage instructions
- **[guides/CLAUDE_CODE_WEB_INSTRUCTIONS.md](guides/CLAUDE_CODE_WEB_INSTRUCTIONS.md)** - Additional guide

---

## 📖 Additional Resources

### Organization & Maintenance
- **[VAULT_ORGANIZATION_GUIDE.md](VAULT_ORGANIZATION_GUIDE.md)** - Organizing your Obsidian vault
- **[VAULT_STANDARDIZATION_GUIDE.md](VAULT_STANDARDIZATION_GUIDE.md)** - Standardizing vault structure
- **[CLEANUP_REPORT.md](CLEANUP_REPORT.md)** - Repository cleanup report
- **[CLEANUP_SUMMARY.md](CLEANUP_SUMMARY.md)** - Cleanup summary
- **[ORGANIZATION_SUMMARY.md](ORGANIZATION_SUMMARY.md)** - Organization overview

### Planning & Updates
- **[AUDIT_PLAN.md](AUDIT_PLAN.md)** - System audit plan
- **[UPDATE_SUMMARY.md](UPDATE_SUMMARY.md)** - Recent updates
- **[📋 Implementation Checklist.md](%F0%9F%93%8B%20Implementation%20Checklist.md)** - Feature checklist

### Index & Navigation
- **[INDEX.md](INDEX.md)** - Documentation index
- **[readme_final.md](readme_final.md)** - Final comprehensive README

### Archive
- **[Archive/](Archive/)** - Archived documentation (deprecated/historical)
- **[Analysis/](Analysis/)** - System analysis reports

---

## 🔍 Quick Reference

### Configuration Files
| File | Purpose |
|------|---------|
| `.env` | Environment variables (API keys, service URLs) |
| `docker-compose.yml` | Docker service definitions |
| `requirements.txt` | Python dependencies |

### Service Ports
| Service | Port | Description |
|---------|------|-------------|
| Streamlit UI | 8501 | Web interface |
| Embedding Service | 8000 | Vector search API |
| Graph Query Service | 8002 | Knowledge graph API |

### Key Directories
| Directory | Purpose |
|-----------|---------|
| `src/` | Source code |
| `Documentation/` | All documentation (you are here!) |
| `Scripts/` | Utility scripts |
| `config/` | Configuration files |
| `graph_data/` | Knowledge graph data |
| `chroma_db/` | Vector database |

---

## 💡 Getting Help

1. **Check the relevant section above** for your topic
2. **Search the [Troubleshooting](#troubleshooting) section**
3. **Review [KNOWLEDGE_GRAPH_TEST_PROMPTS.md](KNOWLEDGE_GRAPH_TEST_PROMPTS.md)** for query examples
4. **Check the [Archive/](Archive/)** for historical context

---

## 🎯 Recommended Reading Path

### For New Users:
1. [START_HERE.md](START_HERE.md)
2. [QUICKSTART.md](QUICKSTART.md)
3. [DOCKER_SETUP_SUMMARY.md](DOCKER_SETUP_SUMMARY.md)
4. [QUICKSTART_MODELS.md](QUICKSTART_MODELS.md)
5. [KNOWLEDGE_GRAPH_TEST_PROMPTS.md](KNOWLEDGE_GRAPH_TEST_PROMPTS.md)

### For Developers:
1. [architecture/obsidian_rag_analysis.md](architecture/obsidian_rag_analysis.md)
2. [Development-MOC.md](Development-MOC.md)
3. [guides/CODE_RESTRUCTURE_PLAN.md](guides/CODE_RESTRUCTURE_PLAN.md)
4. [guides/TESTING.md](guides/TESTING.md)

### For Advanced Features:
1. [Deep Thinking Implementation Plan.md](Deep%20Thinking%20Implementation%20Plan.md)
2. [ENHANCED_SEARCH_PLAN.md](ENHANCED_SEARCH_PLAN.md)
3. [Graph/](Graph/)
4. [MCP/](MCP/)

---

**Last Updated**: 2025-12-18

*This documentation is actively maintained. If you find any broken links or outdated information, please update accordingly.*
