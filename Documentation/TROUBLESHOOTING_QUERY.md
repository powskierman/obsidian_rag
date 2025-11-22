# 🔧 Query Troubleshooting Guide

## ❓ Problem: "I don't have any specific notes on [topic]" Despite Having Notes

### Quick Checks

1. **Check Service Status**:
   ```bash
   ./Scripts/docker_status.sh
   ```
   Should show: ✅ Embedding, ✅ LightRAG, ✅ Streamlit

2. **Check Database**:
   ```bash
   curl http://localhost:8000/stats
   ```
   Should show: `total_documents: 6963` or similar

3. **Check Search Mode**:
   - Make sure you're using "vector" mode in the UI
   - Graph modes require indexing first

### Common Causes

#### 1. Empty Document Lists
The search might return empty results even though documents exist.

**Fix Applied**: Updated `streamlit_ui_docker.py` to:
- Check for empty document lists
- Handle negative distance values properly  
- Show proper warnings when no documents found

#### 2. Distance Calculation Issue
Negative distances were causing relevance scores > 100%.

**Fix Applied**: 
- Changed relevance calculation to handle negative distances
- Clamped relevance between 0-100%

#### 3. Wrong Search Mode
Using graph modes without indexing.

**Solution**: Use "vector" mode first, or index with:
```bash
./Scripts/index_with_lightrag.sh
```

---

## 🧪 Test Your Setup

### Test 1: Check Embedding Service
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"lymphoma","n_results":3}'
```

Should return 3 documents.

### Test 2: Check Ollama
```bash
curl http://localhost:11434/api/tags
```

Should list your models.

### Test 3: Check Models
```bash
ollama list
```

Should show at least:
- qwen2.5-coder:14b
- llama3.2:3b  
- deepseek-r1:14b

---

## 🔄 Rebuild After Changes

If you made changes to the code:

```bash
./Scripts/docker_rebuild.sh
```

This will:
- Rebuild the containers with updated code
- Restart all services
- Apply your changes

---

## 💡 Tips

1. **Always use "vector" mode** for initial testing
2. **Check the sidebar** to see document count (should be 6963+)
3. **Try different keywords** if search fails
4. **Use more sources** (increase slider in sidebar)
5. **Check logs** if issues persist:
   ```bash
   docker-compose logs streamlit-ui
   ```

---

## 📊 Current Configuration

- **Database**: 6,963 chunks from 1,582 notes ✅
- **Services**: All running ✅
- **Models**: Available ✅
- **Default Model**: qwen2.5-coder:14b
- **Default Mode**: vector

---

## 🆘 Still Having Issues?

1. **View logs**: 
   ```bash
   docker-compose logs -f streamlit-ui
   ```

2. **Restart services**:
   ```bash
   ./Scripts/docker_stop.sh
   ./Scripts/docker_start.sh
   ```

3. **Check vault path** in `docker-compose.yml`:
   ```yaml
   - "/Users/michel/.../Documents/Michel:/app/vault:ro"
   ```

4. **Verify files are in vault**:
   ```bash
   ls "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/"
   ```

---

## ✅ Expected Behavior

When you search for "lymphoma":

1. ✅ Vector search finds documents
2. ✅ Shows "🔍 Searching vector database..."
3. ✅ Shows "💭 Thinking with qwen2.5-coder:14b..."
4. ✅ Returns answer with source citations
5. ✅ Click "📚 Sources Used" to see which notes were used

---

If you're still seeing "I don't have notes on..." after these fixes, the issue is likely with the LLM response formatting, not the search itself.

