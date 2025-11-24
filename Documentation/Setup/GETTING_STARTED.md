# Getting Started with Obsidian RAG

## For First-Time Users

Just want to get it working? Follow these 3 steps:

### Step 1: Run Setup (1 minute)
```bash
./setup.sh
```

### Step 2: Add Your API Key (2 minutes)
```bash
nano .env.local
```
Replace `sk-ant-your-api-key-here` with your actual [Anthropic API key](https://console.anthropic.com/account/keys)

Save and exit (Ctrl+X, then Y)

### Step 3: Start Services (1 minute)

**Terminal 1 - Start Ollama:**
```bash
ollama serve
```

**Terminal 2 - Start Obsidian RAG:**
```bash
./run.sh
```

That's it! Open your browser to: **http://localhost:8501**

---

## What Just Happened?

- ✅ Python dependencies installed
- ✅ Environment configured
- ✅ Embedding service started (port 8000)
- ✅ Web UI started (port 8501)

## First Run

1. Paste your Obsidian vault path in the UI
2. Click "📑 Index Vault"
3. Wait 5-15 minutes (it's processing your notes)
4. Start asking questions!

---

## Not Working?

### "Ollama not found"
- Download from: https://ollama.ai
- Run in terminal: `ollama serve`

### "API key error"
- Get key from: https://console.anthropic.com/account/keys
- Edit `.env.local` with your actual key
- Save and restart `./run.sh`

### "Port 8501 already in use"
```bash
# Kill process on that port (Mac/Linux)
lsof -i :8501 | grep LISTEN | awk '{print $2}' | xargs kill -9
# Then try again: ./run.sh
```

---

## Next: Full Documentation

Once you're up and running, check out:
- [QUICKSTART.md](./QUICKSTART.md) - More detailed guide
- [Documentation/README.md](./Documentation/README.md) - Full docs
- [Documentation/TROUBLESHOOTING.md](./Documentation/TROUBLESHOOTING.md) - Problem solving

---

## System Requirements

- **Mac/Linux/Windows** ✅
- **Python 3.10+** - Check: `python3 --version`
- **8GB RAM minimum** (16GB recommended)
- **50GB disk space** (grows with notes)

## Questions?

Check these files for help:
- Troubleshooting issues? → [TROUBLESHOOTING.md](./Documentation/TROUBLESHOOTING.md)
- How does it work? → [README.md](./Documentation/README.md)
- More features? → [QUICKSTART.md](./QUICKSTART.md)

---

**Enjoy your local knowledge base! 🧠**
