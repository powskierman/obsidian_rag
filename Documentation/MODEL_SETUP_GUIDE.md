# 🤖 Model Configuration Guide

## ✅ qwen2.5-coder:14b Added to UI

The model `qwen2.5-coder:14b` has been added to your Streamlit UI dropdown menu.

## 🚀 How to Use the New Model

### Option 1: Use in Streamlit UI (No Rebuild Needed)

1. **Start your services** (if not already running):
   ```bash
   ./Scripts/docker_start.sh
   ```

2. **Access the UI**: http://localhost:8501

3. **Select the model**: In the sidebar under "⚙️ Settings", select `qwen2.5-coder:14b` from the dropdown

4. **Start querying**: The model will be used for your queries!

**Note**: This uses the model for query generation only. For indexing with LightRAG, use Option 2 below.

---

### Option 2: Use for LightRAG Indexing

To use `qwen2.5-coder:14b` for building your knowledge graph:

1. **Set the environment variable**:
   ```bash
   export LLM_MODEL=qwen2.5-coder:14b
   ```

2. **Rebuild the containers**:
   ```bash
   ./Scripts/docker_rebuild.sh
   ```

3. **Index your vault**:
   ```bash
   ./Scripts/index_with_lightrag.sh
   ```

---

## 📊 Model Comparison

| Model | Size | RAM | Speed | Quality | Best For |
|-------|------|-----|-------|---------|----------|
| **qwen2.5-coder:14b** | 14B | 8-10GB | ⚡⚡⚡ Fast | ⭐⭐⭐⭐ Excellent | **Best balance** |
| deepseek-r1:14b | 14B | 8-10GB | ⚡⚡⚡ Fast | ⭐⭐⭐⭐ Excellent | Reasoning tasks |
| llama3.2:3b | 3B | 5GB | ⚡⚡⚡ Very Fast | ⭐⭐⭐ Good | Quick testing |

---

## ⚙️ Model Configuration

### For Streamlit UI (Query Generation)
- **Location**: `streamlit_ui_docker.py` line 99
- **Models available**: Listed in dropdown menu
- **No rebuild needed**: Changes take effect immediately

### For LightRAG Indexing
- **Location**: `docker-compose.yml` line 39
- **Default**: `llama3.2:3b`
- **To change**: Set `LLM_MODEL` environment variable

---

## 🎯 Recommended Usage

### For Your Setup (36GB RAM):

**Indexing (Building Knowledge Graph)**:
- ✅ Use `qwen2.5-coder:14b` - Great quality, reasonable speed (2-3 hours)
- Or use `llama3.2:3b` for fastest indexing (1-2 hours)

**Query Generation**:
- ✅ Use `qwen2.5-coder:14b` - Best balance of speed & quality
- Or use `qwen2.5-coder:32b` for maximum quality (slower, more RAM)

---

## 🔧 Environment Variables

### Quick Model Switch

```bash
# For indexing with qwen2.5-coder:14b
export LLM_MODEL=qwen2.5-coder:14b
./Scripts/docker_rebuild.sh

# For faster indexing
export LLM_MODEL=llama3.2:3b
./Scripts/docker_rebuild.sh

# For maximum quality
export LLM_MODEL=qwen2.5-coder:32b
./Scripts/docker_rebuild.sh
```

---

## 📝 Next Steps

1. **Try the model in the UI** (no rebuild needed):
   - Open http://localhost:8501
   - Select `qwen2.5-coder:14b` from dropdown
   - Ask a question!

2. **Rebuild for indexing** (optional):
   ```bash
   export LLM_MODEL=qwen2.5-coder:14b
   ./Scripts/docker_rebuild.sh
   ./Scripts/index_with_lightrag.sh
   ```

---

## ✅ Verification

Check that Ollama has the model:
```bash
ollama list | grep qwen2.5-coder:14b
```

Should show:
```
qwen2.5-coder:14b    <timestamp>   <size>
```

---

## 🆘 Troubleshooting

**Model not showing in UI?**
- Verify: `ollama list | grep qwen2.5-coder:14b`
- Download: `ollama pull qwen2.5-coder:14b`

**Container using wrong model?**
- Check: `docker-compose exec lightrag-service env | grep LLM_MODEL`
- Rebuild: `./Scripts/docker_rebuild.sh`

**Out of memory?**
- Switch to smaller model: `llama3.2:3b`
- Or use 14b which uses less RAM than 32b

