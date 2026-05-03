# PageIndex-Style PDF Retrieval Specification

## Purpose

Add an optional PDF retrieval backend to `obsidian_rag` that improves long, structured PDF question answering by indexing PDFs into navigable document trees instead of relying only on embedding similarity over chunks.

The feature must support user-selectable LLM providers:

- Ollama
- LM Studio
- OpenRouter
- Any OpenAI-compatible endpoint configured by base URL and API key

This should complement the existing LightRAG/embedding retrieval path, not replace it. LightRAG PDF indexing is decommissioned; LightRAG remains for Markdown notes and graph-style vault retrieval.

## Goals

- Improve retrieval precision for long PDFs, especially reports, manuals, papers, filings, books, and documents with headings, tables, appendices, or page-specific evidence.
- Return page-aware and section-aware citations.
- Allow local/private model use through Ollama and LM Studio.
- Allow hosted model routing through OpenRouter.
- Keep the existing vault-wide retrieval behavior intact.
- Make PDF tree indexing optional and independently rebuildable.
- Support hybrid answers that combine LightRAG context with PDF tree evidence.

## Non-Goals

- Replace LightRAG as the default retriever.
- Re-enable PDF indexing inside LightRAG.
- Replace the existing embedding service.
- Build a general-purpose vector database.
- Guarantee perfect table extraction from all PDFs.
- Require a single model provider.
- Require cloud APIs for local-first users.

## User Stories

- As a user, I can ask a question about a long PDF and get the answer from the correct page or section.
- As a user, I can run the PDF retrieval feature using Ollama without external LLM calls.
- As a user, I can run the same feature against LM Studio using its OpenAI-compatible server.
- As a user, I can use OpenRouter for stronger hosted models when local models are insufficient.
- As a user, I can disable PageIndex-style retrieval and keep current behavior.
- As a user, I can rebuild PDF tree indexes without reindexing the entire vault graph.

## Architecture

Add a PDF tree retrieval sidecar beside the existing retrieval services.

Recommended components:

- `pdf-tree-service`: indexes PDFs into hierarchical trees and answers PDF-focused retrieval requests.
- `llm-provider-adapter`: normalizes Ollama, LM Studio, OpenRouter, and OpenAI-compatible chat completions.
- `pdf-index-store`: stores tree indexes, page spans, source metadata, and extraction artifacts.
- `query-router`: decides whether to use LightRAG, PDF tree retrieval, or both.
- `answer-synthesizer`: merges retrieved PDF evidence with existing RAG context.

LightRAG must not index PDFs. Markdown notes continue through LightRAG; PDFs are handled by the PDF tree service.

## Retrieval Flow

1. User sends a query through the existing API gateway or MCP surface.
2. Query router classifies the request:
   - General vault question: use current retrieval path.
   - PDF-specific question: use PDF tree retrieval.
   - Ambiguous or cross-document question: use hybrid retrieval.
3. For PDF tree retrieval:
   - Identify candidate PDFs by filename, vault path, metadata, prior LightRAG hits, or lexical search.
   - Load the stored tree index for each candidate PDF.
   - Use the configured LLM provider to navigate the tree.
   - Return selected sections, page spans, extracted text, and reasoning trace metadata.
4. Existing answer generation receives normalized evidence blocks.
5. Final answer includes source PDF path, page number, and section/title when available.

## Indexing Flow

1. PDF files are discovered during PDF tree indexing, not LightRAG indexing.
2. Eligible PDFs are sent to `pdf-tree-service`.
3. The service extracts:
   - page text
   - page numbers
   - headings or inferred section hierarchy
   - tables where feasible
   - document metadata
4. The service builds a hierarchical tree:
   - document root
   - major sections
   - subsections
   - page spans
   - leaf text blocks
5. Tree index is persisted separately from LightRAG graph/vector data.
6. Index metadata records source file hash, mtime, provider/model used, extraction version, and index schema version.

## Provider Requirements

All providers should expose a common interface:

```python
class ChatProvider:
    async def complete(self, messages, *, model, temperature=0, max_tokens=None, timeout=None):
        ...
```

### Ollama

Configuration:

- `PDF_TREE_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://localhost:11434`
- `PDF_TREE_MODEL=llama3.1:8b`

Use Ollama's chat API directly or through LiteLLM.

Requirements:

- No API key required by default.
- Must support configurable base URL.
- Must provide clear health checks for missing model or unreachable daemon.

### LM Studio

Configuration:

- `PDF_TREE_PROVIDER=openai_compatible`
- `OPENAI_COMPATIBLE_BASE_URL=http://localhost:1234/v1`
- `OPENAI_COMPATIBLE_API_KEY=lm-studio`
- `PDF_TREE_MODEL=local-model`

Requirements:

- Use OpenAI-compatible chat completions.
- API key may be optional but should be accepted for compatibility.
- Health check should call `/v1/models` or a minimal chat completion.

### OpenRouter

Configuration:

- `PDF_TREE_PROVIDER=openrouter`
- `OPENROUTER_API_KEY=...`
- `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1`
- `PDF_TREE_MODEL=anthropic/claude-3.5-sonnet` or another supported model

Requirements:

- Use OpenAI-compatible chat completions.
- Support optional OpenRouter headers:
  - `HTTP-Referer`
  - `X-Title`
- Never log API keys.

### Generic OpenAI-Compatible

Configuration:

- `PDF_TREE_PROVIDER=openai_compatible`
- `OPENAI_COMPATIBLE_BASE_URL=...`
- `OPENAI_COMPATIBLE_API_KEY=...`
- `PDF_TREE_MODEL=...`

## Configuration

Suggested environment variables:

```env
PDF_TREE_RETRIEVAL_ENABLED=false
PDF_TREE_PROVIDER=ollama
PDF_TREE_MODEL=llama3.1:8b
PDF_TREE_INDEX_DIR=/app/pdf_tree_index
PDF_TREE_MAX_DOCUMENTS_PER_QUERY=5
PDF_TREE_MAX_PAGES_PER_DOCUMENT=500
PDF_TREE_TIMEOUT_SECONDS=120
PDF_TREE_INCLUDE_REASONING_TRACE=false

OLLAMA_BASE_URL=http://localhost:11434

OPENAI_COMPATIBLE_BASE_URL=http://localhost:1234/v1
OPENAI_COMPATIBLE_API_KEY=

OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_API_KEY=
OPENROUTER_HTTP_REFERER=
OPENROUTER_X_TITLE=obsidian_rag
```

## API Contract

Add or extend an internal retrieval endpoint:

```http
POST /pdf-tree/query
```

Request:

```json
{
  "query": "What does the PDF say about CAR-T eligibility?",
  "candidate_paths": ["Medical/Yescarta.pdf"],
  "max_documents": 3,
  "include_trace": false
}
```

Response:

```json
{
  "answer_context": [
    {
      "source_type": "pdf_tree",
      "path": "Medical/Yescarta.pdf",
      "title": "Yescarta Prescribing Information",
      "section": "Patient Selection",
      "page_start": 12,
      "page_end": 13,
      "text": "...",
      "score": 0.84,
      "metadata": {
        "tree_node_id": "node_123",
        "provider": "ollama",
        "model": "llama3.1:8b"
      }
    }
  ]
}
```

The API gateway should normalize this into the same evidence format used by existing answer synthesis.

## Storage

Persist indexes under `PDF_TREE_INDEX_DIR`.

Recommended files:

- `manifest.json`: document registry, file hashes, schema versions.
- `<document_id>/tree.json`: hierarchical document tree.
- `<document_id>/pages.jsonl`: page text and extraction metadata.
- `<document_id>/tables.jsonl`: optional extracted table artifacts.
- `<document_id>/trace/`: optional debug traces.

Indexes should be invalidated when:

- file hash changes
- extraction version changes
- tree schema version changes
- forced rebuild is requested

Provider/model changes should not automatically invalidate indexes unless the model is used to create the tree structure. If the LLM contributes to tree construction, record the provider/model in index metadata and make invalidation configurable.

## Query Routing

Initial routing can be rule-based:

- Use PDF tree retrieval when the query mentions a `.pdf` filename or a known PDF title.
- Use PDF tree retrieval when existing retrieval returns PDF documents as top candidates.
- Use hybrid retrieval when query contains terms like "page", "section", "table", "figure", "appendix", "in the PDF", "manual", "paper", or "report".
- Fall back to current retrieval when PDF tree retrieval is disabled, unavailable, or returns no evidence.

Later routing can use a small classifier prompt.

## Observability

Log structured events:

- provider selected
- model selected
- candidate PDFs
- indexing duration
- query duration
- pages inspected
- sections selected
- errors by provider

Do not log:

- API keys
- full PDF text by default
- full prompts unless debug tracing is explicitly enabled

## Error Handling

Required fallback behavior:

- If provider is unavailable, return a retriever warning and continue with existing LightRAG retrieval.
- If a PDF has no tree index, optionally enqueue or trigger indexing, then fall back to current retrieval.
- If local model context length is too small, return a clear configuration error.
- If a query times out, return partial evidence only when it is safe and marked as partial.

## Security And Privacy

- Default provider should be local-first: Ollama.
- Hosted providers must be opt-in.
- API keys must come from environment variables or secret management.
- Do not send PDF contents to OpenRouter unless `PDF_TREE_PROVIDER=openrouter` or equivalent hosted provider is explicitly configured.
- Add documentation warning that hosted providers receive document excerpts or indexing prompts.

## Evaluation

Create a PDF retrieval eval set before enabling by default.

Minimum eval:

- 20-50 representative PDFs.
- 50-150 questions.
- Expected answer text.
- Expected source PDF.
- Expected page or section.

Metrics:

- correct source document
- correct page or section
- answer faithfulness
- citation accuracy
- latency
- local model failure rate
- hosted model cost

## Acceptance Criteria

- Feature can be disabled with `PDF_TREE_RETRIEVAL_ENABLED=false`.
- Ollama works with no external API calls.
- LM Studio works through OpenAI-compatible configuration.
- OpenRouter works through OpenAI-compatible configuration.
- PDF evidence includes source path and page span.
- Existing non-PDF retrieval behavior remains unchanged when feature is disabled.
- Failed PDF tree retrieval falls back to current retrieval.
- Index rebuild can be run independently from full vault reindexing.
- Basic tests cover provider selection, routing fallback, and response normalization.
