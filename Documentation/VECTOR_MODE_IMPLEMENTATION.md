# Vector Mode with LLM Synthesis - Backend Implementation

## Overview

Vector mode with LLM synthesis has been implemented in the backend `graph_query_service.py` to ensure consistent behavior across both Streamlit and Next.js frontends. This completes the backend-first architecture for all three search modes: **vector**, **graph**, and **hybrid**.

## Architecture

### Backend-First Design

All search modes and LLM integration now live in `graph_query_service.py`:
- **Vector Mode**: Vector search + LLM synthesis
- **Graph Mode**: Knowledge graph reasoning
- **Hybrid Mode**: Graph + vector search + entity extraction

**Benefits**:
- Both UIs get identical functionality
- Single source of truth for LLM integration
- Centralized prompt management
- Consistent results across all clients

## Implementation

### Backend: graph_query_service.py

**New `/query` endpoint with vector mode**:
```json
{
  "query": "What are mitochondria?",
  "mode": "vector" | "graph" | "hybrid",
  "llm_provider": "ollama" | "claude" | "gemini" | "gpt-oss",
  "model": "llama2",
  "temperature": 0.7,
  "system_prompt": "Custom instructions...",
  "n_results": 10,
  "max_entities": 20,
  "web_search": false
}
```

### Vector Mode Flow

1. **Vector Search**: Calls embedding service to get relevant document chunks
2. **Build Context**: Formats documents into context string with source citations
3. **Build System Prompt**: Uses custom prompt if provided, otherwise uses default
4. **Call LLM**: Routes to selected provider (Ollama, Claude, Gemini, GPT-OSS)
5. **Return Response**: Includes answer, sources, LLM provider, and model used

### LLM Provider Integration

The `call_llm()` function supports four providers:

#### Ollama
```python
ollama_response = requests.post(
    f'{OLLAMA_HOST}/api/generate',
    json={
        'model': model,
        'prompt': full_prompt,
        'stream': False,
        'options': {'temperature': temperature}
    }
)
```

#### Claude (Anthropic)
```python
from anthropic import Anthropic
client = Anthropic(api_key=ANTHROPIC_API_KEY)
response = client.messages.create(
    model=model,
    max_tokens=4000,
    temperature=temperature,
    system=system_prompt,
    messages=[{"role": "user", "content": user_query}]
)
```

#### Gemini (Google)
```python
gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
gemini_response = requests.post(
    gemini_url,
    headers={"x-goog-api-key": GEMINI_API_KEY},
    json={
        "contents": [{"role": "user", "parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 4000}
    }
)
```

#### GPT-OSS (OpenAI-compatible)
```python
llm_response = requests.post(
    f'{GPT_OSS_HOST}/v1/chat/completions',
    json={
        'model': model,
        'messages': [{'role': 'system', 'content': full_prompt}],
        'max_tokens': 4096,
        'temperature': temperature
    }
)
```

### Default Models

When no model is specified, the backend selects defaults:
- **ollama**: `llama2`
- **claude**: `claude-sonnet-4-5-20250929`
- **gemini**: `gemini-3-pro-preview`
- **gpt-oss**: `gpt-4`

### Default System Prompt

If no custom prompt is provided, the backend uses:
```python
system_prompt = f"""You are an AI assistant helping analyze an Obsidian knowledge base.

Context from notes:
{context_text}

Provide a thorough, accurate answer that:
- References specific information from the context
- Is medically accurate when discussing health topics
- Includes technical details when relevant
- Cites which sources you used
- If the context doesn't contain relevant information, say so clearly"""
```

### Response Format

**Vector mode response**:
```json
{
  "answer": "Mitochondria are organelles found in the cells of most eukaryotic organisms...",
  "query": "What are mitochondria?",
  "mode": "vector",
  "llm_provider": "ollama",
  "model": "llama2",
  "sources": [
    {
      "filename": "Power, Sex, Suicide.md",
      "filepath": "/app/vault/Books/Books/Power, Sex, Suicide.md",
      "relevance": 45.13,
      "snippet": "the greatest mutational health hazard in the population is fertile old men..."
    }
  ]
}
```

## Configuration

### Docker Dependencies

**Dockerfile.graph** now includes `anthropic` package:
```dockerfile
RUN pip install --no-cache-dir \
    openai \
    flask \
    flask-cors \
    networkx \
    tqdm \
    requests \
    tavily-python \
    anthropic
```

### Environment Variables

**docker-compose.yml** graph-service now includes:
```yaml
environment:
  - EMBEDDING_SERVICE_URL=http://embedding-service:8000
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
  - GEMINI_API_KEY=${GEMINI_API_KEY:-}
  - OLLAMA_HOST=${OLLAMA_HOST:-http://host.docker.internal:11434}
  - GPT_OSS_HOST=${GPT_OSS_HOST:-http://host.docker.internal:12434/engines/llama.cpp}
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## Frontend Integration

### Next.js API Client

**Updated `api.graphQuery()` signature**:
```typescript
graphQuery: async (
  query: string,
  mode: 'vector' | 'graph' | 'hybrid' = 'graph',
  n_results = 10,
  llm_provider = 'ollama',
  model = '',
  temperature = 0.7,
  system_prompt = ''
): Promise<{
  answer: string;
  sources?: SearchResult[];
  extracted_entities?: string[];
  llm_provider?: string;
  model?: string;
}>
```

### Next.js Usage

**Vector mode with custom prompt**:
```typescript
const result = await api.graphQuery(
  userMsg,
  'vector',
  settings.sources,      // n_results
  llmProvider,           // 'ollama', 'claude', 'gemini'
  settings.model,        // model name
  settings.temperature,  // temperature
  systemPrompt           // custom system instructions
);

const answer = result.answer;
const sources = result.sources || [];
```

**Hybrid mode**:
```typescript
const result = await api.graphQuery(userMsg, 'hybrid', settings.sources);
const answer = result.answer;
const sources = result.sources || [];
```

**Graph mode**:
```typescript
const result = await api.graphQuery(userMsg, 'graph');
const answer = result.answer;
```

### Streamlit Integration

The Streamlit app can now use the same backend endpoint instead of client-side LLM calls:

**Before** (client-side):
```python
# 100+ lines of LLM integration code in Streamlit UI
```

**After** (backend call):
```python
response = requests.post(
    f'{CLAUDE_GRAPH_SERVICE_URL}/query',
    json={
        'query': prompt,
        'mode': 'vector',
        'llm_provider': active_provider,
        'model': model_option,
        'temperature': temperature,
        'system_prompt': custom_prompt,
        'n_results': num_sources
    }
)

result = response.json()
answer = result['answer']
sources = result.get('sources', [])
```

## Testing

### Test Vector Mode

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are mitochondria?",
    "mode": "vector",
    "llm_provider": "ollama",
    "model": "llama2",
    "n_results": 3
  }' | python3 -m json.tool
```

**Expected Output**:
```json
{
  "answer": "Mitochondria are organelles found in the cells...",
  "llm_provider": "ollama",
  "model": "llama2",
  "mode": "vector",
  "query": "What are mitochondria?",
  "sources": [...]
}
```

### Test with Custom System Prompt

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are mitochondria?",
    "mode": "vector",
    "llm_provider": "ollama",
    "model": "llama2",
    "system_prompt": "You are a biology teacher. Explain concepts simply.",
    "n_results": 5
  }' | python3 -m json.tool
```

### Test with Claude

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are mitochondria?",
    "mode": "vector",
    "llm_provider": "claude",
    "model": "claude-sonnet-4-5-20250929",
    "temperature": 0.5,
    "n_results": 5
  }' | python3 -m json.tool
```

### Test with Gemini

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are mitochondria?",
    "mode": "vector",
    "llm_provider": "gemini",
    "model": "gemini-3-pro-preview",
    "n_results": 5
  }' | python3 -m json.tool
```

## Benefits

### 1. **Consistency**
Both Streamlit and Next.js apps get identical LLM responses since they use the same backend.

### 2. **Maintainability**
LLM integration logic lives in one place. Bug fixes and improvements benefit both UIs automatically.

### 3. **Custom Prompts**
Users can customize system prompts via the UI, and they're actually used by the backend.

### 4. **Multi-Provider Support**
Easy to switch between Ollama (local), Claude (API), Gemini (API), or GPT-OSS (OpenAI-compatible).

### 5. **Performance**
Internal Docker network communication is faster than client → LLM API calls from the browser.

### 6. **Simplified Frontend**
Next.js app has no LLM integration code - just simple API calls.

## Comparison with Previous Architecture

### Before

**Streamlit**: Client-side LLM calls
- ✅ Working vector search with Ollama/Claude/Gemini
- ❌ 100+ lines of LLM integration code in UI
- ❌ Complex error handling
- ❌ Different behavior from Next.js

**Next.js**: No LLM integration
- ❌ Vector search returned placeholder text
- ❌ System prompt UI existed but wasn't used
- ❌ No actual LLM synthesis

### After

**Backend (`graph_query_service.py`)**: Unified LLM integration
- ✅ Vector, graph, and hybrid modes
- ✅ Support for 4 LLM providers
- ✅ Custom system prompts
- ✅ Consistent responses

**Both UIs**: Simple API calls
- ✅ Streamlit can use backend instead of client-side
- ✅ Next.js now has full feature parity
- ✅ Identical results from both apps
- ✅ System prompts actually work

## Migration Path

### Streamlit App (Optional)

The Streamlit app can continue using client-side LLM calls, or optionally migrate to use the backend:

**Benefits of migrating**:
- Reduced code complexity
- Faster responses (Docker network vs external APIs)
- Consistent behavior with Next.js

**Migration**:
Replace client-side LLM calls with:
```python
response = requests.post(
    f'{CLAUDE_GRAPH_SERVICE_URL}/query',
    json={
        'query': prompt,
        'mode': 'vector',
        'llm_provider': active_provider,
        'model': model_option,
        'temperature': temperature,
        'n_results': num_sources
    }
)
```

### Next.js App (Complete)

The Next.js app migration is complete:
- ✅ Updated API client to support all parameters
- ✅ Vector mode now calls backend with LLM synthesis
- ✅ System prompt from Prompt modal is passed to backend
- ✅ Feature parity with Streamlit achieved

## Related Files

- **Backend Service**: [src/services/graph_query_service.py](../src/services/graph_query_service.py)
- **Graph Builder**: [src/services/kimi_graph_builder.py](../src/services/kimi_graph_builder.py)
- **Next.js API**: [webapp/src/lib/api.ts](../webapp/src/lib/api.ts)
- **Next.js UI**: [webapp/src/app/page.tsx](../webapp/src/app/page.tsx)
- **Streamlit UI**: [src/ui/streamlit_ui_docker.py](../src/ui/streamlit_ui_docker.py)
- **Docker Config**: [docker-compose.yml](../docker-compose.yml)
- **Dockerfile**: [config/docker/Dockerfile.graph](../config/docker/Dockerfile.graph)

## Future Enhancements

### 1. Streaming Responses
Stream LLM output for faster perceived performance

### 2. Prompt Templates
Pre-defined prompt templates for common use cases (medical, technical, educational)

### 3. Conversation History
Pass conversation history to LLMs for multi-turn dialogues

### 4. Model Auto-Selection
Automatically select the best model based on query complexity

### 5. Cost Tracking
Track API costs for Claude and Gemini usage

---

**Implementation Date**: December 27, 2025
**Status**: ✅ Complete and tested
**Breaking Changes**: None (backward compatible)
**Verified**: Tested with Ollama (llama2) - generates comprehensive answers with source citations
