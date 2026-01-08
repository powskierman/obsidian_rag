# Vault Organization Guide

This guide focuses on keeping your vault structured for reliable retrieval and graph quality.

## Core Principles

- Use consistent folder names and note titles.
- Prefer explicit links over implicit tags.
- Keep Maps of Content (MoCs) lightweight and link-only.
- Avoid deeply nested folder structures that hide related notes.

## Workflow (Lightweight)

1. Normalize new notes using the template:
   - `Documentation/Notes/Templates/New Note Template.md`
2. Apply tags and MoC structure as needed using scripts in `Scripts/`:
   - `apply_tags.py`, `apply_moc_template.py`, `identify_mocs.py`
3. Reindex when you add or reorganize large sets of notes:
   - `./Scripts/index_with_lightrag.sh`

## Troubleshooting

- Services not responding: `docker compose ps`
- Graph feels stale: re-run indexing script(s) in `Scripts/`

## Related Docs

- `Documentation/VAULT_STANDARDIZATION_GUIDE.md`
- `Documentation/Setup/QUICKSTART.md`
