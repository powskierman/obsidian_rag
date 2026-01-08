# Models Overview

Supported LLM providers in `src/services/graph_query_service.py`:

- `ollama` (local)
- `claude` (Anthropic)
- `gemini` (Google)
- `gpt-oss` (OpenAI-compatible)
- `kimi` (OpenRouter)

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
- `GPT_OSS_HOST` (gpt-oss endpoint)
- `OLLAMA_HOST` (Ollama)

See `Documentation/Models/SETUP.md` for setup steps.
