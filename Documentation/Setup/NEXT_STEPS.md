# Next Steps

After Quickstart, use this checklist:

1. **Index your vault**
   ```bash
   ./Scripts/index_with_lightrag.sh
   ```
2. **Build the NetworkX graph (optional)**
   ```bash
   ./Scripts/build_knowledge_graph.sh
   ```
3. **Verify health**
   ```bash
   curl -s http://localhost:4000/api/v1/health
   ```
4. **Run a test query**
   ```bash
   curl -s -X POST http://localhost:4000/api/v1/search \
     -H "Content-Type: application/json" \
     -d '{"query":"test","mode":"vector","n_results":3}'
   ```

If you change code, rebuild the relevant service:

```bash
docker compose build graph-service
docker compose up -d graph-service
```
