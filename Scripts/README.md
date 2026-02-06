# Scripts Directory Structure

This directory contains utility scripts for managing the Obsidian RAG system.

## Directory Layout

### `indexing/`
Scripts related to updating and maintaining the search index (VectorDB and Knowledge Graph).
- `index_with_lightrag.sh`: Main entry point for full indexing.
- `update_vector_db.sh`: Helper for vector-only updates.
- `update_knowledge_graph.sh`: Helper for graph-only updates.

### `setup/`
Installation and environment management.
- `startup_scripts.sh`: Initializes the environment.
- `start_obsidian_rag.sh`: Starts the Docker services.
- `stop_obsidian_rag.sh`: Stops the Docker services.
- `install_launch_agent.sh`: Configures macOS launch agents.

### `deploy/`
Deployment and packaging utilities.
- `deploy_from_local_volume.sh`: Deploys changes to the Docker volume.
- `package_for_airdrop.sh`: Packages the system for transfer.

### `sync/`
Data synchronization scripts.
- `sync_local_to_icloud.sh`: Syncs local RAG data to iCloud.
- `sync_sota_to_icloud.sh`: Syncs State-of-the-Art models directory.

### `debug/`
Diagnostics and testing tools.
- `check_graph_status.py`: Verifies graph integrity.
- `inspect_graph_nodes.py`: Dumps node information.
- `test.sh`: Runs the test suite.

### `tools/`
Miscellaneous utilities.
- `script_extractor.sh`: Extracts code blocks from markdown files.

### `maintenance/`
Cleanup and maintenance tasks.
- `clean.sh`: Removes temporary files and caches.

### `archive/`
Deprecated or unused scripts.
- Contains legacy deployment scripts and old GUI helpers (`capture_gui`).

## Usage
Most scripts should be run from the project root:
```bash
./Scripts/indexing/index_with_lightrag.sh
```
