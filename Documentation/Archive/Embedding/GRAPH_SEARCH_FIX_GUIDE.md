# 🔧 Step-by-Step: Making Graph Search Operational

## Problem Summary
- **Issue**: Graph search returns 0 chunks because cosine similarity threshold (0.2) is too strict
- **Symptom**: Query finds matching entities but no chunks pass the similarity filter
- **Root Cause**: LightRAG uses hardcoded 0.2 threshold that can't be overridden via QueryParam

---

## ✅ Solution 1: Patch LightRAG to Use Lower Threshold (Recommended)

### Step 1: Check Current LightRAG Location
```bash
cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"
docker exec obsidian-lightrag ls -la /app/LightRAG/lightrag/
```

### Step 2: Find Where Threshold is Set
The threshold is likely in the query logic. Let's check:
```bash
docker exec obsidian-lightrag grep -r "0.2" /app/LightRAG/lightrag/ --include="*.py" | head -20
```

### Step 3: Create a Patch File
We need to override the default threshold. Create a patched version:

```bash
cat > /tmp/patch_lightrag.py << 'EOF'
# This will be used to patch LightRAG in the container
EOF
```

---

## ✅ Solution 2: Use a Better Embedding Model & Re-index

This approach will create better embeddings that are more likely to pass the 0.2 threshold.

### Step 1: Backup Current Database
```bash
cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"
cp -r lightrag_db lightrag_db_backup_$(date +%Y%m%d)
```

### Step 2: Update Embedding Model to V2 (Better Quality)
```bash
# Check if nomic-embed-text-v2 is available
ollama list | grep nomic

# If not available, pull it
ollama pull nomic-embed-text-v2
```

### Step 3: Update docker-compose.yml
Edit `docker-compose.yml` to use the v2 model:

```yaml
lightrag-service:
  environment:
    - EMBED_MODEL=nomic-embed-text-v2  # Change this line
```

### Step 4: Rebuild Container
```bash
docker-compose build lightrag-service
docker-compose up -d lightrag-service
```

### Step 5: Clear Old Database
⚠️ **Warning**: This will delete all current graph data!

```bash
# STOP THE CONTAINER FIRST
docker-compose stop lightrag-service

# Delete old database
rm -rf lightrag_db/*

# Start container (will create fresh database)
docker-compose up -d lightrag-service
```

### Step 6: Re-index Vault
```bash
# Wait for service to be ready
sleep 10

# Trigger re-indexing
curl -X POST http://localhost:8001/index-vault

# Or use the UI button in Streamlit sidebar
```

### Step 7: Monitor Re-indexing
```bash
# Watch the logs
docker-compose logs -f lightrag-service | grep -E "indexing|chunks|entities"

# Check progress
docker-compose exec lightrag-service ls -lh /app/lightrag_db/
```

### Step 8: Test Graph Search
```bash
# Test the query
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query":"ESP32","mode":"naive"}' | python3 -m json.tool
```

---

## ✅ Solution 3: Modify Query Parameters (Quick Fix)

This modifies how we call LightRAG, not the threshold itself:

### Step 1: Edit lightrag_service.py
Modify the query function to use entity-based search first:

```python
async def _do_query_async(query_text, mode):
    """Helper async method for querying"""
    rag = await get_rag()
    
    # Try to search by entity name first (lower threshold)
    # This is a workaround since we can't change the 0.2 threshold
    
    # Use more chunks and let the LLM filter
    param = QueryParam(
        mode=mode,
        chunk_top_k=200,  # Get LOTS of chunks
        top_k=80,  # Get more entities
        max_total_tokens=50000  # Allow more context
    )
    result = await rag.aquery(query_text, param=param)
    return result
```

### Step 2: Rebuild
```bash
docker-compose build lightrag-service
docker-compose restart lightrag-service
```

### Step 3: Test
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query":"ESP32","mode":"naive"}' | python3 -m json.tool
```

---

## ✅ Solution 4: Work Around the Threshold (Hack)

### Create a Custom LightRAG Initialization

Add this to `lightrag_service.py` before the LightRAG initialization:

```python
# Monkey-patch the threshold
import lightrag.utils as lightrag_utils

# Save original function
_original_similarity_search = lightrag_utils.similarity_search

def patched_similarity_search(vecdb, query_embedding, top_k, threshold=0.1):
    # Lower threshold to 0.1 instead of 0.2
    return _original_similarity_search(vecdb, query_embedding, top_k, threshold=0.1)

# Apply patch
lightrag_utils.similarity_search = patched_similarity_search
```

### Then rebuild:
```bash
docker-compose build lightrag-service
docker-compose up -d lightrag-service
```

---

## 📊 Verification Steps

### 1. Check Logs for Better Results
```bash
docker-compose logs lightrag-service | grep "chunks found"
```

**Before fix**: `0 chunks found`
**After fix**: Should show chunks found

### 2. Test Various Queries
```bash
# Test 1: ESP32
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query":"ESP32","mode":"naive"}'

# Test 2: Lymphoma
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query":"lymphoma","mode":"naive"}'

# Test 3: Home automation
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Home Assistant automation","mode":"naive"}'
```

### 3. Check in Streamlit UI
```bash
# Visit the UI
open http://localhost:8501

# Try graph search modes:
# - graph-naive
# - graph-local
# - graph-global  
# - graph-hybrid
```

---

## 🎯 Recommended Approach

**For you right now, I recommend Solution 2 (Better Embedding Model):**

1. ✅ Most reliable approach
2. ✅ Doesn't require patching LightRAG
3. ✅ Will work with all query types
4. ⚠️ Takes time to re-index (~30-60 minutes)
5. ⚠️ Requires deleting old database

**Quick Test First (Solution 3):**

1. Try increasing `chunk_top_k` to 200
2. Increase `max_total_tokens` to 50000
3. See if more chunks pass through
4. If this works, you can keep it while re-indexing

**Both approaches can work together!**

---

## 📋 Complete Procedure Checklist

**Option A: Quick Fix (30 minutes)**
- [ ] Backup `lightrag_db`
- [ ] Update `lightrag_service.py` with higher parameters
- [ ] Rebuild container
- [ ] Test queries
- [ ] Document results

**Option B: Proper Fix (60-90 minutes)**
- [ ] Backup `lightrag_db`
- [ ] Pull `nomic-embed-text-v2`
- [ ] Update `docker-compose.yml`
- [ ] Clear and rebuild database
- [ ] Re-index vault (~30-60 min)
- [ ] Test all query modes
- [ ] Verify improvements

**Option C: Hybrid Approach (90 minutes)**
- [ ] Do Quick Fix first
- [ ] Verify it works
- [ ] Then do Proper Fix for long-term
- [ ] Compare results

---

## 🚀 Expected Results

**Before:**
```
INFO: Naive query: 0 chunks (chunk_top_k:100 cosine:0.2)
INFO: [naive_query] No relevant document chunks found
```

**After Fix:**
```
INFO: Naive query: 15 chunks (chunk_top_k:200 cosine:0.1)
INFO: Found relevant documents for ESP32
```

**Success Criteria:**
- ✅ Graph search returns actual context
- ✅ Query results include relevant notes
- ✅ No more "no-context" messages
- ✅ Works for ESP32, lymphoma, and other queries

---

## ⚠️ Troubleshooting

### If Re-indexing Fails:
```bash
# Check container logs
docker-compose logs lightrag-service --tail 100

# Check if Ollama is responding
curl http://host.docker.internal:11434/api/tags

# Verify vault path in docker-compose.yml
cat docker-compose.yml | grep vault
```

### If Still Getting 0 Chunks:
1. Check embedding model matches between index and query
2. Verify vault path is correct
3. Try a more specific query: "ESP32 development board Arduino"
4. Check that the database actually has chunks

### If Events Errors Persist:
The event loop errors can be ignored if queries work. They're from LightRAG's internal architecture but don't prevent functionality.

---

## 📝 Next Steps After Fix

Once graph search works:

1. **Compare Results**: Vector vs Graph search
2. **Optimize**: Tune chunk_top_k and other parameters
3. **Document**: What queries work best with graph mode
4. **Re-index**: If needed with better settings

---

## 🆘 Need Help?

If none of these solutions work:
1. Check LightRAG GitHub issues for known problems
2. Try different query modes (local, global, hybrid)
3. Consider using vector search for now
4. Report specific error messages

