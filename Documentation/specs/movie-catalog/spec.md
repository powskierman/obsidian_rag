# Specification: Movie Catalog Subsystem

Spec ID: `OC-SPEC-MOVIES-v1.0.0`
Project: `obsidian_rag`
Status: Draft
Date: `2026-04-11`

## Summary

Introduce a movie-catalog subsystem that ingests movie records from Apple exports and NAS title lists, reconciles them into canonical movie records, stores those records outside the vault, and projects deterministic movie notes into Obsidian.

## Goals

1. Establish canonical movie identity with `imdb_id` as the preferred external anchor.
2. Keep the system of record outside the vault.
3. Preserve Apple and NAS provenance.
4. Generate deterministic `Media/Movies/*.md` notes.
5. Prepare stable identifiers for future graph and RAG integration.

## Non-Goals

1. Full TV / episode support in Phase 1.
2. Real-time bidirectional note-to-database syncing.
3. Poster downloading in Phase 1.
4. Media playback or server-management features.

## Core Requirements

### Canonical Identity

- Every resolved movie must have an internal canonical ID.
- `imdb_id` is the preferred external identifier when available.
- `tmdb_id` is optional in Phase 1.
- Titles must not be treated as the primary long-term identity key.

### Inputs

The system must ingest:
- Apple movie export in CSV or equivalent structured form
- NAS title list in plain text

### Canonical Store

- The canonical store must live outside the Obsidian vault.
- Phase 1 uses SQLite for portability, auditability, and deterministic local operation.

### Reconciliation

The pipeline must:
- normalize titles
- use year-aware matching where available
- preserve source provenance
- distinguish likely duplicates from remakes and alternate cuts
- surface ambiguous matches for manual review instead of silently merging them

### Obsidian Projection

Generated movie notes must include frontmatter for:
- `id`
- `kind`
- `title`
- `year`
- `imdb_id`
- `tmdb_id`
- `provenance`
- `collection`
- `quality_apple`
- `quality_nas`
- `top_250`
- `your_rating`
- `watched`
- `match_status`
- `version_notes`

### Graph / RAG Compatibility

- Future graph nodes should be keyed by canonical movie IDs rather than display titles.

## Acceptance Criteria

1. Apple CSV and NAS TXT inputs produce a canonical store and generated notes.
2. Straightforward duplicate ownership cases merge into one canonical movie record.
3. Ambiguous title-only inputs are surfaced in an unresolved report.
4. Alternate cuts remain distinct when version markers are present.
5. Re-running the pipeline is idempotent for unchanged inputs.
6. Generated note paths are stable across runs.

## Implementation Principle

Structured canonical storage is the source of truth.
Obsidian movie notes are deterministic projections.
