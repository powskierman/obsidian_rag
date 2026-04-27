# **OC-SPEC-MOVIES — Speckit Artifacts for Movie Catalog Subsystem**





This document contains draft Speckit-aligned artifacts for introducing a movie-catalog subsystem into obsidian_rag.









# **1.** 

# **spec.md**



# Specification: Movie Catalog Subsystem for Obsidian RAG

**Spec ID**: `OC-SPEC-MOVIES-v1.0.0`   **Project**: `obsidian_rag`   **Status**: Draft   **Date**: 2026-04-11

## 1. Summary

Introduce a movie-catalog subsystem into `obsidian_rag` that ingests movie records from multiple sources, resolves each movie to a canonical identifier, stores canonical metadata in a durable structured store, and generates Obsidian notes as a projection layer for browsing, linking, and retrieval.

The subsystem must support:

- ingestion from Apple-exported library data and NAS-origin title lists
- canonical movie identity using `imdb_id` as the primary external identifier
- optional storage of `tmdb_id` and other external IDs
- deduplication and reconciliation across sources
- franchise / collection grouping
- structured note generation into the Obsidian vault
- future graph integration using canonical IDs for node identity

## 2. Problem Statement

Current movie data exists in heterogeneous formats with inconsistent naming, mixed completeness, duplicate titles, alternate spellings, year ambiguity, and source-specific metadata. Titles alone are not reliable identifiers. The system needs a canonical, repeatable, auditable pipeline that transforms raw movie lists into a stable, queryable corpus aligned with `obsidian_rag` architecture.

## 3. Goals

1. Establish a canonical identity model for movies.
2. Separate the system of record from Obsidian presentation.
3. Preserve provenance from Apple and NAS sources.
4. Support deterministic regeneration of Obsidian movie notes.
5. Prepare the dataset for future graph / RAG / entity-linking workflows.
6. Maintain Spec-Driven Development discipline consistent with project governance.

## 4. Non-Goals

1. Building a full streaming-monitoring service.
2. Creating a complete media server or playback manager.
3. Real-time bidirectional syncing from Obsidian note edits back into the canonical store.
4. Exhaustive support for TV series, episodes, and shorts in this phase.
5. Automatic poster downloading in Phase 1.

## 5. Stakeholders

- Primary user: repository owner / vault owner
- System consumers: Obsidian, Dataview dashboards, future MCP / RAG tooling
- Maintenance agent: implementation agents operating under Speckit governance

## 6. Core Requirements

### 6.1 Canonical identity

- Every resolved movie MUST have an internal canonical ID.
- Every resolved movie SHOULD have an `imdb_id`.
- `imdb_id` SHALL be the preferred external identity anchor.
- `tmdb_id` SHOULD be stored when available.
- Title text MUST NOT be used as the primary identity key.

### 6.2 Source ingestion

The system MUST ingest from:

- Apple movie export (CSV or equivalent structured export)
- NAS title list (plain text)

The system MUST preserve source provenance per movie.

### 6.3 Canonical store

The system MUST maintain a structured canonical store outside the Obsidian note layer.

Acceptable Phase 1 implementations:

- SQLite
- DuckDB
- versioned structured files if strongly justified

### 6.4 Reconciliation and deduplication

The system MUST:

- normalize titles for matching
- use year-aware matching where possible
- distinguish probable duplicates from probable remakes / alternate versions
- preserve unresolved ambiguity for manual review

### 6.5 Metadata enrichment

The system SHOULD enrich canonical records with:

- release year
- directors
- main cast
- genres
- runtime
- IMDb rating
- collection / franchise membership

### 6.6 Obsidian projection

The system MUST generate deterministic movie notes in the vault.

Each generated movie note MUST include frontmatter for:

- internal canonical ID
- `imdb_id`
- `tmdb_id` when available
- title
- year
- provenance
- collection
- quality tracking fields
- user curation fields such as `your_rating` and `watched`

### 6.7 Graph / RAG compatibility

Future graph nodes MUST be keyed by canonical IDs rather than human-readable titles.

### 6.8 Auditability

The pipeline MUST preserve sufficient input/output traceability to explain:

- where a movie came from
- how it was matched
- whether metadata was inferred or sourced
- whether manual review is required

## 7. Constraints

1. The Obsidian vault is not the canonical system of record.
2. Generated notes must be reproducible.
3. Manual edits inside generated note regions must not be silently destroyed unless explicitly designed.
4. Phase 1 should prefer deterministic and auditable logic over high-risk automation.
5. External metadata lookups must be cacheable and rate-limit aware.

## 8. Data Model

### 8.1 Canonical movie entity

Minimum fields:

- `id`
- `type = movie`
- `title`
- `year`
- `imdb_id`
- `tmdb_id`
- `provenance`
- `match_status`
- `duplicate_group`
- `version_notes`
- `collection`
- `quality_apple`
- `quality_nas`
- `top_250`
- `your_rating`
- `watched`

### 8.2 Person entity (future-compatible)

- `id`
- `type = person`
- `name`
- `imdb_id` optional

### 8.3 Relationship model (future phase)

- `ACTED_IN`
- `DIRECTED`
- `BELONGS_TO_COLLECTION`

## 9. Proposed Vault Layout

```text
Media/
  Movies/
    Blade Runner (1982).md
  People/
    Harrison Ford.md
  Collections/
    Star Wars.md
```

Phase 1 requires only Media/Movies/.





## **10. Note Frontmatter Contract**





Example:

```
id: movie:tt0083658
kind: movie
title: Blade Runner
year: 1982
imdb_id: tt0083658
tmdb_id: 78
provenance:
  - Apple
  - NAS
collection: Blade Runner
quality_apple: HD
quality_nas: unknown
top_250: true
your_rating:
watched: false
match_status: resolved
version_notes:
```

Additional frontmatter MAY be added only through governed schema evolution.





## **11. User Stories**





1. As a user, I want one canonical record for each movie even when the title appears differently across sources.
2. As a user, I want my Apple and NAS ownership preserved without duplicate notes.
3. As a user, I want generated movie notes in Obsidian for browsing and Dataview dashboards.
4. As a future RAG consumer, I want graph nodes keyed by stable IDs instead of title strings.
5. As a maintainer, I want unresolved matches clearly surfaced for manual review.







## **12. Acceptance Criteria**





1. Input Apple CSV and NAS TXT produce a canonical store and generated notes.
2. At least 95% of straightforward title matches are resolved automatically in the seed dataset.
3. Ambiguous titles are flagged instead of silently merged.
4. Re-running the pipeline is idempotent for unchanged inputs.
5. Generated note paths and IDs are stable across runs.
6. Provenance is preserved for every canonical movie.
7. Obsidian notes are generated from the canonical store, not vice versa.







## **13. Risks**





- ambiguous titles without year
- remakes sharing identical titles
- collection anchor entries that are not specific films
- metadata source drift
- accidental conflation of bundles and movies







## **14. Open Questions**





1. Is tmdb_id required in Phase 1 or merely preferred?
2. Should people and collection notes be generated in Phase 1 or Phase 2?
3. Should generated notes include embedded poster/image links?
4. What exact integration point in existing obsidian_rag ingestion is preferred?







## **15. Implementation Principle**





The system SHALL treat structured canonical storage as truth and Obsidian notes as deterministic projections.

# 2. `plan.md`

# Implementation Plan: Movie Catalog Subsystem for Obsidian RAG

**Plan ID**: `OC-PLAN-MOVIES-v1.0.0`   **Spec**: `OC-SPEC-MOVIES-v1.0.0`   **Date**: 2026-04-11

## 1. Objective

Implement a governed movie-catalog subsystem in `obsidian_rag` with:

- canonical ID resolution
- structured storage
- deterministic Obsidian projection
- future graph compatibility

## 2. Architectural Decision

### Decision

Use a structured canonical store outside the vault and generate movie notes into the vault.

### Rationale

This preserves identity integrity, avoids title-based duplication, supports deterministic regeneration, and aligns with future graph / RAG evolution.

## 3. Deliverables

1. Canonical schema definition
2. Ingestion pipeline for Apple CSV and NAS TXT
3. Resolution / matching layer
4. Enrichment layer
5. Note generation layer
6. Review report for unresolved/ambiguous titles
7. Tests and verification outputs

## 4. Phases

### Phase 1 — Schema and storage

- define canonical movie schema
- choose SQLite or DuckDB
- implement migration/bootstrap logic

### Phase 2 — Input ingestion

- parse Apple CSV
- parse NAS TXT
- normalize fields into staging records
- preserve raw source provenance

### Phase 3 — Matching and reconciliation

- implement title normalization
- extract and compare years
- assign canonical IDs
- classify: resolved / ambiguous / collection-anchor / invalid

### Phase 4 — Metadata enrichment

- attach `imdb_id`
- attach `tmdb_id` when available
- enrich title, year, runtime, genre, director, cast, rating
- cache metadata results

### Phase 5 — Note generation

- generate `Media/Movies/*.md`
- write governed frontmatter
- include generated body template sections
- ensure idempotent output paths

### Phase 6 — Reporting and verification

- produce unresolved-title review file
- generate summary metrics
- run repository verification workflow

## 5. Proposed File / Module Layout

```text
obsidian_rag/
  src/
    movies/
      schema.py
      ingest_apple.py
      ingest_nas.py
      normalize.py
      match.py
      enrich.py
      project_obsidian.py
      report.py
  data/
    movies/
      canonical.db
      cache/
  templates/
    movies/
      movie_note.md.j2
  reports/
    movies/
      unresolved_matches.md
```

Adjust actual paths to existing repository conventions.





## **6. Detailed Recommendations**







### **6.1 Store design**





Use SQLite unless repository conventions strongly favor another local structured store.



Rationale:



- deterministic
- portable
- inspectable
- simple joins
- easy caching







### **6.2 Matching strategy**





Use a two-stage match:



1. deterministic normalization + year-based exact candidate narrowing
2. fuzzy fallback with explicit confidence thresholds





Never auto-merge low-confidence ambiguous candidates.





### **6.3 Canonical ID strategy**





Internal ID format:



- movie:<imdb_id> when resolved
- movie:local:<slug> for unresolved placeholders pending review







### **6.4 Obsidian note generation**





Generated notes should contain:



- governed frontmatter
- concise metadata block
- provenance summary
- review markers when ambiguity exists







### **6.5 Manual review**





Maintain an explicit unresolved report rather than burying failures in logs.





## **7. Testing Strategy**







### **Unit tests**





- title normalization
- year extraction
- duplicate classification
- ID stability
- note filename stability







### **Integration tests**





- Apple CSV + NAS TXT → canonical store
- canonical store → generated notes
- rerun idempotency







### **Safety checks**





- no duplicate canonical IDs
- no note collisions for distinct movies
- ambiguous titles remain unresolved until reviewed







## **8. Risks and Mitigations**







### **Risk: Ambiguous titles**





Mitigation: require year-aware matching and manual review queue.





### **Risk: Bundle / franchise placeholders in source data**





Mitigation: classify non-film entries separately and do not force them into movie entities.





### **Risk: Schema drift**





Mitigation: freeze Phase 1 schema and govern additions explicitly.





### **Risk: Generated note overwrite concerns**





Mitigation: either regenerate complete files deterministically or isolate generated regions from manual sections.





## **9. Logging and auditability**





- no raw source dumps in logs by default
- prefer IDs, counts, paths, and match summaries
- enable verbose debug logging only when explicitly requested







## **10. Exit Criteria**





The phase is complete when:



1. canonical store exists and is populated from both sources
2. movie notes are generated deterministically
3. unresolved titles are explicitly reported
4. verification checks pass
5. documentation aligns with project governance





# 3. `tasks.md`

# Tasks: Movie Catalog Subsystem for Obsidian RAG

**Tasks ID**: `OC-TASKS-MOVIES-v1.0.0`   **Spec**: `OC-SPEC-MOVIES-v1.0.0`   **Plan**: `OC-PLAN-MOVIES-v1.0.0`

## Phase 1 — Foundation

-  Create feature branch for movie subsystem work
-  Confirm repository path conventions for new subsystem modules
-  Add canonical schema definition for movie records
-  Decide and document canonical store technology
-  Add migration/bootstrap creation logic for canonical store

## Phase 2 — Ingestion

-  Implement Apple CSV parser
-  Implement NAS TXT parser
-  Normalize both sources into a shared staging model
-  Preserve source-specific provenance fields
-  Add fixtures for representative Apple/NAS samples

## Phase 3 — Matching / Resolution

-  Implement title normalization helpers
-  Implement year extraction helpers
-  Implement deterministic match pass
-  Implement fuzzy fallback with thresholding
-  Classify unresolved, ambiguous, and collection-anchor records
-  Add duplicate / alternate-version logic

## Phase 4 — Enrichment

-  Define metadata provider abstraction
-  Implement provider caching
-  Resolve and store `imdb_id`
-  Resolve and store `tmdb_id` when available
-  Populate director / cast / genre / runtime / rating
-  Add `top_250` support

## Phase 5 — Obsidian Projection

-  Define movie note frontmatter schema
-  Create note template
-  Implement deterministic note path generation
-  Generate `Media/Movies/*.md`
-  Add provenance and review markers to note output

## Phase 6 — Reporting

-  Generate unresolved match report
-  Generate summary counts report
-  Document manual review workflow

## Phase 7 — Verification

-  Add unit tests for normalization and matching
-  Add integration tests for end-to-end flow
-  Test idempotent reruns
-  Verify no duplicate canonical IDs
-  Run project-required preflight and verification commands
-  Capture stdout/stderr and exit codes per house rules

## Phase 8 — Documentation

-  Add subsystem README / operator notes if repository conventions require it
-  Cross-link spec, plan, tasks, and reports
-  Document schema evolution rules for future movie fields



# **4. Compliance Matrix**

# Compliance Matrix: Movie Catalog Subsystem

| Requirement                   | Source    | Planned Implementation                       | Verification                         |
| ----------------------------- | --------- | -------------------------------------------- | ------------------------------------ |
| Canonical ID required         | Spec §6.1 | Internal ID + `imdb_id` anchor               | Unit + integration tests             |
| Title not primary identity    | Spec §6.1 | Matching layer then canonical ID assignment  | Code review + tests                  |
| Apple and NAS ingestion       | Spec §6.2 | Separate parsers into shared staging model   | Integration test                     |
| Provenance preserved          | Spec §6.2 | Per-record provenance fields                 | Fixtures + generated note assertions |
| Canonical store outside vault | Spec §6.3 | SQLite/DuckDB canonical DB                   | Repository inspection                |
| Duplicate handling            | Spec §6.4 | normalization + year-aware + ambiguity queue | Test corpus                          |
| Metadata enrichment           | Spec §6.5 | provider abstraction + cache                 | Integration test                     |
| Deterministic note generation | Spec §6.6 | templated projection from canonical DB       | rerun idempotency test               |
| Graph compatibility           | Spec §6.7 | IDs shaped for future graph nodes            | schema review                        |
| Auditability                  | Spec §6.8 | reports + match status + logging discipline  | report inspection                    |
| Ambiguity surfaced            | Spec §12  | unresolved report                            | integration test                     |
| Stable output paths           | Spec §12  | path generator keyed by canonical fields     | unit test                            |

# **5. Recommended repository placement**





Suggested locations inside obsidian_rag:

```
.specify/specs/OC-SPEC-MOVIES-v1.0.0/spec.md
.specify/plans/OC-PLAN-MOVIES-v1.0.0/plan.md
.specify/tasks/OC-TASKS-MOVIES-v1.0.0/tasks.md
Documentation/compliance/movie-subsystem-compliance-matrix.md
```

If your existing repository uses a numeric prefix convention, adapt accordingly, for example:

```
.specify/specs/00X-movie-catalog-subsystem/spec.md
.specify/plans/00X-movie-catalog-subsystem/plan.md
.specify/tasks/00X-movie-catalog-subsystem/tasks.md
```







# **6. Assessment of readiness**





These drafts are intentionally aligned to the architectural principles discussed earlier:



- canonical external identifiers
- structured store as source of truth
- Obsidian as projection layer
- future graph compatibility
- auditable ambiguity handling





Before implementation, I recommend one final hardening pass against your existing obsidian_rag governance documents:



- .specify/memory/constitution.md
- .specify/memory/implementation-checklist.md
- .specify/memory/codex-house-rules.md





The most likely required adjustments are:



- exact file placement conventions
- mandatory wording required by your constitution
- required verification command sequence
- naming/versioning format for spec folders



```

```