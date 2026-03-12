# Model Setup

Obsidian RAG supports a wide range of LLM providers for both the **Knowledge Graph**, **Search**, and **Deep Thinking** agent.

## Configuration (.env)

All model settings are controlled via environment variables in your `.env` file. These settings are now automatically picked up by the Web UI as intelligent defaults.

### 1. Ollama (Local Privacy)

Deep Thinking works best with larger models (e.g., Llama 3.3 70B, DeepSeek R1), but efficient local models work too.

1. **Install Ollama**: [ollama.com](https://ollama.com)
2. **Pull a Model**:
   ```bash
   ollama pull mistral
   # OR for reasoning:
   ollama pull deepseek-r1
   ```
3. **Configure .env**:
   ```bash
   OLLAMA_HOST=http://host.docker.internal:11434  # For Docker access
   OLLAMA_MODEL=mistral                         # Default model
   ```

> **Note**: For `deepseek-r1`, the Deep Thinking agent automatically handles system prompts to avoid degradation.

### 2. Perplexity AI (Online Search)

Perplexity provides excellent live web search and citations.

1. **Get API Key**: [perplexity.ai](https://www.perplexity.ai/settings/api)
2. **Configure .env**:
   ```bash
   PERPLEXITY_API_KEY=pplx-xxxxxxxx...
   PERPLEXITY_MODEL=llama-3.1-sonar-large-128k-online
   ```

### 3. OpenRouter (Universal Aggregator)

Access hundreds of models (Claude, GPT-4, Llama 3, Qwen) via a single API.

1. **Get API Key**: [openrouter.ai](https://openrouter.ai/keys)
2. **Configure .env**:
   ```bash
   OPENROUTER_API_KEY=sk-or-v1-...
   OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free  # Example free model
   ```

> **Stability**: The system now includes retry logic and special headers (`HTTP-Referer`, `X-Title`) to ensure reliable connection to OpenRouter, even for free-tier models.

### 4. Claude (Anthropic)

Best for high-quality Knowledge Graph building and complex reasoning.

```bash
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-3-5-sonnet-latest
```

### 5. Google Gemini

Fast and large context windows (up to 2M tokens).

```bash
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-1.5-pro
```

### 6. OpenAI (ChatGPT)

Standard reliable baseline.

```bash
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o
```

---

## 🧠 UI Smart Defaults

When you switch providers in the Web UI Settings panel, the system now **automatically pre-fills the model** based on your `.env` configuration.

- If you set `OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct`, selecting "OpenRouter" in the UI will instantly switch to that model.
- This prevents "invalid model ID" errors and makes switching between your preferred models seamless.
