# PDF Retrieval Baseline

## Current Behavior

`obsidian_rag` currently has multiple PDF-aware paths, but LightRAG PDF indexing is decommissioned because single-PDF indexing latency is not operationally viable. PDF retrieval work should move to the PDF tree pipeline.

Known ingestion paths:

- `src/indexing/index_vault.py`
  - supports `.md` and `.pdf`
  - extracts PDF text with `pypdf.PdfReader`
  - prefixes extracted page text with `[Page N]`
  - cleans simple page-number artifacts before embedding/indexing
- `src/integrations/lightrag_service.py`
  - indexes Markdown only for LightRAG
  - rejects or ignores `.pdf` extension requests
  - retains legacy PDF extraction code only as unreachable compatibility code until it can be removed safely
- `src/services/networkx_graph_builder.py`
  - creates graph nodes for `.pdf` files
  - lets graph retrieval return PDFs as source nodes
- `src/services/api_gateway.py`
  - normalizes PDF-derived retrieval sources into existing answer/source responses

This means current PDF answers should be evaluated against the existing vector/graph behavior and then compared against the new PDF tree pipeline. LightRAG is no longer a valid PDF retrieval baseline.

## Baseline Cases

The scaffold file is:

```text
evals/pdf_retrieval_cases.example.jsonl
```

Copy it to a local eval file with real vault PDFs before scoring:

```text
evals/pdf_retrieval_cases.local.jsonl
```

Each JSONL row supports:

- `id`
- `query`
- `expected_source`
- `expected_page`
- `expected_answer_contains`
- `mode`
- `depth`
- `sources`
- `max_results`
- `llm_provider`
- `model`

## Baseline Command

Run against the existing API gateway:

```bash
python Scripts/benchmarks/run_pdf_retrieval_baseline.py \
  --cases evals/pdf_retrieval_cases.local.jsonl \
  --gateway-url http://localhost:4000 \
  --output Documentation/specs/pdf_retrieval_baseline_results.local.json
```

## Metrics

The baseline script records:

- source accuracy: expected PDF path appears in returned sources
- page accuracy: expected page marker appears in the response payload
- answer contains hit: required answer terms appear in the answer text
- latency per query
- returned source paths
- answer preview

## Expected Phase 0 Outcome

Phase 0 is complete when:

- the current PDF ingestion path is documented
- an eval JSONL format exists
- a baseline runner can call the current retrieval stack
- later PDF tree retrieval phases can compare against the same cases

## Known Current Failure Modes To Validate

- Similar chunks from the wrong PDF section may outrank the correct page.
- Page markers can be lost or omitted from final synthesized answers.
- Long PDFs are not indexed into LightRAG because that path is decommissioned.
- Scanned/image PDFs may produce little or no text with `pypdf`.
- PDF table structure is mostly flattened during text extraction.
