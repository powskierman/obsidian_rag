# Default LLM Provider Configuration Fix

## Issue Identified

The `obsidian_unified_query` tool was timing out consistently because the default LLM provider was **hardcoded to `ollama`** in the API gateway code.

**Root Cause**: Line 2784 in `src/services/api_gateway.py`:
```python
llm_provider: str = "ollama"  # Hardcoded!
```

Ollama (local model inference) is significantly slower than cloud providers like OpenRouter, ChatGPT, or Gemini, especially for complex cascading queries that require multi-stage synthesis.

---

## Fix Applied

### 1. Made Default Provider Configurable via Environment Variable

**Changed**: `src/services/api_gateway.py:2784`

**Before**:
```python
llm_provider: str = "ollama"
```

**After**:
```python
llm_provider: str = _get_env_value(
    "DEFAULT_LLM_PROVIDER",
    _get_env_value("CASCADING_LLM_PROVIDER", "openrouter")
)
```

**Priority**:
1. `DEFAULT_LLM_PROVIDER` (if set in .env)
2. `CASCADING_LLM_PROVIDER` (if set in .env)
3. `"openrouter"` (default fallback - much faster than Ollama)

---

### 2. Updated `.env` Configuration

**Added** (lines 40-43):
```bash
# Default LLM Provider for cascading/unified queries
# Options: openrouter (fast, recommended), ollama (slow, local), chatgpt, gemini, claude
DEFAULT_LLM_PROVIDER=openrouter
CASCADING_LLM_PROVIDER=openrouter
```

**Why OpenRouter?**
- Fast cloud inference
- Free tier models available (nvidia/nemotron-3-super-120b-a12b:free)
- Already configured: `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` are set
- Timeout already optimized: `OPENROUTER_TIMEOUT=300` (5 minutes)

---

### 3. Updated `docker-compose.yml`

**Added** to `api-gateway` service environment (lines 220-221):
```yaml
- DEFAULT_LLM_PROVIDER=${DEFAULT_LLM_PROVIDER:-openrouter}
- CASCADING_LLM_PROVIDER=${CASCADING_LLM_PROVIDER:-openrouter}
```

This ensures the Docker container picks up the environment variable from `.env`.

---

## Testing the Fix

### Step 1: Restart the API Gateway Container

```bash
docker-compose restart api-gateway
```

Wait for the container to be healthy:
```bash
docker ps | grep api-gateway
# Should show (healthy) status
```

### Step 2: Test via MCP (Optional - if you want to test from Claude Desktop)

The MCP server doesn't need restart if you're testing directly against the API gateway. But if you want to test through Claude Desktop's MCP:

1. Quit Claude Desktop
2. Restart Claude Desktop
3. Ask Claude to run: `obsidian_unified_query("What is the progression timeline of my lymphoma scans?")`

### Step 3: Direct API Test (Recommended First)

You can test the API gateway directly without going through Claude Desktop:

```bash
curl -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the key findings from my PET scans?",
    "mode": "cascading",
    "max_results": 5
  }'
```

**Expected behavior**:
- Should complete in **under 60 seconds** (previously timing out)
- Response will include synthesized answer with sources
- Should use OpenRouter model (check logs for confirmation)

### Step 4: Verify Provider in Logs

```bash
docker logs obsidian-api-gateway --tail 100 | grep -i "provider\|openrouter"
```

You should see log entries indicating OpenRouter is being used.

---

## Performance Comparison

| Provider | Expected Query Time | Notes |
|----------|---------------------|-------|
| **openrouter** | 15-45 seconds | Fast cloud inference, recommended |
| **chatgpt** | 10-30 seconds | Fast, requires OpenAI API key |
| **gemini** | 15-40 seconds | Fast, requires Google API key |
| **ollama** | 60-120+ seconds | Slow local inference, often times out |
| **lmstudio** | 45-90 seconds | Moderate local inference |

---

## Alternative Providers

If you want to use a different provider, update `.env`:

### Option 1: Use ChatGPT (OpenAI)
```bash
DEFAULT_LLM_PROVIDER=chatgpt
# Already configured: OPENAI_API_KEY and OPENAI_MODEL
```

### Option 2: Use Gemini (Google)
```bash
DEFAULT_LLM_PROVIDER=gemini
# Already configured: GEMINI_API_KEY
```

### Option 3: Use Claude (Anthropic)
```bash
DEFAULT_LLM_PROVIDER=claude
# Already configured: ANTHROPIC_API_KEY
```

### Option 4: Keep Ollama (Local, Slow)
```bash
DEFAULT_LLM_PROVIDER=ollama
# Already configured: OLLAMA_HOST and OLLAMA_MODEL
# Note: Will be slower, may timeout on complex queries
```

After changing, restart the api-gateway:
```bash
docker-compose restart api-gateway
```

---

## Timeout Configuration

If you still experience timeouts (unlikely with OpenRouter), you can increase the MCP timeout:

### In Claude Desktop MCP Config:
```json
{
  "env": {
    "MCP_GATEWAY_QUERY_TIMEOUT": "300",  // 5 minutes instead of default 2 minutes
    ...
  }
}
```

### In docker-compose.yml for webapp:
Already configured (lines in docker-compose.yml):
```yaml
- GATEWAY_QUERY_TIMEOUT_MS_CASCADING=300000  # 5 minutes for cascading mode
```

---

## Additional Fix: Query Normalizer Timeout

After testing, we discovered the **expansion stage** (query normalization) was timing out with a 4-second default timeout.

**Added to `.env`**:
```bash
# Query Normalizer (Expansion Stage) Timeout
QUERY_NORMALIZER_TIMEOUT_SECONDS=15  # Increased from 4 to 15 seconds
```

**Added to `docker-compose.yml`** (api-gateway environment):
```yaml
- QUERY_NORMALIZER_TIMEOUT_SECONDS=${QUERY_NORMALIZER_TIMEOUT_SECONDS:-15}
```

This allows the expansion stage to complete without timing out when using OpenRouter (which takes 5-10 seconds to respond for query enhancement).

---

## Verification Checklist

After restarting `api-gateway`:

- [ ] Container is healthy: `docker ps | grep api-gateway`
- [ ] Direct API test completes without timeout
- [ ] **No expansion stage failures** in response diagnostics
- [ ] MCP `obsidian_unified_query` works from Claude Desktop
- [ ] Response time is under 60 seconds (typically 15-45s with OpenRouter)
- [ ] Logs show OpenRouter provider being used

---

## Summary

**What changed**:
- ❌ Before: Hardcoded to `ollama` → slow, frequent timeouts
- ✅ After: Configurable via `.env` → defaults to `openrouter` → fast, reliable

**Files modified**:
1. `src/services/api_gateway.py` - Made provider configurable
2. `.env` - Added `DEFAULT_LLM_PROVIDER=openrouter`
3. `docker-compose.yml` - Passed env var to api-gateway container

**Expected result**:
- `obsidian_unified_query` should now complete in 15-45 seconds instead of timing out
- All other MCP tools continue working as before
- No changes needed to MCP client configuration (but container restart required)

---

## Rollback (if needed)

If you want to revert to Ollama (not recommended for performance):

1. Edit `.env`:
   ```bash
   DEFAULT_LLM_PROVIDER=ollama
   ```

2. Restart api-gateway:
   ```bash
   docker-compose restart api-gateway
   ```

Or simply remove the environment variables to use the code's default (now `openrouter` instead of `ollama`).
