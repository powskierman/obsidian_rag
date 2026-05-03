# PDF Tree Retrieval Operations

PDF tree retrieval is the operational path for PDF information retrieval. LightRAG PDF ingestion is intentionally decommissioned because large PDFs take too long to index through the graph pipeline and produce poor page-level traceability.

## Runtime Model

- PDF indexes are persisted under `PDF_TREE_INDEX_DIR`.
- Docker deployments should mount `PDF_TREE_INDEX_HOST_DIR` to `/app/pdf_tree_index`.
- Markdown and graph indexing remain separate. Do not route PDFs into LightRAG.
- The retriever can use Ollama, LM Studio, OpenRouter, or any OpenAI-compatible endpoint for branch selection. Lexical fallback is still available when the provider is disabled or unreachable.

## Provider Choices

Ollama:

```env
PDF_TREE_RETRIEVAL_ENABLED=true
PDF_TREE_PROVIDER=ollama
PDF_TREE_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

LM Studio:

```env
PDF_TREE_RETRIEVAL_ENABLED=true
PDF_TREE_PROVIDER=lmstudio
PDF_TREE_MODEL=local-model
OPENAI_COMPATIBLE_BASE_URL=http://host.docker.internal:1234/v1
OPENAI_COMPATIBLE_API_KEY=lmstudio
```

OpenRouter:

```env
PDF_TREE_RETRIEVAL_ENABLED=true
PDF_TREE_PROVIDER=openrouter
PDF_TREE_MODEL=openrouter/auto
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_HTTP_REFERER=http://localhost:3030
OPENROUTER_X_TITLE=obsidian_rag
```

## Indexing One PDF

From the host:

```bash
python Scripts/indexing/index_pdf_tree.py "/path/to/vault/file.pdf"
```

Through the gateway:

```bash
curl -s http://localhost:4000/api/v1/pdf-tree/index \
  -H 'Content-Type: application/json' \
  -d '{"pdf_path":"relative/path/in/vault/file.pdf","force":false}'
```

## Querying

The Next.js UI sends PDF tree settings with unified search. Direct API usage:

```bash
curl -s http://localhost:4000/api/v1/pdf-tree/query \
  -H 'Content-Type: application/json' \
  -d '{"query":"What does the report say on page 12?","candidate_paths":["relative/path/in/vault/file.pdf"]}'
```

## Verification

Use the provider status endpoint before enabling PDF tree retrieval broadly:

```bash
curl -s http://localhost:4000/api/v1/pdf-tree/provider-status
```

Expected checks:

- `configured` is true for the selected provider.
- `reachable` is true when the provider is running and network-accessible.
- `baseUrl` points to `host.docker.internal` for host-run Ollama or LM Studio from Docker.
- `model` is the model shown in the UI settings.

## Storage Maintenance

- Rebuild a stale index with `force=true` on `/api/v1/pdf-tree/index`.
- Remove obsolete document directories from `PDF_TREE_INDEX_HOST_DIR` only when the matching source PDF is no longer used.
- Keep `manifest.json` with the document directories; it records source SHA, page count, and index versions.
