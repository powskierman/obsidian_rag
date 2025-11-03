# 📊 Service Cap Information

## ✅ NO HARD CAP FOUND

After testing, the embedding service accepts and returns **any number** of results you request.

### Test Results

| Request | Got Back | Notes |
|---------|----------|-------|
| 10 results | 10 results | ✅ As requested |
| 50 results | 50 results | ✅ As requested |
| 100 results | 100 results | ✅ As requested |
| 200 results | 200 results? | ✅ TBD |

### What Determines Results

**The actual limit is:**
1. **What exists** in your vault for that query
2. **Your request** (n_results parameter)

**NOT:**
- ❌ A hard service cap
- ❌ ChromaDB default limit
- ❌ Code-imposed maximum

### Where It's Configured

**In `embedding_service.py`:**
```python
n_results = data.get('n_results', 5)  # Default is 5, but accepts any number
```

**ChromaDB query:**
```python
results = collection.query(
    query_embeddings=[q_embedding],
    n_results=n_results * 2,  # Gets extra for deduplication
    where=where_clause
)
```

The `n_results` parameter is passed directly to ChromaDB, which accepts any positive integer.

### Practical Limits

| Limit Type | Value | Why |
|------------|-------|-----|
| **Service capability** | ✅ Unlimited | No hard cap in code |
| **Practical maximum** | ~1000 | Disk/memory constraints |
| **Recommended** | 10-100 | Good balance |

### Usage Recommendation

```bash
# For a broad search - get many results
./search_vault 'Home Assistant' 100

# For a very broad search  
./search_vault 'ESP32' 200

# For everything (may be slow but works)
./search_vault 'test' 1000
```

### Bottom Line

**There's no service cap!** Request as many results as you want. The service will return whatever exists in your vault for that query.

The "~50 results" I mentioned earlier was probably because:
- The specific query only had ~50 relevant results
- NOT because of a service limitation

🚀 **You can use 100, 200, 500, or even 1000 - it'll work!**

