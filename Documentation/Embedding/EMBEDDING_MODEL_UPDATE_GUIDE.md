# Embedding Model Update

To change the embedding model used by the embedding service:

1. Update `.env`:
   ```bash
   EMBED_MODEL=all-MiniLM-L6-v2
   ```
2. Rebuild the embedding service:
   ```bash
   docker compose build embedding-service
   docker compose up -d embedding-service
   ```
3. Reindex your vault:
   ```bash
   ./Scripts/index_with_lightrag.sh
   ```
