# Implementation Plan: Movie Catalog Subsystem

Plan ID: `OC-PLAN-MOVIES-v1.0.0`
Spec: `OC-SPEC-MOVIES-v1.0.0`
Date: `2026-04-11`

## Objective

Implement a governed movie-catalog subsystem with:
- canonical ID resolution
- structured storage
- deterministic Obsidian projection
- unresolved-match reporting
- future graph compatibility

## Architecture Decision

Use a SQLite canonical store outside the vault and generate notes into `Media/Movies/`.

## Deliverables

1. Canonical schema and storage bootstrap
2. Apple CSV ingestion
3. NAS TXT ingestion
4. Matching and reconciliation
5. Optional metadata provider abstraction
6. Deterministic Obsidian note projection
7. Unresolved-match reporting
8. Unit and integration tests

## Phase Breakdown

### Phase 1: Schema and Storage

- add a `src/movies` package
- define canonical movie and source-record schema
- persist canonical data under `${OBSIDIAN_RAG_DATA_DIR}/movies`

### Phase 2: Input Ingestion

- parse Apple CSV exports into a shared staging shape
- parse NAS TXT lines into the same staging shape
- retain raw provenance and source payloads

### Phase 3: Matching and Resolution

- normalize titles
- extract year and version markers
- merge Apple/NAS duplicates
- keep remakes and alternate cuts separate when evidence exists
- write ambiguous title-only records to review output

### Phase 4: Enrichment

- define a provider abstraction
- ship a null provider and an optional OMDb-backed provider with local cache

### Phase 5: Obsidian Projection

- generate deterministic note paths
- write governed frontmatter
- preserve a user-editable notes section across reruns

### Phase 6: Reporting and Verification

- write unresolved report
- write summary report
- add tests for normalization, matching, and end-to-end projection

## Repository Placement

- Specs: `Documentation/specs/movie-catalog/`
- Compliance matrix: `Documentation/compliance/movie-subsystem-compliance-matrix.md`
- Operator guide: `Documentation/operations/movies/MOVIE_SUBSYSTEM_OPERATOR_GUIDE.md`
- Code: `src/movies/`
- Script entrypoint: `Scripts/movies/sync_movies.py`
