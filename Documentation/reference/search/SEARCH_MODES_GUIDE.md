# Search Mode Comparison

| Mode | Best For | Entry Point | Notes |
| --- | --- | --- | --- |
| `ask` | Fast single-pass answer | `POST /api/v1/query` mode=ask | Vector retrieval + compact synthesis |
| `research` | Staged, grounded answers | `POST /api/v1/query` mode=research | Graph → LightRAG → vector → synthesis; supports depth and source overrides |
| `investigate` | Agentic multi-step research | `WS /api/v1/deep-research` | Plan → search → reflect; streaming |

## Guidance

- Start with **ask** for fast recall and topic lookup.
- Use **research** when you want a synthesized, evidence-backed answer. Auto-depth routes most queries through a staged pipeline; override with `depth` if needed.
- Use **investigate** for open-ended or multi-hop analysis where the system needs several retrieval passes.
- NetworkX and LightRAG are internal retrieval subsystems behind `research` and `investigate`; they are not user-selectable modes.

## Research Depth

`research` mode accepts an optional `depth` field:

| Depth | Behaviour |
| --- | --- |
| `auto` (default) | Classifier picks shallow or staged based on query complexity |
| `shallow` | Single-pass vector search only |
| `staged` | Graph → LightRAG → vector (full pipeline) |
| `full` | Staged pipeline + full-note MCP reads |

## Data Sources

All modes accept an optional `sources` array:

| Source | Description |
| --- | --- |
| `vault` | Obsidian vault (always on) |
| `mempalace` | MemPalace long-term memory sidecar |
| `web` | Tavily web search (requires `TAVILY_API_KEY`) |

## Legacy Mode Compatibility

Legacy mode strings are still accepted and normalised at the API boundary. A `X-Deprecated-Mode` response header is emitted when a legacy string is used.

| Legacy mode | Maps to | Notes |
| --- | --- | --- |
| `vector` | `ask` + depth=shallow | |
| `mempalace` | `ask` + source=mempalace | |
| `cascading` | `research` + depth=auto | |
| `vault_review` | `research` + depth=full | |
| `deep-thinking` | `investigate` | |

## Enhanced Search

In the webapp, the Enhanced Search toggle adds supplemental web search and memory context when available. The underlying `sources` field controls this at the API level.

## Diagnosing Slow Research Queries

Check `cascading_query.*` and `cascading_synthesis.*` timing logs before changing retrieval logic. They show whether latency came from retrieval, prompt preparation, or the model call.
