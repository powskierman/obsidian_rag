# Documentation Audit & Update Plan

## Current System State (November 2024)

### Core Capabilities
1. **Deep Thinking Agentic Search** - 5 specialized agents
2. **Multi-Source Search** - Vault (vector/hybrid/graph) + Web (Tavily API  
3. **Image Embedding** - Automatic pinouts, diagrams from web searches
4. **Adaptive Planning** - Can revise research plan if gaps detected
5. **Full Attribution** - Vault `[[notes]]` + web URLs

### Required Environment Variables
```bash
ANTHROPIC_API_KEY      # Claude agents (Planner, Policy, Reflector, Synthesizer)
TAVILY_API_KEY         # Web search with images
EMBEDDING_SERVICE_URL  # http://localhost:8000
CLAUDE_GRAPH_SERVICE_URL  # http://localhost:8002
OBSIDIAN_VAULT_PATH    # /path/to/vault
```

---

## Document Review Status

### ✅ Already Updated & Accurate
- [x] **README.md** - Mentions Deep Thinking, Tavily web search, images ✅
- [x] **Documentation/INDEX.md** - Complete navigation with latest features ✅
- [x] **Documentation/architecture/DEEP_THINKING_FLOW.md** - Full system flow with diagrams ✅
- [x] **Documentation/troubleshooting/DOCKER_TROUBLESHOOTING.md** - Includes TAVILY_API_KEY  issues ✅

### ⚠️ Needs Review & Update

#### Setup Guides
- [ ] **Documentation/setup/QUICKSTART.md**
  - Check: Mentions TAVILY_API_KEY requirement?
  - Check: Explains Deep Thinking mode vs fast search?
  - Check: Shows web search example?
  
- [ ] **Documentation/setup/GETTING_STARTED.md**
  - Check: Environment variables section complete?
  - Check: Explains all search modes (vector, graph, web, deep thinking)?
  
- [ ] **Documentation/setup/GRAPHRAG_SETUP.md**
  - Check: Still relevant for current LightRAG implementation?
  - Check: Mentions integration with Deep Thinking?

- [ ] **Documentation/setup/CLAUDE_CODE_WEB_SETUP.md**
  - Check: MCP setup still works with Deep Thinking?
  - Check: Tavily integration mentioned?

#### Troubleshooting
- [ ] **Documentation/troubleshooting/API_KEY_VALIDATION_GUIDE.md**
  - Check: Includes TAVILY_API_KEY validation?
  - Check: Shows how to test web search?

- [ ] **Documentation/troubleshooting/TROUBLESHOOTING_STREAMLIT_MODEL_ERROR.md**
  - Check: Still relevant?
  - Check: Mentions Deep Thinking UI?

#### Guides  
- [ ] **Documentation/guides/README_CLI_SEARCH.md**
  - Check: Shows Deep Thinking mode CLI usage?
  - Check: Web search examples?

- [ ] **Documentation/guides/TESTING.md**
  - Check: Includes web search tests?
  - Check: Mentions `reproduce_issue.py` script?
  - Check: Shows how to test image embedding?

- [ ] **Documentation/guides/SERVICE_CAP_INFO.md**
  - Check: Lists Tavily as web search provider?
  - Check: Mentions image retrieval capability?

#### Architecture
- [ ] **Documentation/architecture/obsidian_rag_analysis.md**
  - Check: Reflects Deep Thinking architecture?
  - Check: Outdated references to old systems?

---

## Priority Updates Needed

### High Priority (User-Facing)
1. **QUICKSTART.md** - Add TAVILY_API_KEY to prerequisites
2. **API_KEY_VALIDATION_GUIDE.md** - Add Tavily validation section
3. **TESTING.md** - Update with web search + image tests

### Medium Priority (Developer-Facing)
4. **SERVICE_CAP_INFO.md** - Update with Tavily capabilities
5. **GETTING_STARTED.md** - Expand search modes explanation
6. **TESTING.md** - Reference `reproduce_issue.py`

### Low Priority (Optional)
7. **obsidian_rag_analysis.md** - Full rewrite for Deep Thinking (can wait)
8. **README_CLI_SEARCH.md** - Add Deep Thinking CLI examples (if exists)

---

## Next Steps

1. Review each document systematically
2. Update content to reflect current state
3. Add missing information (TAVILY_API_KEY, images, web search)
4. Remove outdated references
5. Verify all links and paths are correct
6. Create updated artifact summaries

---

## Template for Updates

When updating a document, ensure it includes:

### Setup Docs Should Mention
- [ ] TAVILY_API_KEY in prerequisites
- [ ] Deep Thinking mode explanation
- [ ] When to use web search
- [ ] Image embedding capability

### Troubleshooting Docs Should Include
- [ ] Web search not working → Check TAVILY_API_KEY
- [ ] Images not appearing → Rebuild Docker
- [ ] 0 documents found → Keyword vs query issue

### Guide Docs Should Cover
- [ ] How to use Deep Thinking mode
- [ ] Example queries that trigger web search
- [ ] How to verify web search is working
- [ ] Testing procedures for new features
