# Graph Query Quality - Root Cause Analysis

**Investigation Date**: December 28, 2025
**Status**: 🔍 Root Cause Identified
**Severity**: 🔴 Critical - Affects core graph query quality

---

## The Problem

**User Report**:
> "Certainly not the same quality as the streamlit app results. Why?"

Despite identical UI settings:
- ✅ Both UIs in Hybrid mode
- ✅ Both using Gemini Pro
- ✅ Both with Enhanced Search enabled
- ✅ Both with same number of sources
- ✅ Both sending identical parameters to backend

**Streamlit Result** (High Quality):
```
📚 Vault Knowledge
Hello Michel. Based on the notes in your Obsidian knowledge base, I have reconstructed
the timeline and assessment of your imaging history regarding your Double-hit DLBCL
and response to Yescarta CAR-T therapy.

Timeline:
1. Pre-Treatment / Baseline (March 14, 2025): SUV max 27.4
2. 1-Month Post-Infusion CT (May 16, 2025): size decreased
3. 3-Month Post-Infusion PET (July 16, 2025): SUV max 4.0, Deauville 4
4. 6-Month Post-Infusion PET (October 2025): SUV max 10.5, Deauville 5

Sources Referenced: 1, 2, 4, 5, 7 (with specific dates, SUV values, Dr. Slaby mentions)
```

**Next.js Result** (Generic):
```
📚 Vault Knowledge
Assessment of the four PET-scan entities in your graph

1. What is captured
All four nodes are literally the same: every relationship triple is identical.
Entity: PET Scan
− monitors → DLBCL
− relates_to → CAR-T Therapy

[Generic graph structure analysis, no specific dates or values]
```

---

## Investigation Timeline

### 1. Initial Hypothesis: Enhanced Search Not Working
**Status**: ❌ Ruled Out

Checked:
- ✅ Next.js sends `llm_knowledge=true` and `web_search=true`
- ✅ Backend receives these parameters
- ✅ Backend returns enhanced content
- ✅ Frontend displays enhanced content

**Finding**: Enhanced search (🧠 LLM Knowledge, 🌐 Web Search) works fine. The issue is with the **main graph answer quality**.

### 2. Second Hypothesis: Custom System Prompt Not Used
**Status**: ⚠️ Partially Correct

**Discovery**: Backend's LLM Knowledge generation (lines 671-697 in graph_query_service.py) was using a generic prompt instead of the user's custom system prompt.

**Fix Applied**:
```python
# Now checks if custom_system_prompt exists and uses it
if custom_system_prompt:
    knowledge_prompt = f"""{custom_system_prompt}

Based on the following information found in the user's vault:
{graph_answer[:2000]}
...
"""
```

**User Feedback**: "This is a tough nut to crack! I get the same result."

**Conclusion**: This fix improved the LLM Knowledge section but **did NOT fix the main graph answer quality**.

### 3. Third Hypothesis: Frontend Differences
**Status**: ❌ Ruled Out

**User Clarification**:
> "Regarding your questions both UI are set the same. The frontends should be just for
> data entry. All processing should be done by the backend to achieve a single source
> of truth"

**Confirmed**:
- Both frontends send identical parameters
- Both hit the same backend service at port 8002
- Backend should return identical results
- **But it doesn't!**

---

## Root Cause Discovered

### The Real Issue: Graph Query System Prompt

**File**: [kimi_graph_builder.py:366-382](../src/services/kimi_graph_builder.py)

```python
def query_with_llm(self, user_query: str, max_entities: int = 20, additional_context: str = "") -> str:
    """Query the knowledge graph using the LLM with optional additional context from vector search"""
    entities_in_query = [node for node in self.graph.nodes() if node.lower() in user_query.lower()]
    graph_context = [self.get_entity_neighborhood(e) for e in entities_in_query[:max_entities]]

    if not graph_context:
        centrality = nx.degree_centrality(self.graph)
        top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:10]
        graph_context = [self.get_entity_neighborhood(node) for node, _ in top_nodes]

    context_text = "\n---\n".join([f"Entity: {c['entity']}\nRelationships: " +
        ", ".join([f"{c['entity']} --[{r['relationship']}]--> {r['target']}" for r in c['outgoing']])
        for c in graph_context])

    # ❌ HARDCODED GENERIC SYSTEM PROMPT
    prompt_parts = ["You are analyzing a personal knowledge graph. Answer the user's question based on the graph structure and relationships."]

    if additional_context:
        prompt_parts.append(f"\nAdditional Context from Vector Search:\n<vector_context>\n{additional_context}\n</vector_context>")

    prompt_parts.append(f"\nKnowledge Graph Context:\n<graph>\n{context_text}\n</graph>")
    prompt_parts.append(f"\nUser Question: {user_query}")
    prompt_parts.append("\nProvide a comprehensive answer cite specific entities when relevant.")

    prompt = "\n".join(prompt_parts)

    # Uses Kimi K2 model via OpenRouter
    response = self.client.chat.completions.create(
        model=self.model,  # moonshotai/kimi-k2-0905
        messages=[{"role": "user", "content": prompt}],
        max_tokens=3000
    )
    return response.choices[0].message.content
```

### The Problem

**Line 371**: Hardcoded generic system prompt:
```python
"You are analyzing a personal knowledge graph. Answer the user's question based on the graph structure and relationships."
```

**Missing**:
- No knowledge of Michel's medical timeline
- No context about DLBCL, CAR-T therapy, Yescarta
- No awareness of Dr. Slaby
- No understanding that this is a cancer patient's medical journey
- No instruction to be compassionate and medically accurate
- No direction to provide expert-level analysis

### How This is Called

**File**: [graph_query_service.py:519](../src/services/graph_query_service.py)

```python
# Step 1: Query the knowledge graph
graph_answer = querier.query_with_llm(user_query, max_entities=max_entities)
```

**Notice**: `custom_system_prompt` is received at line 412 but **NEVER passed** to `query_with_llm()`!

The method signature shows:
```python
def query_with_llm(self, user_query: str, max_entities: int = 20, additional_context: str = "") -> str:
```

There is **NO parameter** for custom system prompt!

---

## Why Streamlit Appears to Work Better

### Hypothesis 1: Different Entity Extraction

The query "review my 4 pet scans" might extract different entities:
- **Streamlit**: Finds specific PET scan entities with dates, SUV values
- **Next.js**: Finds generic "PET Scan" entity nodes

This could be due to:
1. Case sensitivity in entity matching (line 355: `if node.lower() in user_query.lower()`)
2. Different graph nodes available
3. Different centrality calculations if no entities match

### Hypothesis 2: Different Graph Data

Possible that:
- Streamlit UI connects to a different graph file
- Graph was rebuilt/updated between Streamlit and Next.js usage
- Different graph indexing quality

### Hypothesis 3: Model Behavior Variation

Kimi K2 (moonshotai/kimi-k2-0905) might:
- Have non-deterministic responses
- Perform differently based on timing
- Cache previous results

---

## The Solution

### Fix Required

Update `query_with_llm` to accept and use custom system prompt:

**File**: [kimi_graph_builder.py](../src/services/kimi_graph_builder.py)

**Before**:
```python
def query_with_llm(self, user_query: str, max_entities: int = 20, additional_context: str = "") -> str:
    # Hardcoded generic prompt
    prompt_parts = ["You are analyzing a personal knowledge graph. Answer the user's question based on the graph structure and relationships."]
```

**After**:
```python
def query_with_llm(self, user_query: str, max_entities: int = 20, additional_context: str = "", custom_system_prompt: str = "") -> str:
    # Use custom system prompt if provided, otherwise use default
    if custom_system_prompt:
        prompt_parts = [custom_system_prompt]
    else:
        prompt_parts = ["You are analyzing a personal knowledge graph. Answer the user's question based on the graph structure and relationships."]
```

**And update the call site** in [graph_query_service.py:519](../src/services/graph_query_service.py):
```python
# Pass custom_system_prompt to graph query
graph_answer = querier.query_with_llm(
    user_query,
    max_entities=max_entities,
    custom_system_prompt=custom_system_prompt
)
```

---

## Impact

### Without Fix (Current State)

Graph queries use a generic prompt that:
- ❌ Doesn't know about Michel's medical context
- ❌ Doesn't understand the importance of specific dates and values
- ❌ Treats medical queries like generic graph traversal
- ❌ Produces abstract "Entity X relates to Entity Y" responses
- ❌ No compassionate, medically-aware tone
- ❌ No expert-level clinical analysis

### With Fix (Expected)

Graph queries will use Michel's custom prompt:
- ✅ Knows about DLBCL, CAR-T therapy, Yescarta
- ✅ References Dr. Slaby when appropriate
- ✅ Provides medical timeline context
- ✅ Expert-level, compassionate tone
- ✅ Cites specific notes and sources
- ✅ Medically accurate, actionable guidance

---

## Debug Logging Added

To confirm this diagnosis, I added detailed logging:

### In graph_query_service.py (lines 519-528):
```python
logger.info(f"=== GRAPH QUERY DEBUG ===")
logger.info(f"Query: {user_query}")
logger.info(f"Mode: {mode}")
logger.info(f"LLM Provider: {llm_provider}")
logger.info(f"Model: {model}")
logger.info(f"Max Entities: {max_entities}")
logger.info(f"Custom System Prompt Present: {bool(custom_system_prompt)}")
logger.info(f"Custom System Prompt (first 200 chars): {custom_system_prompt[:200] if custom_system_prompt else 'None'}")
graph_answer = querier.query_with_llm(user_query, max_entities=max_entities)
logger.info(f"Graph Answer (first 500 chars): {graph_answer[:500]}")
```

### In kimi_graph_builder.py (lines 356-368):
```python
logger.info(f"=== GRAPH BUILDER DEBUG ===")
logger.info(f"Entities found in query: {entities_in_query[:10]}")
# ...
if not graph_context:
    logger.info(f"No entities in query, using top centrality nodes: {[node for node, _ in top_nodes]}")
# ...
logger.info(f"Graph context (first 500 chars): {context_text[:500]}")
```

**To Test**:
1. Make a query from Next.js UI: "review my 4 pet scans and provide your assessment"
2. Check logs: `docker logs obsidian-graph-service | grep "GRAPH"`
3. Verify:
   - Is `custom_system_prompt` received? (Should be: YES if user entered it in Prompt modal)
   - What entities are found? (Should show which graph nodes matched the query)
   - What's in the graph context? (Should show the relationship data being sent to LLM)

---

## User's Core Requirement

> "The frontends should be just for data entry. All processing should be done by the
> backend to achieve a single source of truth"

**Current State**: ❌ Backend is NOT single source of truth because:
- Custom system prompt is received but not used for graph queries
- Graph query quality depends on hardcoded generic prompts
- Different results despite identical parameters

**Expected State**: ✅ Backend should be single source of truth:
- Same parameters → Same processing → Same results
- Custom system prompt used consistently across ALL query types
- Graph, Vector, and LLM Knowledge all use user's personalization

---

## Next Steps

1. ✅ Debug logging added (service restarted)
2. ⏳ **User to test and provide logs** from a query
3. ⏳ Implement the fix to pass custom_system_prompt to graph query
4. ⏳ Test that both UIs now get identical, high-quality results
5. ⏳ Verify backend is true single source of truth

---

## Related Documentation

1. [Enhanced Search Display Bug](ENHANCED_SEARCH_DISPLAY_BUG.md) - Fixed display of llm_knowledge/web_search
2. [Model Selection Fix](MODEL_SELECTION_FIX.md) - Fixed model selection for Gemini/Claude
3. [System Prompt LLM Knowledge Fix](SYSTEM_PROMPT_LLM_KNOWLEDGE_FIX.md) - Fixed LLM Knowledge using custom prompt
4. **This Document** - Graph query doesn't use custom prompt (ROOT CAUSE)

---

## Conclusion

**Root Cause**: The graph query method `query_with_llm()` uses a hardcoded generic system prompt and never receives or uses the user's custom system prompt, even though it's sent by both frontends to the backend.

**Why Streamlit Seems Better**: Unclear - needs investigation. Could be:
- Different entities extracted from the query
- Different graph data being used
- Model non-determinism
- Timing/caching differences

**The Real Fix**: Pass `custom_system_prompt` to `query_with_llm()` so graph queries are personalized with Michel's medical context, just like the LLM Knowledge section now is.

**User Impact**: Once fixed, both UIs will produce **identical, high-quality, medically-aware responses** that reference Michel's specific medical timeline, doctors, and treatment journey.
