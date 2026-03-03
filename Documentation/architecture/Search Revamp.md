# Implementation Plan: Fix Cascading and Deep Thinking

This plan addresses Phase 1 of the assessment to restore broken functionality in the [cascading](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#1989-2051) and `deep-research` modes before we proceed to tear down the legacy search modes in Phase 2.

## Proposed Changes

### 1. Fix Deep Thinking Port Mismatch

#### [MODIFY] [universal_client.py](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py)
Update the [_create_mlx](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py#377-434) function to properly default to port `8090/v1` for MLX requests, rather than `1234/v1`. This will match how [graph_query_service.py](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/graph_query_service.py) handles MLX.

```python
        base_url = os.getenv("QUERY_MLX_BASE_URL") or os.getenv("MLX_BASE_URL", "http://host.docker.internal:8090/v1")
```

### 2. Fix Cascading Synthesis Support

#### [MODIFY] [api_gateway.py](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py)
Replace the hardcoded [ollama](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py#435-505)/[openrouter](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py#218-291) logic in [_synthesize_cascading_answer](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#1989-2051) with proper logic that fully supports [mlx](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py#377-434), `chatgpt`, [gemini](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py#139-217), etc. We will refactor it to use the new LLM client patterns used elsewhere in the application, or simply mirror the logic from [_call_query_normalizer_llm](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#648-744) that handles [mlx](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py#377-434), `chatgpt`, [openrouter](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py#218-291), and [ollama](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py#435-505) appropriately using `httpx.AsyncClient`.

We will:
1. Identify the requested `llm_provider`.
2. Construct the URL and Headers dynamically based on the provider (OpenAI, OpenRouter, MLX, Gemini, Ollama).
3. Send the asynchronous POST request and parse the response natively.

## Verification Plan

### Automated Tests
- Run `pytest tests/unit/test_deep_thinking_synthesizer.py` or equivalent suites to ensure the Deep Thinking [UniversalClient](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py#22-505) still builds and operates correctly without syntax errors.

### Manual Verification
1. I will ask you to run a query using [cascading](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/src/services/api_gateway.py#1989-2051) mode with [mlx](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py#377-434) (or another previously failing provider) to confirm it returns a full summary rather than raw snippets.
2. I will ask you to run a `deep-research` query using [mlx](file:///Users/michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/deep_thinking/utils/universal_client.py#377-434) to ensure that it connects to `8090` without throwing the `1234 connection refused` error.
