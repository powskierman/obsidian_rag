# Streamlit Backend Migration Guide

## Overview

This guide shows how to migrate the Streamlit app from client-side LLM calls to using the backend `graph_query_service.py`. This will:
- Reduce code complexity (~150 lines removed)
- Ensure consistent behavior with Next.js app
- Leverage backend's unified LLM integration

## Current Architecture (Before)

**Streamlit App** (lines 656-967):
- ❌ 300+ lines of client-side LLM integration code
- ❌ Separate API calls for Claude, Gemini, Ollama, GPT-OSS
- ❌ Duplicated logic for enhanced search (LLM knowledge + web search)
- ❌ Different behavior from Next.js app

## New Architecture (After)

**Streamlit App**:
- ✅ Single backend API call
- ✅ ~30 lines of code (instead of 300+)
- ✅ Identical results to Next.js app
- ✅ All LLM logic handled by backend

## Migration Steps

### Step 1: Replace Vector/Hybrid Mode LLM Calls

**BEFORE** (lines 621-809 in `streamlit_ui_docker.py`):
```python
# Get selected LLM provider from session state
active_provider = st.session_state.get('llm_provider', 'ollama')

# ... 200+ lines of client-side LLM code for Claude, Gemini, Ollama, GPT-OSS ...

if active_provider == "claude":
    # Claude API code
    from anthropic import Anthropic
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    ...
elif active_provider == "gemini":
    # Gemini API code
    ...
else:
    # Ollama API code
    ...
```

**AFTER** (simplified replacement):
```python
# Get selected LLM provider from session state
active_provider = st.session_state.get('llm_provider', 'ollama')

# Determine display name and model for spinner
provider_display = {"ollama": "Ollama", "gemini": "Gemini Pro", "claude": "Claude Sonnet", "gpt-oss": "GPT-OSS"}.get(active_provider, "Ollama")

if active_provider == "gemini":
    display_model = "gemini-3-pro-preview"
elif active_provider == "claude":
    display_model = "claude-sonnet-4-5"
elif active_provider == "gpt-oss":
    display_model = model_option
else:  # ollama
    display_model = model_option

with st.spinner(f"💭 Thinking with {display_model} ({provider_display})..."):
    try:
        # Call backend for LLM synthesis
        llm_response = requests.post(
            f'{CLAUDE_GRAPH_SERVICE_URL}/query',
            json={
                'query': prompt,
                'mode': 'vector',  # or 'hybrid' based on search_mode
                'llm_provider': active_provider,
                'model': model_option,
                'temperature': temperature,
                'n_results': num_sources,
                'llm_knowledge': enhanced_search,
                'web_search': enhanced_search and active_provider in ["gemini", "claude"]
            },
            timeout=180
        )

        if llm_response.status_code != 200:
            st.error(f"Backend error: {llm_response.status_code}")
            st.code(llm_response.text)
            st.stop()

        result = llm_response.json()
        response_text = result['answer']
        llm_knowledge_text = result.get('llm_knowledge', '')
        web_search_data = result.get('web_search', {})

    except Exception as e:
        st.error(f"Query error: {e}")
        st.stop()
```

### Step 2: Handle Enhanced Search Results

**BEFORE** (lines 810-967):
```python
# Enhanced Search Sections (if enabled)
llm_knowledge_text = ""
web_search_text = ""

if enhanced_search:
    # Section 2: LLM Knowledge (100+ lines of code)
    with st.spinner("🧠 Gathering additional knowledge..."):
        try:
            if active_provider == "claude":
                # Claude-specific code
                ...
            elif active_provider == "gemini":
                # Gemini-specific code
                ...
            else:
                # Ollama-specific code
                ...
        except:
            ...

    # Section 3: Web Search (100+ lines of code)
    with st.spinner("🌐 Searching the web..."):
        try:
            # Web search code
            ...
        except:
            ...
```

**AFTER** (simplified):
```python
# Enhanced search results come from backend
llm_knowledge_text = ""
web_search_text = ""

if enhanced_search and result.get('llm_knowledge'):
    if isinstance(result['llm_knowledge'], str):
        llm_knowledge_text = result['llm_knowledge']
    else:
        llm_knowledge_text = f"_Could not retrieve LLM knowledge: {result['llm_knowledge'].get('error', 'Unknown error')}_"

if enhanced_search and result.get('web_search'):
    web_data = result['web_search']
    if 'results' in web_data and web_data['results']:
        web_results = []
        for i, res in enumerate(web_data['results'], 1):
            web_results.append(f"{i}. **[{res['title']}]({res['url']})**\n   {res['content']}")
        web_search_text = f"_Search terms used: {web_data.get('search_terms', '')}_\n\n" + "\n\n".join(web_results)
    elif 'error' in web_data:
        web_search_text = f"_Web search unavailable: {web_data['error']}_"
    else:
        web_search_text = "_No web results found._"
```

### Step 3: Update Knowledge Graph Mode

The knowledge graph mode already uses the backend correctly (lines 566-608), so no changes needed.

### Step 4: Complete Replacement Code

Here's the complete replacement for lines 621-967 in `streamlit_ui_docker.py`:

```python
else:
    # For vector and hybrid modes, use backend LLM integration
    # Get selected LLM provider from session state
    active_provider = st.session_state.get('llm_provider', 'ollama')

    # Determine provider display name and model for spinner
    provider_display = {"ollama": "Ollama", "gemini": "Gemini Pro", "claude": "Claude Sonnet", "gpt-oss": "GPT-OSS"}.get(active_provider, "Ollama")

    # Use correct model name based on provider
    if active_provider == "gemini":
        display_model = "gemini-3-pro-preview"
    elif active_provider == "claude":
        display_model = "claude-sonnet-4-5"
    elif active_provider == "gpt-oss":
        display_model = model_option
    else:  # ollama
        display_model = model_option

    # Determine mode based on search_mode
    if search_mode == 'vector':
        query_mode = 'vector'
    elif search_mode == 'hybrid':
        query_mode = 'hybrid'
    else:
        query_mode = 'vector'  # fallback

    with st.spinner(f"💭 Thinking with {display_model} ({provider_display})..."):
        try:
            # Call backend for unified LLM synthesis
            llm_response = requests.post(
                f'{CLAUDE_GRAPH_SERVICE_URL}/query',
                json={
                    'query': prompt,
                    'mode': query_mode,
                    'llm_provider': active_provider,
                    'model': model_option,
                    'temperature': temperature,
                    'n_results': num_sources,
                    'llm_knowledge': enhanced_search,
                    'web_search': enhanced_search and active_provider in ["gemini", "claude"]
                },
                timeout=180
            )

            if llm_response.status_code != 200:
                st.error(f"Backend error: {llm_response.status_code}")
                st.code(llm_response.text)
                st.stop()

            result = llm_response.json()
            response_text = result['answer']

            # Enhanced Search Sections (from backend)
            llm_knowledge_text = ""
            web_search_text = ""

            if enhanced_search:
                # LLM Knowledge section
                if result.get('llm_knowledge'):
                    if isinstance(result['llm_knowledge'], str):
                        llm_knowledge_text = result['llm_knowledge']
                    else:
                        llm_knowledge_text = f"_Could not retrieve LLM knowledge: {result['llm_knowledge'].get('error', 'Unknown error')}_"

                # Web Search section
                if result.get('web_search'):
                    web_data = result['web_search']
                    if 'results' in web_data and web_data['results']:
                        web_results = []
                        for i, res in enumerate(web_data['results'], 1):
                            web_results.append(f"{i}. **[{res['title']}]({res['url']})**\n   {res['content']}")
                        web_search_text = f"_Search terms used: {web_data.get('search_terms', '')}_\n\n" + "\n\n".join(web_results)
                    elif 'error' in web_data:
                        web_search_text = f"_Web search unavailable: {web_data['error']}_"
                    else:
                        web_search_text = "_No web results found._"
                else:
                    if active_provider not in ["gemini", "claude"]:
                        web_search_text = f"_⚠️ Web search not available with {provider_display}_"

        except Exception as e:
            st.error(f"Query error: {e}")
            logger.error(f"Backend query error: {e}")
            st.stop()
```

## Benefits

### Code Reduction
- **Before**: ~350 lines of LLM integration code
- **After**: ~60 lines
- **Saved**: ~290 lines

### Maintenance
- **Before**: Update LLM code in Streamlit AND backend
- **After**: Update only in backend, both UIs benefit

### Consistency
- **Before**: Streamlit and Next.js could give different results
- **After**: Identical results from both UIs

### Feature Parity
- **Before**: Manual sync needed between UIs
- **After**: Automatic feature parity

## Testing

### Test Vector Mode
```python
# In Streamlit UI
# Select: Search Mode = Vector, LLM Provider = Ollama
# Enter query: "What are mitochondria?"
# Verify: Gets comprehensive answer with sources
```

### Test Hybrid Mode
```python
# In Streamlit UI
# Select: Search Mode = Hybrid, LLM Provider = Claude
# Enter query: "What health topics are discussed?"
# Verify: Gets graph + vector synthesis
```

### Test Enhanced Search
```python
# In Streamlit UI
# Enable "Enhanced Search" checkbox
# Select: LLM Provider = Claude (for web search)
# Enter query: "Review my health data"
# Verify: Shows 3 sections - Vault, LLM Knowledge, Web Search
```

## Breaking Changes

None - the migration is backward compatible. The UI behavior remains identical, just powered by the backend instead of client-side code.

## Migration Checklist

- [ ] Backup `streamlit_ui_docker.py`
- [ ] Replace lines 621-967 with new code (above)
- [ ] Test vector mode with Ollama
- [ ] Test vector mode with Claude
- [ ] Test vector mode with Gemini
- [ ] Test hybrid mode
- [ ] Test enhanced search (LLM knowledge + web)
- [ ] Verify sources display correctly
- [ ] Verify ratings work
- [ ] Compare results with Next.js app (should be identical)

## Rollback Plan

If issues occur:
1. Restore backup of `streamlit_ui_docker.py`
2. Restart Streamlit container
3. Report issue for backend fix

## Related Files

- **Streamlit UI**: [src/ui/streamlit_ui_docker.py](../src/ui/streamlit_ui_docker.py)
- **Backend Service**: [src/services/graph_query_service.py](../src/services/graph_query_service.py)
- **Next.js UI**: [webapp/src/app/page.tsx](../webapp/src/app/page.tsx)

---

**Migration Status**: Ready to implement
**Code Reduction**: ~290 lines
**Estimated Time**: 15 minutes
**Risk Level**: Low (easy rollback available)
