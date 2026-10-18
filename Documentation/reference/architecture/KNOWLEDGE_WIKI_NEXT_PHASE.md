# Next Phase: Maintained Knowledge Wiki

> **Status: Proposed next phase. Not implemented.**
> Recorded: 2026-10-18.
> Basis: source review of local commit `e460eaeb1a93b0cbecd1fb1f789e41ecdf8459a0`, OKF v0.2, and Karpathy's LLM Wiki pattern.
> This proposal records a design recommendation. It does not report measured improvements or a completed implementation.

## Project folder

Plan this phase in the current local working copy at `/Users/michel/dev/obsidian_rag`. The vault and database paths are separate settings. See the [documentation index](../../README.md#project-folder) for the project folder reference.

## Recommendation

Extend `obsidian_rag` with a small, maintained knowledge wiki. Keep the existing retrieval engine. Use the wiki workflow to maintain selected concept pages. Use Open Knowledge Format (OKF) metadata where it helps with source tracking, verification, freshness, and exchange.

The result has three complementary parts:

| Part | Responsibility |
| --- | --- |
| Original vault | Preserve source notes and attachments as evidence. |
| Generated wiki | Store readable synthesis with links to the original evidence. |
| Existing retrieval engine | Search both layers and produce answers with clear source attribution. |

The first pilot should cover one bounded topic that the user revisits often. Its value must be measured before wider adoption.

## Why this is the next phase

`obsidian_rag` already provides vector retrieval, graph expansion, full-note review, and iterative research. Optional PDF tree retrieval supplies section and page references. Its derived indexes retain processed knowledge. It is more capable than basic retrieval of isolated document chunks.

The missing layer is maintained, readable synthesis. A repeated question still requires substantial assembly of evidence during the query. A wiki could retain a useful comparison or topic summary and update it when its sources change.

Karpathy's pattern supplies the maintenance workflow: ingest, query, and periodic wiki checks. OKF supplies a portable document format. Neither replaces the retrieval engine. Neither establishes better answer quality or lower cost for this vault without evaluation.

## Current implementation and gaps

| Area | Current evidence | Work proposed for this phase |
| --- | --- | --- |
| Query entry points | [API gateway](../../../src/services/api_gateway.py) supports `ask`, `research`, and WebSocket `investigate`. | Retrieve original evidence and generated synthesis through the existing interfaces. |
| Capture and editing | [Unified MCP server](../../../src/mcp/obsidian_rag_unified_mcp.py) provides capture, note creation, and note updates. | Define an ingest workflow that maintains related pages, an index, and a change log. |
| Inbox automation | [Second Brain Architecture](SECOND_BRAIN_ARCHITECTURE.md) marks its larger automation loop as a proposal. | Start with explicit, user-directed ingestion. A background watcher is optional later work. |
| Metadata | The [capture template](../../operations/notes/New%20Note%20Template.md) has no required OKF `type`. | Define templates for generated pages with the selected OKF fields. |
| Graph links | The [structural graph parser](../../../src/services/networkx_graph_builder.py) extracts Obsidian wikilinks. | Add support for standard Markdown links and OKF bundle path rules. |
| Maintenance | Index checks and repeated-content checks exist. | Add checks for unsupported claims, contradictions, stale synthesis, and missing source links. |

## Proposed pilot design

### Source boundary

Treat source notes and attachments as read-only inputs to wiki generation. Place generated pages in a distinct, configurable folder. Select the folder in the implementation specification. Preserve raw external material separately from its generated summary when it is ingested.

Track source identity and source changes. Record a source fingerprint as an extension field or in a local manifest. A changed source must flag its dependent synthesis for review. An indexing timestamp alone does not establish that a claim is current.

### Wiki workflow

Support source summary pages, concept pages, entity pages, and useful comparison pages. Maintain `index.md` for navigation and `log.md` for change history. Preserve unresolved disagreements with links to each source.

An explicit ingest run should follow this sequence:

1. Read the selected source.
2. Present its key findings.
3. Create or revise its source summary page.
4. Update affected concept and entity pages.
5. Update the wiki index.
6. Append a change-log entry.

A useful query answer can become a wiki page through an explicit save action. Periodic wiki checks should identify stale claims, contradictions, orphan pages, missing references, and evidence gaps. These checks complement index-health checks.

### Metadata and OKF compatibility

Use OKF v0.2 as the reference format for generated pages. Include `type`, `title`, and `description` in pilot templates. Use `sources`, `generated`, `verified`, `status`, and `stale_after` when applicable.

OKF requires only `type` for an ordinary concept document. Its trust fields are optional. Therefore, format conformance is distinct from factual verification. Record `verified` only after an actual verification event. Do not infer human review from successful generation or indexing.

Keep existing vault metadata intact. Preserve unknown fields during document updates. Support standard Markdown links alongside Obsidian wikilinks. Resolve relative links and bundle-root links against their correct roots. A conversion of the whole vault is outside this pilot.

### Retrieval and attribution

Identify each result as original evidence or generated synthesis. Keep links from generated claims to their underlying evidence. Do not count a source note and a summary derived from that note as independent corroboration.

Keep direct retrieval of original notes and PDF evidence available. Surface stale or unverified synthesis clearly. Define retrieval filters and update rules in the specification before implementation. Reuse the current gateway and indexing boundaries.

## Delivery sequence

| Stage | Deliverable |
| --- | --- |
| Specification | Spec Kit spec, plan, and tasks for the selected topic, folder, metadata contract, source tracking, update behavior, and evaluation criteria. |
| Pilot | Explicit ingest, page maintenance, query-answer saving, and wiki checks over the bounded source set. |
| Integration | Markdown link support, source-layer labels, and incremental indexing of generated pages through the existing stack. |
| Evaluation | A comparison of retrieval over original evidence alone and retrieval with the generated wiki. |

Keep the existing `ask`, `research`, and `investigate` interfaces. Follow the [project constitution](../governance/PROJECT_CONSTITUTION.md) for service boundaries, privacy, and independent indexing. Source editing, broad vault reorganization, graph-stack retirement, new hosted services, and automatic bulk ingestion are separate work.

## Acceptance criteria for expansion

Define the evaluation questions and numeric thresholds in the specification before the pilot runs. Include repeated synthesis questions and questions that require exact source details.

The pilot must demonstrate these outcomes:

- Original source content remains unchanged by wiki generation.
- Generated claims retain usable links to their evidence.
- A changed source flags the affected synthesis for review.
- Conflicting sources remain visible without invented agreement.
- Repeated ingestion avoids duplicate pages and duplicate log entries for an unchanged run.
- Retrieval distinguishes generated synthesis from original evidence.
- Existing search modes continue to satisfy the applicable project checks.
- Removing the pilot wiki restores retrieval over the original evidence.

Measure answer correctness, citation accuracy, evidence coverage, query latency, generation cost, and maintenance effort. Measure ingestion cost separately from query cost. Record regressions and unresolved errors. Expand only if the pilot demonstrates useful gains at an acceptable maintenance cost.

## Decisions for the implementation specification

- Pilot topic and source set.
- Generated wiki folder and document identity rules.
- Local model or existing provider for wiki maintenance.
- Source fingerprint storage and dependency tracking.
- Verification workflow and freshness policy.
- Retrieval defaults for original evidence and generated synthesis.
- Private version history and rollback method for generated pages.

These decisions remain open. This document does not start ingestion, indexing, deployment, or vault migration.

## References

External references reviewed on 2026-10-18:

- [Open Knowledge Format repository](https://github.com/GoogleCloudPlatform/open-knowledge-format)
- [Open Knowledge Format v0.2 specification](https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md)
- [Karpathy: LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

Recheck the OKF version before implementation. Its reference agent is one example producer; this proposal does not require its BigQuery or Gemini workflow.

Related project documentation:

- [Documentation index](../../README.md)
- [Second Brain Architecture](SECOND_BRAIN_ARCHITECTURE.md)
- [Capture and Inbox](CAPTURE_AND_INBOX.md)
- [Search Architecture](../search/SEARCH_ARCHITECTURE.md)
- [Indexing Strategy](../../operations/indexing/INDEXING_STRATEGY.md)
