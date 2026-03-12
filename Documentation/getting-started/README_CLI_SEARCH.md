# CLI Vault Search

Use the `./search_vault` helper to query the embedding service directly (no MCP length limits).

## Usage

```bash
./search_vault "Home Assistant"
./search_vault "ESP32" 3
./search_vault "lymphoma treatment" 20
```

Results are saved as `search_results_<query>.txt` in the repo root.

## Troubleshooting

- Service not running:
  ```bash
  docker compose up -d
  ```
- Python dependency errors:
  ```bash
  source venv/bin/activate
  python src/indexing/query_vault.py "your query"
  ```
