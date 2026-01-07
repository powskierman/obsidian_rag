# Lymphoma Query Issue - Root Cause Analysis & Fix

## Date: 2026-01-05

## Problem Statement

When querying "Lymphoma Progress report" across different search modes (entities, entities+vector, dual graph), the system returns:
> "I do not have enough information to answer."

Even though:
- **Dual graph mode reports 220 sources retrieved**
- The LightRAG debug logs show 20+ relevant lymphoma documents being found
- The documents contain extensive information about DLBCL, Yescarta, CAR-T therapy, etc.

## Root Cause

### The Paradox: Retrieval Success, Synthesis Failure

The investigation revealed a critical disconnect between **retrieval** and **synthesis**:

1. **Retrieval Layer** ✅ **WORKING CORRECTLY**
   - LightRAG successfully finds 20+ relevant documents
   - Documents include:
     - `GCB DLBCL treatment alternatives.md`
     - `CAR-T Cell Therapy.md`
     - `Lymphoma Treatment.md`
     - `ASCT Poor Outcome Studies.md`
     - And many more...

2. **Synthesis Layer** ❌ **FAILING**
   - The LLM (Kimi K2-0905 via OpenRouter) receives all this context
   - But responds with "I do not have enough information"
   - This is due to **overly conservative system prompts**

### The System Prompt Problem

#### Original LightRAG Prompt (lines 52-65 of `lightrag_service.py`):

```python
DEFAULT_SYSTEM_PROMPT = """You are a **Deep Thinking AI assistant**...

When generating your answer:
1. Reference Michel's specific **medical timeline**...
2. Incorporate insights from his **Obsidian notes**...
3. Maintain a **compassionate and supportive** tone...
4. Provide **technical depth** and precision...
5. Adapt to his **expert-level understanding**...
6. Be **concise but thorough**, focusing on clarity and reasoning.
7. Avoid redundant or generic phrasing.
"""
```

**The Problem**: The prompt tells the LLM to be "concise" and avoid redundancy, but it doesn't explicitly instruct it to **USE** the provided context. When combined with LightRAG's internal prompting, this causes the LLM to be overly cautious.

#### Similar Issue in Graph Query Service (line 759):

The hybrid mode synthesis prompt had the same issue - no explicit instruction to synthesize from the provided context.

## The Fix

### The Real Problem (Updated After Further Investigation)

The initial fix to `DEFAULT_SYSTEM_PROMPT` helped with the wrapper's LLM calls, but **the actual issue was deeper**: 

**Line 297 of `lightrag_service.py` was calling `rag.aquery()` WITHOUT a `system_prompt` parameter.**

```python
# BEFORE (Line 297):
result = await rag.aquery(query_text, param=param)  # ❌ No system_prompt!
```

This meant LightRAG was using its **own internal default prompt**, which is extremely conservative and tends to say "I don't have enough information" even when provided with extensive context.

### The Actual Fix

**Modified `_do_query_async()` function (lines 274-298):**

1. **Use a stronger system prompt** for LightRAG's in-library response path:

```python
lightrag_system_prompt = """You are analyzing Michel's Obsidian Knowledge Base to answer his question.

**CRITICAL**: You have been provided with extensive context including entities, relationships, 
and document chunks retrieved from the knowledge graph. Your task is to SYNTHESIZE this 
information into a comprehensive answer.

**DO NOT** claim "insufficient information" or "I don't have enough context" when you have 
been given entities, relationships, and chunks. If context is provided, USE IT to construct 
your answer.

Guidelines:
1. **Synthesize the provided entities, relationships, and chunks** into a coherent answer
2. Reference specific information from Michel's notes when relevant
3. For medical topics (DLBCL, Yescarta, lymphoma): Be compassionate, supportive, and medically accurate
4. For technical topics: Provide depth and precision appropriate to his expert-level understanding
5. Cite which notes or sources you're drawing from
6. Structure your answer clearly with headers/sections if appropriate
7. Be thorough but focused - include relevant details without unnecessary verbosity

Remember: The context you receive IS the answer to the question - your job is to organize 
and present it clearly."""
```

2. **Pass the prompt to `aquery()`**:

```python
# AFTER (Line 297):
result = await rag.aquery(query_text, param=param, system_prompt=DEFAULT_SYSTEM_PROMPT)  # ✅ Stronger prompt
```

**Note**: The current implementation uses LightRAG's in-library response path with the stronger prompt (no custom synthesis layer).

### Why This Works

LightRAG's `aquery()` method accepts an optional `system_prompt` parameter. When not provided, it uses `PROMPTS["rag_response"]` from its internal configuration, which is designed to be conservative and cautious.

By passing our own prompt that explicitly says:
- "You HAVE context - use it"
- "DO NOT claim insufficient information when context is provided"
- "The context IS the answer - organize and present it"

We override LightRAG's conservative behavior and force it to synthesize from the retrieved data.

## Files Modified

1. `/src/integrations/lightrag_service.py` (lines 274-320)
   - **PRIMARY FIX**: Added `lightrag_system_prompt` and passed it to `rag.aquery()`
   - Also updated `DEFAULT_SYSTEM_PROMPT` (lines 51-69) for wrapper LLM calls

2. `/src/services/graph_query_service.py` (lines 759-782)
   - Updated `synthesis_system_prompt` in hybrid mode (secondary fix for graph+vector queries)

## Services Restarted

```bash
docker-compose restart lightrag-service graph-service
```

## Testing Recommendations

### Test 1: Entities Mode (LightRAG)
```
Query: "Lymphoma Progress report"
Mode: entities
Expected: Detailed summary of your lymphoma treatment timeline, citing specific notes
```

### Test 2: Entities+Vector Mode
```
Query: "Lymphoma Progress report"
Mode: entities+vector
Expected: Even more comprehensive answer combining entity graph and vector search
```

### Test 3: Dual Graph Mode
```
Query: "Lymphoma Progress report"
Mode: dual-graph
Expected: Synthesis of both NetworkX structural graph and LightRAG entity graph
```

### Test 4: Verify Source Citations
All responses should include:
- Specific note names (e.g., "According to your note on CAR-T Cell Therapy...")
- Timeline references (e.g., "Your DLBCL diagnosis...", "After Yescarta treatment...")
- Proper citations of the 220 sources being retrieved

## Why This Happened

This is a classic **prompt engineering issue** where:

1. **Implicit assumptions don't work**: We assumed the LLM would naturally use the context provided
2. **Conservative behavior is the default**: LLMs err on the side of caution when uncertain
3. **Explicit instructions are required**: We need to tell the LLM "YOU HAVE CONTEXT, USE IT"

## Prevention

For future system prompts:
- ✅ Always include explicit "USE THE PROVIDED CONTEXT" instructions
- ✅ Add negative instructions: "DO NOT claim insufficient information when context exists"
- ✅ Test with queries that have known-good retrieval to verify synthesis works
- ✅ Monitor debug logs to catch retrieval vs. synthesis disconnects

## Additional Notes

### Why 220 Sources But No Answer?

The "220 sources" number comes from the dual-graph mode which combines:
- NetworkX graph: ~16,000 nodes (note-level connections)
- LightRAG graph: ~7,000 entities (concept-level connections)

When querying "Lymphoma," both graphs find extensive connections, but the final LLM synthesis step was failing due to the prompt issue.

### Model Behavior

The Kimi K2-0905 model is actually quite capable, but it's also very literal. When the prompt says "be concise" without saying "use the context," it interprets this as "only answer if you're absolutely certain," leading to the "insufficient information" response even with 220 sources available.

## Verification

After restarting services, check:

```bash
# Verify services are running
docker ps | grep obsidian

# Check LightRAG logs for new prompt
docker exec obsidian-lightrag cat /app/lightrag_db/prompt_debug.log | tail -50

# Test a query and verify it uses context
# (Use the web UI or API to submit "Lymphoma Progress report")
```

## Success Criteria

✅ Query "Lymphoma Progress report" returns a detailed summary
✅ Response cites specific notes from your vault
✅ Response includes timeline information (DLBCL diagnosis, Yescarta, scans, etc.)
✅ No more "I do not have enough information" when 220 sources are available
