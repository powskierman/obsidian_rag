# Code Cleanup & Restructuring Plan

## Issues Identified

### 1. **Root Directory Clutter** (102 files!)
- Multiple JSON files from vault processing (broken_links_*.json, tag_*.json)
- Multiple GraphRAG service implementations (5+ versions)
- Duplicate/redundant scripts
- Test result files in root

### 2. **Redundant Code**
- **5 GraphRAG implementations**: `graphrag_service.py`, `graphrag_claude_service.py`, `graphrag_openai_service.py`, `graphrag_local_service.py`, `graphrag_local_service_v2.py`
- **Multiple settings files**: 6 different YAML configs for GraphRAG
- **Duplicate Dockerfiles**: 6 Dockerfiles with overlapping functionality

### 3. **Missing Structure**
- No `src/` directory for source code
- No `data/` directory for processing results
- No `config/` consolidation
- Scripts scattered (62 in Scripts/, some in root)

---

## Proposed Structure

```
obsidian_rag/
├── src/                        # All source code
│   ├── services/               # Core services
│   │   ├── embedding_service.py
│   │   ├── graph_query_service.py
│   │   └── claude_graph_builder.py
│   ├── mcp/                    # MCP servers
│   │   ├── obsidian_rag_unified_mcp.py
│   │   └── knowledge_graph_mcp.py
│   ├── ui/                     # User interfaces
│   │   └── streamlit_ui_docker.py
│   ├── indexing/               # Indexing tools
│   │   ├── index_vault.py
│   │   └── build_knowledge_graph.py
│   └── utils/                  # Utilities
│       ├── logging_config.py
│       └── validate_claude_api_key.py
│
├── config/                     # All configuration
│   ├── docker/                 # Docker configs
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile.embedding
│   │   ├── Dockerfile.graph
│   │   └── Dockerfile.streamlit
│   ├── settings/               # Service settings
│   │   └── (consolidated YAML files)
│   └── examples/               # Example configs
│       ├── .env.example
│       └── claude_desktop_config.json
│
├── scripts/                    # Utility scripts (cleaned up)
│   ├── docker_start.sh
│   ├── fix_api_key.sh
│   └── restart_graph_service.sh
│
├── data/                       # Data & processing results
│   ├── vault_processing/       # JSON results from vault ops
│   ├── chroma_db/              # ChromaDB storage
│   └── graph_data/             # Graph storage
│
├── tests/                      # All tests
│   └── (existing test files)
│
├── docs/                       # Renamed from Documentation
│   └── (existing structure)
│
├── archive/                    # Deprecated code
│   ├── graphrag_implementations/
│   └── old_scripts/
│
├── .env                        # Environment variables
├── requirements.txt            # Dependencies
└── README.md                   # Main readme
```

---

## Cleanup Actions

### Phase 1: Archive Redundant Code
**Move to `archive/`:**
- [ ] `graphrag_service.py` (use `claude_graph_builder.py` instead)
- [ ] `graphrag_openai_service.py` (unused)
- [ ] `graphrag_local_service.py` (unused)
- [ ] `graphrag_local_service_v2.py` (unused)
- [ ] `graphrag_local_patch.py` (unused)
- [ ] Old Dockerfiles: `Dockerfile.graphrag`, `Dockerfile.graphrag-local`
- [ ] Unused settings: `settings_graphrag_*.yaml`, `settings_ollama*.yaml`

### Phase 2: Organize Data Files
**Move to `data/vault_processing/`:**
- [ ] All `broken_links_*.json` (11 files)
- [ ] All `tag_*.json` (13 files)
- [ ] All `*_results.json` files
- [ ] `moc_list*.json`, `regular_notes_list.json`
- [ ] Search result files (`search_results_*.txt`)

### Phase 3: Create Source Structure
**Create `src/` and move:**
- [ ] `src/services/`: Core service files
- [ ] `src/mcp/`: MCP server files
- [ ] `src/ui/`: Streamlit UI
- [ ] `src/indexing/`: Indexing scripts
- [ ] `src/utils/`: Utility scripts

### Phase 4: Consolidate Config
**Create `config/` and move:**
- [ ] `config/docker/`: All Dockerfiles + docker-compose.yml
- [ ] `config/settings/`: YAML settings (keep only active ones)
- [ ] `config/examples/`: .env.example files

### Phase 5: Clean Scripts
**Review `Scripts/` (62 files!):**
- [ ] Keep essential scripts in `scripts/`
- [ ] Archive deprecated scripts
- [ ] Document what each script does

### Phase 6: Update References
- [ ] Update `docker-compose.yml` paths
- [ ] Update import statements in Python files
- [ ] Update script references
- [ ] Update documentation links

---

## Benefits

1. **Clarity**: Clear separation of source, config, data
2. **Maintainability**: Easy to find and update code
3. **Professionalism**: Standard Python project structure
4. **Reduced Clutter**: 102 files → ~30 in root
5. **Better Git**: Cleaner diffs, easier to review

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking imports | Test after each move, update systematically |
| Docker build fails | Update Dockerfile paths, test builds |
| Lost functionality | Archive, don't delete; can restore |
| Time consuming | Do in phases, commit after each |

---

## Execution Plan

1. **Create backup branch**: `git checkout -b code-restructure`
2. **Phase 1-2**: Archive & organize (low risk)
3. **Test**: Ensure services still work
4. **Phase 3-4**: Restructure source (medium risk)
5. **Test**: Full integration test
6. **Phase 5-6**: Final cleanup
7. **Merge**: After thorough testing

---

**Estimated Time**: 2-3 hours  
**Recommended**: Do in one session to avoid confusion

**Ready to proceed?**
