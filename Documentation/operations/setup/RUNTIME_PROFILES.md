# Runtime Profiles

This repo supports machine-specific runtime overlays without forking the codebase.

## Profiles

- `canmore`
  - Preserves the home-base behavior.
  - Keeps the current Canmore-oriented defaults, including the MLX-compatible local path.
- `macbook`
  - Uses the MacBook-local Ollama path on `http://host.docker.internal:11434`.
  - Defaults to `qwen3.5:9b` for generation and `nomic-embed-text:latest` for local embedding-related paths.

## Selection

- The active profile is selected with `OBSIDIAN_RAG_PROFILE`.
- Profile overlays live in:
  - `config/profiles/canmore.env`
  - `config/profiles/macbook.env`
- Startup helpers merge `.env` with the selected profile and generate `.env.runtime`.

## Helpers

- `Scripts/setup/start_obsidian_rag.sh`
- `Scripts/setup/wait_for_obsidian_rag_ready.sh`
- `Scripts/setup/recover_local_llm_and_gateway.sh`

These helpers now adapt to the selected profile instead of assuming MLX unconditionally.
