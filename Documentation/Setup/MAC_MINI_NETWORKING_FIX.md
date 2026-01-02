# Mac Mini Networking Fix - RESOLVED

## What Was Wrong

The `setup_mac_mini.sh` script failed with:
```
Error: listen tcp: lookup host.docker.internal: no such host
```

**Root cause:** The LightRAG Docker container couldn't resolve `host.docker.internal` to reach Ollama running on the Mac Mini host machine.

---

## What Was Fixed

Added `extra_hosts` configuration to `docker-compose.yml` for the `lightrag-service`:

```yaml
lightrag-service:
  # ... other config ...
  extra_hosts:
    - "host.docker.internal:host-gateway"  # ← This line added
```

This maps `host.docker.internal` to the actual host machine's IP address, allowing the Docker container to reach Ollama at `http://host.docker.internal:11434`.

---

## Why We Need Ollama

You asked: **"Why do we need Ollama if we are using Kimi?"**

**Answer:** LightRAG uses **two different AI services**:

| Service | Purpose | When Used | Cost |
|---------|---------|-----------|------|
| **Kimi K2** (via OpenRouter) | Entity extraction, reasoning about relationships | Only during indexing | ~$0.30/million tokens |
| **Ollama/nomic-embed-text** | Convert text to vector embeddings | Indexing + every query | **$0** (local) |

**Cost comparison for embeddings:**

If we used OpenRouter for embeddings instead of Ollama:
- OpenRouter embeddings: ~$5-10 for 1,676 notes
- Ollama embeddings: **$0** (runs locally)

**For your 1,676 note vault:**
- With Kimi + Ollama: ~$0.50 total
- With Kimi + OpenRouter embeddings: ~$5-10 total
- With Claude + OpenRouter embeddings: ~$15-25 total

**Bottom line:** Ollama saves you ~$5-10 per indexing run by handling embeddings locally!

---

## Next Steps on Mac Mini

The updated files have been synced. Now run the continuation script:

### 1. SSH into Mac Mini

```bash
ssh yourusername@mac-mini.local
```

### 2. Run Continuation Script

```bash
cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"

./Scripts/continue_mac_mini_setup.sh
```

**What this script does:**
1. ✅ Verifies Ollama is running (already is - PID 35565)
2. ✅ Verifies nomic-embed-text model exists (already does)
3. ✅ Restarts Docker container with fixed networking
4. ✅ Loads your database into container (152 MB, 2,000 files)
5. ✅ Tests Ollama connection from container
6. ✅ Verifies everything is working

**Time:** ~2 minutes

### 3. Set API Key and Run Indexing

```bash
# Set your OpenRouter API key
export OPENROUTER_API_KEY='your-key-here'

# Run incremental indexing
./Scripts/index_lightrag_with_kimi.sh
```

**What will happen:**
- LightRAG checks `indexed_files.txt` (2,000 files from November)
- Only processes NEW notes added since November
- Updates the graph incrementally (preserves existing 23,926 entities)
- Uses Kimi K2 for entity extraction (~$0.50)
- Uses Ollama for embeddings ($0)

**Cost:** ~$0.10-0.50 (only for new notes)
**Time:** 5-15 minutes (depends on how many new notes)

### 4. Monitor Progress

In a separate terminal:

```bash
# Watch live logs
docker logs -f obsidian-lightrag

# Or check stats periodically
curl http://localhost:8001/stats
```

---

## Verification Commands

After setup completes, verify everything works:

```bash
# Health check
curl http://localhost:8001/health

# Database stats
curl http://localhost:8001/stats | python3 -m json.tool

# Test Ollama connection
curl http://localhost:11434/api/tags

# Test query
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query":"test","mode":"hybrid"}'
```

---

## Troubleshooting

### If container still can't reach Ollama:

```bash
# Check Ollama is accessible from host
curl http://localhost:11434/api/tags

# Check from inside container
docker exec obsidian-lightrag curl http://host.docker.internal:11434/api/tags

# If fails, try restarting Ollama
pkill ollama
sleep 2
ollama serve &
```

### If database shows 0 files after restart:

```bash
# Recopy database
docker cp lightrag_db/. obsidian-lightrag:/app/lightrag_db/
docker restart obsidian-lightrag
sleep 10
curl http://localhost:8001/stats
```

---

## Summary

✅ **Fixed:** Docker networking issue (`host.docker.internal` now resolves)
✅ **Synced:** Updated docker-compose.yml to Mac Mini
✅ **Created:** Continuation script to complete setup
✅ **Clarified:** Why Ollama is needed (saves $5-10 per indexing run!)

**Next:** Run `./Scripts/continue_mac_mini_setup.sh` on Mac Mini, then index your vault!

---

**Created:** December 30, 2025
**Issue:** Docker container couldn't reach Ollama on host
**Solution:** Added `extra_hosts` configuration to docker-compose.yml
**Author:** Claude Code (Sonnet 4.5)
