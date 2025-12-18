# 🔍 CLI Vault Search - No Length Limits!

## ✅ Direct API Access - Bypasses MCP Length Limits

Instead of using the MCP integration (which has Claude's length limits), query your vault directly via the CLI.

---

## 🚀 Usage

```bash
# Basic search (default: 10 results)
./search_vault 'Home Assistant'

# Limit to 3 results
./search_vault 'ESP32' 3

# Get more results
./search_vault 'lymphoma treatment' 20
```

---

## 📊 Output Format

```
🔍 Searching for: 'Home Assistant'

✅ Found 3 results:

1. Home-Assistant MoC.md
   Relevance: 626.9%
   Path: Tech/Electronics/Software/Home-Assistant/...
   
   Content (256 chars):
   [Full content shown]
```

---

## 💾 Saved Results

Results are automatically saved to `search_results_<query>.txt` with full content.

---

## 🆚 Comparison

| Method | Length Limit | Output |
|--------|--------------|--------|
| **MCP (Claude Desktop)** | ❌ Claude limits | 2-3 filenames only |
| **CLI Script** | ✅ Unlimited | Full content + all results |

---

## 🔧 Troubleshooting

**"Can't connect to embedding service"**
```bash
./Scripts/docker_start.sh
```

**"No module named requests"**
```bash
# Activate venv first
source venv/bin/activate
python query_vault.py 'your query'
```

---

## 🎯 When to Use Which?

- **Use CLI** (`./search_vault`): When you want full results, no limits
- **Use MCP** (Claude Desktop): When you want quick filename lookups in conversations

The CLI gives you everything with no restrictions! 🎉

