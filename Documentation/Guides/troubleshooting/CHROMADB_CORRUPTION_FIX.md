# ChromaDB Corruption Fix

Symptoms: embedding service fails to start or queries crash.

## Fix

1. Stop services:
   ```bash
   docker compose down
   ```
2. Backup and remove the DB:
   ```bash
   mv chroma_db chroma_db_backup_$(date +%Y%m%d)
   ```
3. Restart services:
   ```bash
   docker compose up -d
   ```
4. Reindex:
   ```bash
   ./Scripts/index_with_lightrag.sh
   ```
