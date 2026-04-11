# Scripts Directory

Utility scripts for managing the Obsidian RAG system. All scripts should be run from the project root unless noted otherwise.

## Directory Layout

### `indexing/`
Scripts for updating and maintaining the search index (vector DB and knowledge graph).

- `run_indexing.sh` — **Main entry point.** Runs the full indexing pipeline (vector + graph).
- `index_with_lightrag.sh` — Full LightRAG indexing workflow.
- `partial_index_lightrag.sh` — Gap-only markdown partial indexing (batch mode + logs).
- `run_lightrag_partial_index.py` — Engine behind partial indexing workflow.
- `update_vector_db.sh` — Vector-only (ChromaDB) index update.
- `update_knowledge_graph.sh` — NetworkX graph-only update.
- `verify_index_with_lightrag.sh` — Post-indexing verification.
- `reindex_missing_folders.sh` — Re-index specific missing folders.
- `reindex_remaining_md_only.sh` — Re-index remaining markdown files.
- `reindex_remaining_pdf_only.sh` — Re-index remaining PDF files.
- `safe_reindex_remaining_md.py` — Safe incremental markdown re-indexer.
- `repair_lightrag_index_metadata.py` — Repair metadata in LightRAG index.
- `clear_lightrag_pdf_queue.py` — Clear stuck PDF entries from LightRAG queue.
- `list_remaining_missing_files.sh` — Audit missing files in current index.
- `subsets/` — Scripts for indexing vault subsets.

### `movies/`
Movie-catalog ingestion and projection utilities.

- `sync_movies.py` — Canonical movie sync entry point for Apple CSV + NAS TXT -> SQLite store -> Obsidian notes.

### `setup/`
Installation, environment management, and service lifecycle.

- `startup_scripts.sh` — Initializes the environment.
- `start_obsidian_rag.sh` — Starts Docker services.
- `stop_obsidian_rag.sh` — Stops Docker services.
- `install_launch_agent.sh` — Configures macOS launch agent for auto-start.
- `start_webapp.sh` — Starts the Next.js webapp separately.
- `start_inbox_watcher.sh` — Starts the inbox file watcher.
- `wait_for_obsidian_rag_ready.sh` — Polls until all services are healthy.
- `fix_ollama_network.sh` — Fixes Ollama Docker networking issues.
- `verify_canmore_runtime_patch.sh` — Verifies Canmore runtime patch is applied.
- `verify_deep_thinking_patch.sh` — Verifies deep-thinking patch is applied.

### `deploy/`
Deployment and packaging utilities.

- `deploy_from_local_volume.sh` — Deploys changes to Docker volume.
- `package_for_airdrop.sh` / `make_airdrop_bundle.sh` — Packages the system for AirDrop transfer.
- `pull.sh` / `push.sh` — Git pull/push helpers.
- `recover_api_gateway_and_mlx.sh` — Recovery script for gateway + MLX.

### `docker/`
Docker service management helpers.

- `docker_start.sh` / `docker_stop.sh` — Start/stop all Docker services.
- `docker_rebuild.sh` — Rebuild Docker images.
- `docker_status.sh` — Show Docker service status.
- `docker_gateway_wrapper.sh` — Gateway container wrapper.
- `restart_graph_service.sh` — Restart the graph service container.

### `sync/`
Data synchronization scripts.

- `sync_local_to_icloud.sh` — Syncs local RAG data to iCloud.
- `sync_sota_to_icloud.sh` — Syncs SOTA models directory to iCloud.
- `sync_to_mac_mini.sh` — Syncs project files to Mac Mini (Canmore).

### `data_sync/`
iCloud vault data import/export.

- `export_to_icloud.sh` — Exports vault data to iCloud.
- `import_from_icloud.sh` — Imports vault data from iCloud.

### `debug/`
Diagnostics, audits, and testing tools.

- `audit_search_modes.py` — **Canonical health check.** Runs all search modes and reports pass/fail.
- `check_graph_status.py` — Verifies graph integrity.
- `inspect_graph_nodes.py` — Dumps node information.
- `inspect_graph_structure.py` — Structural graph analysis.
- `test_all_modes.py` — Functional tests for all search modes.
- `test.sh` — Runs the test suite.
- `cascading_canary_queries.py` — Canary queries for cascading mode regression.
- `run_retrieval_eval.py` — Retrieval quality evaluation.
- `evaluate_data_coverage.py` — Assesses vault coverage in the index.
- `verify_data_integrity.py` — Data integrity checks.
- `verify_networkx_db_completeness.py` — NetworkX completeness audit.
- `verify_vector_db_completeness.py` — ChromaDB completeness audit.
- `report_duplicate_entities.py` — Identifies duplicate entities in the graph.
- `lightrag_smoke_tests.sh` — LightRAG smoke test suite.

### `benchmarks/`
Performance benchmarking scripts.

- `compare_lightrag_benchmarks.py` — Compares LightRAG benchmark runs.
- `mlx_throughput_benchmark.py` — MLX provider throughput benchmark.
- `run_lightrag_ab.sh` / `run_mlx_openrouter_5note_benchmark.py` — A/B and note-level benchmarks.
- `reset_benchmark_lightrag.sh` — Resets benchmark baseline.
- `find_high_risk_notes.py` — Identifies notes most likely to cause indexing issues.

### `vault_management/`
Vault scanning and tag management.

- `obsidian_scanner.py` — Scans vault structure and metadata.
- `simple_scanner.py` — Lightweight vault scanner.
- `watching_scanner.py` — File-watching vault scanner for live updates.
- `tag_manager.py` — Tag management utilities.
- `create_subset.py` — Creates vault subsets for testing.

### `tools/`
Miscellaneous utilities.

- `script_extractor.sh` — Extracts code blocks from markdown files.
- `bash_scripts.sh` — Bash scripting helpers.
- `repo-check.sh` — Repository health check.

### `maintenance/`
Cleanup and maintenance tasks.

- `clean.sh` — Removes temporary files and caches.
- `cleanup_git_history.sh` — Git history cleanup.
- `fix_api_key.sh` / `fix_secrets_in_history.py` — Secrets remediation tools.

## Common Usage

```bash
# Start all services
docker compose up -d

# Run full indexing
./Scripts/indexing/run_indexing.sh

# Health check all search modes
python Scripts/debug/audit_search_modes.py

# Stop all services
docker compose down
```
