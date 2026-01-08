# Model Setup

## Ollama (Local)

1. Install and start Ollama.
2. Pull a model:
   ```bash
   ollama pull llama3.2
   ```
3. Ensure `OLLAMA_HOST` is set if not default.

## Claude (Anthropic)

Set `ANTHROPIC_API_KEY` in `.env`.

## Gemini (Google)

Set `GEMINI_API_KEY` in `.env`.

## Kimi (OpenRouter)

Set `OPENROUTER_API_KEY` in `.env`.

## GPT-OSS

Point `GPT_OSS_HOST` to your OpenAI-compatible endpoint.

## Verify

```bash
docker compose up -d
curl -s http://localhost:4000/api/v1/health
```
