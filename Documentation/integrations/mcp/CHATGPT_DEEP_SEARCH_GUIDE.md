# ChatGPT Deep Search Guide

Use this when running deep, multi-step searches through ChatGPT + the obsidian_rag MCP server. It focuses on consistent retrieval and structured answers.

## Prerequisites

- MCP setup completed (see `Documentation/integrations/mcp/MCP_SETUP_INSTRUCTIONS.md`).
- `obsidian-rag-unified` server is connected in ChatGPT Desktop.
- Embedding and graph services are running.
- Graph queries require `OPENAI_API_KEY`; model selection uses `OPENAI_MODEL` in `.env`.

## Deep Search Checklist

1. **State the goal and scope**
   - Example: "Review my lymphoma notes, PET/CT scans, and blood work from Dec 2024–Jan 2026."

2. **Require tool use up front**
   - Example: "Use vault search tools first, then summarize."

3. **Request a scan-by-scan timeline**
   - Ask for: date, modality, size, SUV max, Deauville score, and key findings.

4. **Require missing-data reporting**
   - Example: "If a referenced scan is missing, list it under Missing Data."

5. **Ask for source listing**
   - Example: "List the note filenames used for each scan."

6. **Keep output structured**
   - Request sections: Timeline, Trends, Interpretation, Open Questions.

7. **If results look generic, rerun with tighter query**
   - Include exact note titles or folders (e.g., "Medical/Lymphoma/").

## Prompt Template (Copy/Paste)

```text
Use obsidian_rag tools first. Find all PET/CT scan notes, CT scans, and blood work related to lymphoma between Dec 2024–Jan 2026. Build a timeline with date, modality, lesion size, SUV max, Deauville score, and key findings. List the exact note filenames used for each entry. If any referenced scan or lab is missing, add a "Missing Data" section. Then provide a brief interpretation and 3–6 questions for my oncologist.
```

## Recommended Model/Settings Profile (Consistent Results)

Use one of the following profiles in `.env` and ensure the values are passed to the `api-gateway` and `graph-service` containers.

### Profile: Stable Deep Search (recommended)

```bash
OPENAI_MODEL=gpt-4.1-mini
OPENAI_TIMEOUT=120
DEEP_THINKING_OPENAI_MAX_TOKENS=2200
```

### Profile: Higher-Quality (slower/costlier)

```bash
OPENAI_MODEL=gpt-4.1
OPENAI_TIMEOUT=180
DEEP_THINKING_OPENAI_MAX_TOKENS=2600
```

Notes:
- For `gpt-5*` models, temperature is fixed at the default (the client ignores custom values). The runtime already switches to `max_completion_tokens` for those models.
- If you see truncated answers, increase `DEEP_THINKING_OPENAI_MAX_TOKENS`.

## Verification Steps

- In ChatGPT Desktop, run: "Search my vault for CAR-T therapy" to confirm tool access.
- In a terminal, check API gateway health:

```bash
curl -s http://localhost:4000/api/v1/health
```

If tools are unavailable, re-check the MCP config, then restart ChatGPT Desktop.
