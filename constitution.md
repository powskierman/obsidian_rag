# Constitution

This file is the root-level entrypoint for the project constitution.

Authoritative source:
- `Documentation/reference/governance/PROJECT_CONSTITUTION.md`

Mirrored source mentioned by the constitution:
- `.specify/memory/constitution.md`

Rules:
- Treat `Documentation/reference/governance/PROJECT_CONSTITUTION.md` as the governing document.
- Keep any mirrored copies aligned in the same change set.
- Route public search traffic through the API gateway public interfaces.
- Keep generated local data out of Git.
- Preserve independent rebuildability of vector and graph indexes.
- Update documentation when workflows, APIs, or service boundaries change.

Current canonical summary:
- Local-first personal RAG system for a private Obsidian vault.
- Public gateway on port `4000`.
- Internal retrieval services:
  - Embedding `8000`
  - LightRAG `8001`
  - NetworkX graph `8002`
  - Streamlit `8501`
- Primary public interfaces:
  - `POST /api/v1/query`
  - `GET /api/v1/health`
  - `GET /api/v1/stats`
  - `WS /api/v1/deep-research`

Definition of done:
- Relevant tests and smoke checks pass.
- Search modes remain functional for changed paths.
- Documentation is updated.
- Indexing and storage behavior remains constitution-compliant.
