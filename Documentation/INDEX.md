# Obsidian RAG Documentation

**Quick Links**: [Quickstart](#quickstart) • [Features](#features) • [Setup](#setup) • [Troubleshooting](#troubleshooting)

---

## 🚀 Quickstart

**TL;DR**: Get up and running in 5 minutes

- **[QUICKSTART.md](QUICKSTART.md)** - Fast setup guide for graph building and querying
- **[START_SERVICES.md](START_SERVICES.md)** - How to start Docker services

---

## ✨ Features

### Hybrid Search (Default)
**TL;DR**: Best of both worlds - combines graph relationships with detailed document content

📄 **[Features/HYBRID_SEARCH_IMPLEMENTATION_PLAN.md](Features/HYBRID_SEARCH_IMPLEMENTATION_PLAN.md)**
- Graph-guided vector search
- 2-5 second queries
- Automatic fallback to vector-only

### Search Modes Comparison
**TL;DR**: Vector (fast, detailed), Graph (relationships), Hybrid (both)

📄 **[Features/SEARCH_COMPARISON_RESULTS.md](Features/SEARCH_COMPARISON_RESULTS.md)**
- Performance benchmarks
- Quality comparisons
- Use case recommendations

### Search Examples
**TL;DR**: Real-world query examples for all search modes

📄 **[Features/SEARCH_EXAMPLES.md](Features/SEARCH_EXAMPLES.md)**
- Medical queries
- Timeline questions
- Relationship exploration

### Combined Search Workflow
**TL;DR**: Best practices for using multiple search modes together

📄 **[Features/COMBINED_SEARCH_WORKFLOW.md](Features/COMBINED_SEARCH_WORKFLOW.md)**
- When to use each mode
- Query optimization
- Result interpretation

---

## 🔧 Setup & Configuration

### Initial Setup
📄 **[Setup/NEXT_STEPS.md](Setup/NEXT_STEPS.md)** - Post-installation configuration  
📄 **[Setup/COST_DECISION_GUIDE.md](Setup/COST_DECISION_GUIDE.md)** - Model selection and cost analysis

### Vault Management
**TL;DR**: Standardize your Obsidian vault for better RAG performance

📄 **[VAULT_STANDARDIZATION_GUIDE.md](VAULT_STANDARDIZATION_GUIDE.md)**
- Template application
- Tag generation
- Link management
- Folder organization

---

## 🧠 Knowledge Graph

**TL;DR**: Build and optimize your knowledge graph with Claude

📄 **[Graph/IMPROVED_GRAPH_BUILDER_GUIDE.md](Graph/IMPROVED_GRAPH_BUILDER_GUIDE.md)** - Complete guide  
📄 **[Graph/QUALITY_IMPROVEMENTS.md](Graph/QUALITY_IMPROVEMENTS.md)** - Improve graph quality  
📄 **[Graph/IMPROVE_MEDICAL_QUALITY.md](Graph/IMPROVE_MEDICAL_QUALITY.md)** - Medical domain tips  
📄 **[Graph/GRAPH_DATA_FLOW.md](Graph/GRAPH_DATA_FLOW.md)** - How data flows  
📄 **[Graph/TRANSFER_BETWEEN_MACHINES.md](Graph/TRANSFER_BETWEEN_MACHINES.md)** - Move graphs  
📄 **[KNOWLEDGE_GRAPH_TEST_PROMPTS.md](KNOWLEDGE_GRAPH_TEST_PROMPTS.md)** - Test queries

---

## 🤖 MCP Integration (Claude Desktop)

**TL;DR**: Connect Claude Desktop to your Obsidian vault via MCP

📄 **[MCP/MCP_SETUP_INSTRUCTIONS.md](MCP/MCP_SETUP_INSTRUCTIONS.md)** - **Start here**  
📄 **[MCP/MCP_VAULT_SEARCH_GUIDE.md](MCP/MCP_VAULT_SEARCH_GUIDE.md)** - Search capabilities  
📄 **[MCP/MCP_CAPABILITIES_COMPARISON.md](MCP/MCP_CAPABILITIES_COMPARISON.md)** - Server comparison  
📄 **[MCP/FORCE_UNIFIED_SERVER.md](MCP/FORCE_UNIFIED_SERVER.md)** - Force unified server usage  
📄 **[MCP/TROUBLESHOOT_GRAPH_TOOLS.md](MCP/TROUBLESHOOT_GRAPH_TOOLS.md)** - Fix graph tools

---

## 🐳 Docker

**TL;DR**: Docker setup and troubleshooting

📄 **[Docker/DOCKER_MCP_INTEGRATION.md](Docker/DOCKER_MCP_INTEGRATION.md)** - Docker MCP setup  
📄 **[Docker/DOCKER_GATEWAY_TROUBLESHOOTING.md](Docker/DOCKER_GATEWAY_TROUBLESHOOTING.md)** - Gateway issues  
📄 **[Docker/DOCKER_GATEWAY_CLAUDE_DESKTOP_FIX.md](Docker/DOCKER_GATEWAY_CLAUDE_DESKTOP_FIX.md)** - Claude Desktop fix  
📄 **[Docker/DISABLE_DOCKER_OBSIDIAN.md](Docker/DISABLE_DOCKER_OBSIDIAN.md)** - Disable Docker toolkit server

---

## 🛠️ Troubleshooting

**TL;DR**: Common issues and fixes

📄 **[Troubleshooting/CHROMADB_CORRUPTION_FIX.md](Troubleshooting/CHROMADB_CORRUPTION_FIX.md)** - Fix ChromaDB corruption

**Also see**:
- [MCP/TROUBLESHOOT_GRAPH_TOOLS.md](MCP/TROUBLESHOOT_GRAPH_TOOLS.md) - MCP graph issues
- [Docker/DOCKER_GATEWAY_TROUBLESHOOTING.md](Docker/DOCKER_GATEWAY_TROUBLESHOOTING.md) - Docker gateway

---

## 📊 Analysis & Improvements

### KET-RAG Analysis
**TL;DR**: Advanced Graph-RAG framework - NOT recommended for current setup

📄 **[Analysis/KET_RAG_ANALYSIS.md](Analysis/KET_RAG_ANALYSIS.md)**
- 20% cost savings, 32% quality boost
- Too complex for 1,771 notes
- Reconsider at 10,000+ notes

### Project Improvements
**TL;DR**: Recommended optimizations and future enhancements

📄 **[Analysis/Improvements.md](Analysis/Improvements.md)** - Enhancement roadmap  
📄 **[Analysis/CODE_CLEANUP_SUMMARY.md](Analysis/CODE_CLEANUP_SUMMARY.md)** - Code cleanup history

---

## 📦 Archive

Historical and deprecated documentation: **[Archive/](Archive/)**

---

## 🎯 Common Tasks

| Task | Document |
|------|----------|
| **First time setup** | [QUICKSTART.md](QUICKSTART.md) |
| **Start services** | [START_SERVICES.md](START_SERVICES.md) |
| **Build knowledge graph** | [Graph/IMPROVED_GRAPH_BUILDER_GUIDE.md](Graph/IMPROVED_GRAPH_BUILDER_GUIDE.md) |
| **Use hybrid search** | [Features/HYBRID_SEARCH_IMPLEMENTATION_PLAN.md](Features/HYBRID_SEARCH_IMPLEMENTATION_PLAN.md) |
| **Connect Claude Desktop** | [MCP/MCP_SETUP_INSTRUCTIONS.md](MCP/MCP_SETUP_INSTRUCTIONS.md) |
| **Fix ChromaDB** | [Troubleshooting/CHROMADB_CORRUPTION_FIX.md](Troubleshooting/CHROMADB_CORRUPTION_FIX.md) |
| **Standardize vault** | [VAULT_STANDARDIZATION_GUIDE.md](VAULT_STANDARDIZATION_GUIDE.md) |

---

## 📂 Directory Structure

```
Documentation/
├── INDEX.md                    # This file
├── QUICKSTART.md               # Fast start guide
├── START_SERVICES.md           # Service startup
├── VAULT_STANDARDIZATION_GUIDE.md
├── KNOWLEDGE_GRAPH_TEST_PROMPTS.md
│
├── Features/                   # Search features
│   ├── HYBRID_SEARCH_IMPLEMENTATION_PLAN.md
│   ├── SEARCH_COMPARISON_RESULTS.md
│   ├── SEARCH_EXAMPLES.md
│   └── COMBINED_SEARCH_WORKFLOW.md
│
├── Setup/                      # Initial configuration
│   ├── NEXT_STEPS.md
│   └── COST_DECISION_GUIDE.md
│
├── Graph/                      # Knowledge graph guides
│   ├── IMPROVED_GRAPH_BUILDER_GUIDE.md
│   ├── QUALITY_IMPROVEMENTS.md
│   ├── IMPROVE_MEDICAL_QUALITY.md
│   ├── GRAPH_DATA_FLOW.md
│   ├── TRANSFER_BETWEEN_MACHINES.md
│   ├── BUILD_STATISTICS.md
│   └── IMPROVING_GRAPH_RESULTS.md
│
├── MCP/                        # Claude Desktop integration
│   ├── MCP_SETUP_INSTRUCTIONS.md
│   ├── MCP_VAULT_SEARCH_GUIDE.md
│   ├── MCP_CAPABILITIES_COMPARISON.md
│   ├── FORCE_UNIFIED_SERVER.md
│   └── TROUBLESHOOT_GRAPH_TOOLS.md
│
├── Docker/                     # Docker setup
│   ├── DOCKER_MCP_INTEGRATION.md
│   ├── DOCKER_GATEWAY_TROUBLESHOOTING.md
│   ├── DOCKER_GATEWAY_CLAUDE_DESKTOP_FIX.md
│   └── DISABLE_DOCKER_OBSIDIAN.md
│
├── Troubleshooting/            # Problem solving
│   └── CHROMADB_CORRUPTION_FIX.md
│
├── Analysis/                   # Technical analysis
│   ├── KET_RAG_ANALYSIS.md
│   ├── Improvements.md
│   └── CODE_CLEANUP_SUMMARY.md
│
└── Archive/                    # Historical docs
    └── (31 deprecated files)
```

---

**Last Updated**: 2025-11-21  
**Maintainer**: Michel
