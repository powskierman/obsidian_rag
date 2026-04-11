# Movie Subsystem Operator Guide

## Overview

The movie subsystem ingests Apple CSV and NAS TXT inputs, reconciles them into canonical movie records, stores the canonical dataset outside the vault, and projects deterministic notes into `Media/Movies/`.

## Data Locations

Default data root:
- `${OBSIDIAN_RAG_DATA_DIR}/movies`

Outputs:
- SQLite store: `${OBSIDIAN_RAG_DATA_DIR}/movies/canonical_movies.db`
- Cache: `${OBSIDIAN_RAG_DATA_DIR}/movies/cache/`
- Reports: `${OBSIDIAN_RAG_DATA_DIR}/movies/reports/`

## Script Entry Point

```bash
python Scripts/movies/sync_movies.py \
  --apple-csv /path/to/apple_movies.csv \
  --nas-txt /path/to/nas_titles.txt
```

## Important Flags

- `--vault-root`: override `OBSIDIAN_VAULT_PATH`
- `--db-path`: custom SQLite path
- `--report-dir`: custom report directory
- `--provider`: `none` or `omdb`
- `--omdb-api-key`: explicit OMDb key, otherwise `OMDB_API_KEY`
- `--skip-projection`: update canonical store and reports only

## Matching Rules

- Duplicate ownership variants merge when title, year, and version markers align.
- Remakes remain separate when years differ.
- Alternate cuts remain separate when version markers differ.
- Ambiguous title-only cases are written to the unresolved report.

## Generated Notes

Generated notes are written to:
- `Media/Movies/`

The generator preserves:
- `your_rating`
- `watched`
- content between:
  - `<!-- MOVIE-USER-NOTES-START -->`
  - `<!-- MOVIE-USER-NOTES-END -->`

## Reports

- `unresolved_matches.md`
- `movie_sync_summary.md`

## Verification

Recommended checks:

```bash
pytest -o addopts='' tests/unit/test_movie_normalize.py tests/integration/test_movie_subsystem.py
```
