# Models Overview

Supported LLM providers in `src/services/graph_query_service.py`:

- `ollama` (local)
- `claude` (Anthropic)
- `gemini` (Google)
- `gpt-oss` (OpenAI-compatible)
- `kimi` (OpenRouter)

## Component Model Usage

- **Vector DB (`embedding_service.py`)**: no generative LLM. It uses embedding + reranker models only.
- **NetworkX graph (`graph_query_service.py` + `networkx_graph_builder.py`)**:
  - API synthesis model is selected by request (`llm_provider` + `model`).
  - Structural graph answer model defaults to `GRAPH_MODEL`/`OPENROUTER_MODEL`.
  - Structural graph LLM endpoint is configurable with `GRAPH_LLM_BASE_URL` + `GRAPH_LLM_API_KEY` (falls back to OpenRouter env).
- **LightRAG (`lightrag_service.py`)**:
  - OpenRouter model env is `LIGHTRAG_MODEL` (with backward compatibility fallback to `KIMI_MODEL`).
  - Query-time override remains `QUERY_LLM_MODEL`.

## Default Models

- `ollama`: `llama3.2`
- `claude`: `claude-sonnet-4-5-20250929`
- `gemini`: `gemini-3-pro-preview`
- `gpt-oss`: `gpt-4`
- `kimi`: `moonshotai/kimi-k2-0905`

## Required Environment Variables

- `ANTHROPIC_API_KEY` (Claude)
- `GEMINI_API_KEY` (Gemini)
- `OPENROUTER_API_KEY` (Kimi)
- `LIGHTRAG_MODEL` (LightRAG OpenRouter model; preferred)
- `GRAPH_MODEL` (NetworkX structural graph model; preferred)
- `GPT_OSS_HOST` (gpt-oss endpoint)
- `OLLAMA_HOST` (Ollama)

See `Documentation/operations/models/SETUP.md` for setup steps.
