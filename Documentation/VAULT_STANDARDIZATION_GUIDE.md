# Vault Standardization Guide

Standardization improves retrieval, linking, and graph quality.

## Core Rules

- Consistent filenames and folders.
- Prefer explicit links over vague tags.
- Keep MoCs short and link-focused.
- Avoid duplicate notes with near-identical titles.

## Minimal Workflow

1. Apply the note template:
   - `Documentation/Notes/Templates/New Note Template.md`
2. Run tagging and MoC helpers as needed:
   - `Scripts/apply_tags.py`
   - `Scripts/identify_mocs.py`
   - `Scripts/apply_moc_template.py`
3. Reindex after large changes:
   - `./Scripts/index_with_lightrag.sh`

## Related Docs

- `Documentation/VAULT_ORGANIZATION_GUIDE.md`
- `Documentation/Setup/INDEXING_SCRIPTS_GUIDE.md`
