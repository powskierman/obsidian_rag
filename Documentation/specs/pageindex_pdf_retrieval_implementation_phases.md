# PageIndex-Style PDF Retrieval Implementation Phases

## Phase 0: Discovery And Baseline

Objective: establish current PDF behavior and create a measurable target.

Tasks:

- Identify the current PDF ingestion path.
- Identify where text extraction, chunking, embeddings, LightRAG insertion, and API query synthesis occur.
- Document current citation behavior for PDF-derived results.
- Select representative PDFs from the vault.
- Create a small eval file with queries, expected source PDFs, expected pages, and expected answers.
- Capture baseline results from the existing retrieval stack.

Deliverables:

- `Documentation/specs/pdf_retrieval_baseline.md`
- `evals/pdf_retrieval_cases.jsonl`
- Baseline metrics for source accuracy, page accuracy, answer quality, and latency.

Exit Criteria:

- There is a repeatable baseline command or script.
- At least 25 PDF questions are represented.
- Current failure modes are documented.

## Phase 1: Provider Abstraction

Objective: add a provider-neutral chat interface for PDF tree indexing and retrieval.

Tasks:

- Add a `ChatProvider` interface.
- Implement provider adapters:
  - Ollama
  - OpenAI-compatible endpoint
  - OpenRouter
- Treat LM Studio as an OpenAI-compatible endpoint.
- Add environment-driven provider selection.
- Add health checks for each provider.
- Add timeout, retry, and structured error handling.
- Add tests with mocked HTTP responses.

Suggested files:

- `src/services/chat_providers.py`
- `src/config/pdf_tree_config.py`
- `tests/test_chat_providers.py`

Deliverables:

- Provider interface.
- Provider implementations.
- Configuration documentation.
- Unit tests.

Exit Criteria:

- Ollama configuration can complete a trivial chat request.
- LM Studio configuration can complete a trivial OpenAI-compatible request.
- OpenRouter configuration can complete a trivial OpenAI-compatible request.
- Provider failures return typed errors without crashing the API gateway.

## Phase 2: PDF Tree Index Store

Objective: create durable storage for PDF tree indexes independent of LightRAG data.

Tasks:

- Add document ID generation based on vault-relative path.
- Add file hash and mtime tracking.
- Define tree schema:
  - node ID
  - title
  - level
  - page start
  - page end
  - text preview
  - child nodes
  - extraction metadata
- Define page artifact schema.
- Add manifest read/write.
- Add invalidation logic.
- Add index directory configuration.
- Add tests for manifest updates and stale detection.

Suggested files:

- `src/services/pdf_tree_store.py`
- `src/models/pdf_tree.py`
- `tests/test_pdf_tree_store.py`

Deliverables:

- Persistent index store.
- Manifest format.
- Stale-index detection.

Exit Criteria:

- A PDF can be registered in the manifest.
- Changed files are detected.
- Index data can be read back into typed models.

## Phase 3: PDF Extraction And Tree Building

Objective: build initial PDF trees from extracted PDF text.

Tasks:

- Choose extraction backend already compatible with the project, or add one deliberately.
- Extract page text with stable page numbers.
- Infer headings using PDF outline/bookmarks when available.
- Fall back to layout/text heuristics when no outline exists.
- Build a first-pass tree without requiring an LLM.
- Optionally use the configured LLM to improve section titles and hierarchy.
- Persist page and tree artifacts.
- Add a CLI or service endpoint for indexing one PDF.

Suggested files:

- `src/services/pdf_tree_extractor.py`
- `src/services/pdf_tree_builder.py`
- `scripts/index_pdf_tree.py`
- `tests/test_pdf_tree_builder.py`

Deliverables:

- PDF-to-tree indexing path.
- Single-document indexing command.
- Sample indexed fixture for tests.

Exit Criteria:

- A representative PDF produces a navigable tree.
- Every leaf node maps to a page span.
- Indexing can run without sending content to a hosted provider when Ollama or no-LLM tree building is configured.

## Phase 4: PDF Tree Retriever

Objective: answer retrieval requests by navigating PDF trees.

Tasks:

- Implement candidate document loading.
- Implement LLM-guided tree traversal:
  - summarize root choices
  - select relevant branches
  - inspect leaf nodes
  - return evidence blocks
- Add deterministic safeguards:
  - max documents
  - max inspected nodes
  - max page text per call
  - timeout
- Add optional reasoning trace capture.
- Add tests with small synthetic trees and mocked provider outputs.

Suggested files:

- `src/services/pdf_tree_retriever.py`
- `tests/test_pdf_tree_retriever.py`

Deliverables:

- PDF tree retrieval service.
- Normalized evidence response.
- Traversal limits and trace support.

Exit Criteria:

- Querying a known PDF returns relevant page-aware evidence.
- Bad provider output is handled gracefully.
- Retrieval has bounded cost and latency.

## Phase 5: API And Query Routing Integration

Objective: expose PDF tree retrieval through the existing query path.

Tasks:

- Add internal endpoint or service method for PDF tree queries.
- Add feature flag check.
- Add rule-based query routing.
- Use existing retrieval first to identify candidate PDFs when no file is named.
- Add hybrid retrieval mode:
  - LightRAG retrieves broad context.
  - PDF tree retriever refines page-specific evidence.
  - answer synthesis receives both evidence sets.
- Normalize PDF tree evidence into existing result schema.
- Add warnings in API response metadata when PDF tree retrieval fails and fallback is used.

Suggested files:

- `src/services/query_router.py`
- `src/services/api_gateway.py`
- `src/integrations/pdf_tree_service.py`
- `tests/test_query_router_pdf_tree.py`

Deliverables:

- API integration.
- Hybrid retrieval path.
- Fallback behavior.

Exit Criteria:

- Existing queries behave the same when the feature flag is disabled.
- PDF-specific queries use tree retrieval when enabled.
- Hybrid queries return both graph/vector and page-aware PDF evidence.
- Provider failures do not break existing search.

## Phase 6: Docker And Configuration

Objective: make the feature deployable in the existing local stack.

Tasks:

- Add config variables to `.env.example`.
- Add index volume for PDF tree data.
- Add optional service container if the project uses service separation.
- Document Ollama host access from Docker.
- Document LM Studio host access from Docker.
- Document OpenRouter configuration.
- Add health checks.

Docker notes:

- On macOS/Windows Docker Desktop, local host services are usually reachable as `host.docker.internal`.
- Ollama from container may need `OLLAMA_BASE_URL=http://host.docker.internal:11434`.
- LM Studio from container may need `OPENAI_COMPATIBLE_BASE_URL=http://host.docker.internal:1234/v1`.

Suggested files:

- `docker-compose.yml`
- `.env.example`
- `Documentation/specs/pdf_tree_provider_setup.md`

Deliverables:

- Local deployment configuration.
- Provider setup docs.
- Health check endpoint.

Exit Criteria:

- Ollama works from Docker.
- LM Studio works from Docker.
- OpenRouter works from Docker.
- Missing provider configuration is reported clearly.

## Phase 7: Evaluation And Tuning

Objective: decide whether the feature improves real retrieval quality enough to keep.

Tasks:

- Run baseline eval against existing retrieval.
- Run eval against PDF tree retrieval only.
- Run eval against hybrid retrieval.
- Compare local models:
  - small Ollama model
  - stronger Ollama model if available
  - LM Studio model
  - OpenRouter model
- Tune:
  - routing rules
  - traversal prompts
  - max nodes inspected
  - page text window sizes
  - candidate PDF selection
- Record cost and latency.

Deliverables:

- `Documentation/specs/pdf_tree_eval_results.md`
- Updated default configuration recommendations.

Exit Criteria:

- Hybrid retrieval improves page/section accuracy over baseline on the eval set.
- Latency is acceptable for interactive use or documented as a slower high-accuracy mode.
- Local model quality is characterized honestly.

## Phase 8: Hardening

Objective: make the feature robust enough for regular use.

Tasks:

- Add concurrency limits for indexing and retrieval.
- Add cancellation/timeout propagation.
- Add corrupt PDF handling.
- Add support for partial indexes.
- Add debug trace redaction.
- Add migration/version handling for index schemas.
- Add docs for rebuilding indexes.
- Add regression tests for routing and fallback.

Deliverables:

- Production-ready error handling.
- Operational docs.
- Regression tests.

Exit Criteria:

- Failed or corrupt PDFs do not break vault indexing.
- Index schema changes are handled cleanly.
- Logs are useful without leaking secrets or excessive document content.

## Suggested Milestone Order

1. Provider abstraction.
2. Index store.
3. Minimal PDF extraction and tree building.
4. Single-PDF retrieval command.
5. API integration behind feature flag.
6. Hybrid routing.
7. Docker/provider setup.
8. Eval and tuning.
9. Hardening.

## Minimal Viable Implementation

The smallest useful version is:

- Feature flag.
- Ollama and OpenAI-compatible provider adapters.
- PDF extraction with page numbers.
- Simple heading/page tree.
- Single-PDF tree query.
- Existing query fallback.
- Source path and page citation in the final evidence.

OpenRouter support can be added immediately after OpenAI-compatible support because it uses the same API shape plus headers.

## Key Risks

- Local models may be too weak for reliable tree traversal on complex documents.
- PDF extraction quality may dominate retrieval quality.
- LLM-guided traversal can be slower than vector search.
- Hosted providers can leak document excerpts if users configure them without understanding the privacy impact.
- Hybrid routing can over-trigger PDF tree retrieval and increase latency.

## Recommended Defaults

- `PDF_TREE_RETRIEVAL_ENABLED=false`
- `PDF_TREE_PROVIDER=ollama`
- `PDF_TREE_MODEL=llama3.1:8b`
- `PDF_TREE_MAX_DOCUMENTS_PER_QUERY=3`
- `PDF_TREE_INCLUDE_REASONING_TRACE=false`
- Prefer hybrid retrieval only after eval demonstrates quality improvement.
