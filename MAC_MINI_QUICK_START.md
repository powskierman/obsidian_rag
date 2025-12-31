# Mac Mini Quick Start Guide

## 🎯 Goal
Run LightRAG indexing on your Mac Mini so your main Mac stays free for other work.

---

## 📋 Pre-Flight Checklist

**On Your Current Mac** (Already Done ✅):
- ✅ Backed up database (2 copies - local + max volume)
- ✅ All files saved to iCloud
- ✅ Setup script created and ready

**Optional - Stop services on current Mac:**
```bash
cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/config/docker"
docker compose down
```

---

## 🖥️ On Your Mac Mini

### **Step 1: Wait for iCloud Sync**

Check that the project has synced from iCloud:

```bash
cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"
ls -la
```

**You should see:**
- `lightrag_db/` directory (~152 MB)
- `Scripts/` directory with setup script
- `src/` directory with source code
- `config/docker/` with docker-compose.yml

**If missing:** Wait for iCloud sync (check System Settings → iCloud → iCloud Drive)

---

### **Step 2: Run Automated Setup**

This single script does everything:

```bash
cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"

./Scripts/setup_mac_mini.sh
```

**What it does:**
1. ✅ Checks Docker is installed and running
2. ✅ Installs Ollama (if needed)
3. ✅ Pulls embedding model (nomic-embed-text)
4. ✅ Builds Docker image (5-10 min)
5. ✅ Starts LightRAG service
6. ✅ Loads your database into container
7. ✅ Verifies everything works

**Time:** 15-20 minutes (mostly automated)

---

### **Step 3: Set API Key**

```bash
export OPENROUTER_API_KEY='your-key-here'
```

Or add to `.env` file for persistence:
```bash
echo "OPENROUTER_API_KEY=your-key-here" >> .env
```

Get your key at: https://openrouter.ai/keys

---

### **Step 4: Run Indexing**

```bash
cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag"

./Scripts/index_lightrag_with_kimi.sh
```

**What happens:**
- Compares your vault against indexed files (2,000 from November)
- Only processes NEW notes added since November
- Updates entities and relationships incrementally
- **Cost:** ~$0.10-0.20 (only new notes)
- **Time:** 5-15 minutes (depends on new note count)

---

### **Step 5: Monitor Progress**

In a separate terminal:

```bash
# Watch live logs
docker logs -f obsidian-lightrag

# Or check stats periodically
curl http://localhost:8001/stats
```

---

## 🔧 If Setup Script Fails

### **Docker not installed:**
```bash
# Download and install Docker Desktop
open https://www.docker.com/products/docker-desktop/
```

### **Ollama not installed:**
```bash
# Install via Homebrew
brew install ollama

# Or download from:
open https://ollama.ai/download
```

### **iCloud not synced:**
```bash
# Check iCloud status
# System Settings → Apple ID → iCloud → iCloud Drive

# Force sync (optional)
killall bird
```

---

## 📊 Verification Commands

**Check service health:**
```bash
curl http://localhost:8001/health
```

**Check database stats:**
```bash
curl http://localhost:8001/stats | python3 -m json.tool
```

**Check running containers:**
```bash
docker ps | grep lightrag
```

**Check Ollama:**
```bash
curl http://localhost:11434/api/tags
```

---

## 🌐 Access from Main Mac (Optional)

While indexing runs on Mac Mini, you can check status remotely:

### **SSH Access:**
```bash
# From your main Mac
ssh yourusername@mac-mini.local

# Then run commands
docker logs obsidian-lightrag
curl http://localhost:8001/stats
```

### **Web Access:**
```bash
# On Mac Mini, get IP:
ifconfig | grep "inet " | grep -v 127.0.0.1

# From main Mac browser:
http://[mac-mini-ip]:8001/health
http://[mac-mini-ip]:8501  # Streamlit UI
```

---

## ⏸️ After Indexing

### **Keep Services Running:**
If you want to query the graph later:
```bash
# Services stay running
# Access at http://localhost:8001
```

### **Stop Services:**
If you're done and want to free resources:
```bash
cd "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/config/docker"
docker compose down
```

### **Database Auto-Syncs:**
The updated `lightrag_db/` will sync back to iCloud and appear on your main Mac automatically!

---

## 🚨 Troubleshooting

### **"Service not healthy"**
```bash
# Check logs for errors
docker logs obsidian-lightrag

# Restart service
docker restart obsidian-lightrag
sleep 10
```

### **"Database shows 0 files"**
```bash
# Recopy database to container
docker cp lightrag_db/. obsidian-lightrag:/app/lightrag_db/
docker restart obsidian-lightrag
```

### **"Ollama connection failed"**
```bash
# Restart Ollama
pkill ollama
ollama serve &
sleep 5

# Verify
curl http://localhost:11434/api/tags
```

### **"Out of memory"**
```bash
# Increase Docker memory
# Docker Desktop → Settings → Resources → Memory
# Recommended: 8 GB
```

---

## 📝 Quick Reference

| Command | Purpose |
|---------|---------|
| `./Scripts/setup_mac_mini.sh` | One-time setup |
| `./Scripts/index_lightrag_with_kimi.sh` | Run indexing |
| `docker logs -f obsidian-lightrag` | Watch progress |
| `curl localhost:8001/stats` | Check database |
| `docker compose down` | Stop services |
| `docker compose up -d` | Restart services |

---

## 🎯 Expected Timeline

| Task | Time |
|------|------|
| iCloud sync | 5-10 min |
| Setup script | 15-20 min |
| Indexing | 5-15 min |
| **Total** | **25-45 min** |

Most of this is automated - you can walk away after starting!

---

## ✅ Success Indicators

**Setup Complete:**
```json
{
  "status": "healthy",
  "service": "lightrag",
  "database_exists": true,
  "total_files": 13
}
```

**Indexing Complete:**
```
✅ Indexing Complete!
⏱️  Time: 12.3 minutes
📊 Files indexed: 1,847
```

---

## 🔄 Switching Back to Main Mac

After indexing completes:

1. **Database syncs back automatically** via iCloud
2. **Stop Mac Mini services** (optional): `docker compose down`
3. **On main Mac, restart services:**
   ```bash
   cd config/docker
   docker compose up -d lightrag-service

   # Copy updated database
   docker cp lightrag_db/. obsidian-lightrag:/app/lightrag_db/
   docker restart obsidian-lightrag
   ```

---

## 📞 Need Help?

**Check logs:**
```bash
docker logs obsidian-lightrag
```

**Verify each component:**
```bash
docker ps                           # Container running?
curl localhost:11434/api/tags      # Ollama working?
curl localhost:8001/health          # Service healthy?
ls -lh lightrag_db/                # Database present?
```

---

**Created:** December 30, 2025
**Purpose:** Seamless Mac Mini setup for LightRAG indexing
**Author:** Claude Code (Sonnet 4.5)
