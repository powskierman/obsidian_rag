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
2. **Manual Tagging & MoCs**:
   - Add explicit tags (e.g. `#topic/subtopic`) to frontmatter.
   - Link related notes to their parent Map of Content (MoC).
3. Reindex after large changes:
   - `./Scripts/run_indexing.sh`

## Related Docs

- `Documentation/VAULT_ORGANIZATION_GUIDE.md`
- `Documentation/Setup/INDEXING_SCRIPTS_GUIDE.md`
