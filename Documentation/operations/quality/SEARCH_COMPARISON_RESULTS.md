# Search Comparison Results

Recording log for ad-hoc search-mode comparison runs (`ask` vs `research` vs `investigate`).

## How To Use

For each comparison run, append a section like:

```markdown
## YYYY-MM-DD <topic-or-vault-area>

- Query: "..."
- Mode A: ask                       | latency: <x>s | sources: <n> | notes:
- Mode B: research depth=auto       | latency: <x>s | sources: <n> | notes:
- Mode C: investigate (WS)          | latency: <x>s | sources: <n> | notes:
- Outcome: which mode answered best, why.
```

Pair each run with the timing diagnostics emitted by the gateway:

- `cascading_query.retrieval_complete`
- `cascading_query.synthesis_complete`
- `cascading_synthesis.*`

See `Documentation/getting-started/API_GATEWAY_QUICKSTART.md` for the full timing-log list.

## Runs

<!-- Append entries below this line -->
