# Compliance Matrix: Movie Catalog Subsystem

| Requirement | Planned Implementation | Verification |
|---|---|---|
| Canonical ID required | `movie:<imdb_id>` or `movie:local:<slug>` | Unit + integration tests |
| Title not primary identity | Matching layer uses normalized title, year, version, and optional external IDs | Code review + tests |
| Apple and NAS ingestion | Separate parsers into shared staging records | Integration test |
| Provenance preserved | Source records and note frontmatter keep provenance | Assertions in integration test |
| Canonical store outside vault | SQLite under `${OBSIDIAN_RAG_DATA_DIR}/movies` | Repository inspection |
| Duplicate handling | Deterministic merge for title/year/version matches | Unit tests |
| Alternate cuts remain distinct | Version markers influence grouping | Unit tests |
| Ambiguity surfaced | Unresolved report written for title-only ambiguous inputs | Integration test |
| Deterministic note generation | Stable filename generator and projection template | Unit + integration tests |
| Graph compatibility | Canonical IDs shaped for future graph node identity | Schema review |
