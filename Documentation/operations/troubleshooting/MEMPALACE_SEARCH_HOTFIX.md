# MemPalace Search Hotfix

Date documented: 2026-04-26

## Problem

After mining the vault, exact one-word searches can return irrelevant `Match: 0.0`
results instead of exact note hits.

Example bad result:

```bash
mempalace search "yescarta" --results 5
```

Observed before patch:

- `Hemispheres-Spring-2013.md` from `recipes`
- `Lapointe Network Architecture.md`
- `main.js`
- all with `Match: 0.0`

The palace does contain exact Yescarta notes, so this is a search recall/ranking
problem, not missing data.

## Root Cause

MemPalace 3.3.3 still has two gaps in the installed CLI/programmatic search:

1. The human CLI path uses only Chroma vector nearest neighbors and prints them
   even when cosine distance is so poor that displayed similarity becomes `0.0`.
2. The programmatic `search_memories(..., max_distance=1.0)` path filters out
   the bad vector hits, but it does not add exact lexical candidates, so it can
   return no results for rare terms that exist verbatim in the palace.

## Upgrade First

Always upgrade MemPalace before reapplying the local patch:

```bash
pipx upgrade mempalace
~/.local/pipx/venvs/mempalace/bin/python - <<'PY'
import importlib.metadata
print(importlib.metadata.version("mempalace"))
PY
```

On 2026-04-26, this upgraded MemPalace from `3.3.0` to `3.3.3`, but the bug
remained.

## Verify Whether Patch Is Needed

Run:

```bash
mempalace search "yescarta" --results 5

~/.local/pipx/venvs/mempalace/bin/python - <<'PY'
from mempalace.config import MempalaceConfig
from mempalace.searcher import search_memories

res = search_memories("yescarta", MempalaceConfig().palace_path, n_results=5, max_distance=1.0)
for hit in res.get("results", []):
    print(hit["source_file"], hit["room"], hit["similarity"], hit.get("bm25_score"))
PY
```

Patch is needed if the CLI returns unrelated `Match: 0.0` results or if
`search_memories` returns no exact Yescarta hits.

Expected after patch:

```text
Yescarta.md medical 1.0
Yescarta Treatment Plan.md medical 1.0
Yescarta Side Effects.md medical 1.0
Immune System Health.md medical 1.0
Yescarta Survival Graph.md medical 1.0
```

## Local Patch Summary

Patch these installed files after a MemPalace upgrade if upstream has not fixed
the issue:

```text
~/.local/pipx/venvs/mempalace/lib/python3.12/site-packages/mempalace/searcher.py
~/.local/pipx/venvs/mempalace/lib/python3.12/site-packages/mempalace/cli.py
```

The patch adds:

- `_COMPOUND_TOKEN_RE` for identifiers such as `esp-idf`, `api/gateway`, and
  `foo_bar`
- `_LEXICAL_STOPWORDS`
- `_lexical_terms(query)`
- `_collect_lexical_hits(col, query, where, limit)`
- CLI `search(..., max_distance=1.0)` filtering
- `mempalace search --max-distance`
- exact-term candidate fallback in both `search()` and `search_memories()`

Important: lexical lookup is a fallback, not a primary ranker. Use it only when
the vector path has no acceptable hit after distance filtering. Otherwise broad
catalog files such as `single-tag-files.csv` can outrank better vector hits for
technical identifiers like `esp-idf`.

## Manual Patch Guide

In `searcher.py`, near `_TOKEN_RE`, add:

```python
_COMPOUND_TOKEN_RE = re.compile(r"\b\w+(?:[-_/]\w+)+\b", re.UNICODE)
_LEXICAL_STOPWORDS = {
    "about",
    "after",
    "and",
    "are",
    "for",
    "from",
    "how",
    "into",
    "the",
    "this",
    "what",
    "when",
    "where",
    "which",
    "with",
    "your",
}
```

After `_tokenize()`, add:

```python
def _lexical_terms(query: str) -> list:
    """Terms worth using for exact document lookup."""
    seen = {}
    for term in _COMPOUND_TOKEN_RE.findall(query.lower()):
        seen.setdefault(term, None)
    for term in _tokenize(query):
        if len(term) < 4 or term in _LEXICAL_STOPWORDS:
            continue
        seen.setdefault(term, None)
    return list(seen.keys())[:5]


def _collect_lexical_hits(col, query: str, where: dict, limit: int) -> list:
    """Fetch exact-term candidates so rare names do not depend on vector recall."""
    hits = []
    seen = set()
    for term in _lexical_terms(query):
        try:
            kwargs = {
                "where_document": {"$contains": term},
                "include": ["documents", "metadatas"],
                "limit": limit,
            }
            if where:
                kwargs["where"] = where
            results = col.get(**kwargs)
        except Exception:
            continue
        for rid, doc, meta in zip(
            results.get("ids") or [],
            results.get("documents") or [],
            results.get("metadatas") or [],
        ):
            if rid in seen:
                continue
            seen.add(rid)
            hits.append((rid, doc, meta, 0.0))
    return hits
```

In `search()`, add a `max_distance: float = 1.0` parameter. After the vector
query succeeds, replace the direct `docs/metas/dists = ...` assignment with
distance filtering and fallback-only lexical rescue:

```python
candidates = []
seen_ids = set()
for rid, doc, meta, dist in zip(
    _first_or_empty(results, "ids"),
    _first_or_empty(results, "documents"),
    _first_or_empty(results, "metadatas"),
    _first_or_empty(results, "distances"),
):
    seen_ids.add(rid)
    candidates.append((rid, doc, meta, dist))
for rid, doc, meta, dist in _collect_lexical_hits(col, query, where, n_results * 3):
    if rid not in seen_ids:
        candidates.append((rid, doc, meta, dist))
        seen_ids.add(rid)

filtered = []
for _rid, doc, meta, dist in candidates:
    if max_distance > 0.0 and dist > max_distance:
        continue
    filtered.append((doc, meta, dist))

if not filtered:
    for _rid, doc, meta, dist in _collect_lexical_hits(col, query, where, n_results * 3):
        if max_distance > 0.0 and dist > max_distance:
            continue
        filtered.append((doc, meta, dist))

filtered.sort(key=lambda item: item[2])
filtered = filtered[:n_results]

if filtered:
    docs, metas, dists = zip(*filtered)
else:
    docs, metas, dists = [], [], []
```

In `search_memories()`, before building `scored`, build vector candidates and
only add lexical candidates when no vector candidate passes `max_distance`:

```python
drawer_candidates = []
seen_ids = set()
for rid, doc, meta, dist in zip(
    _first_or_empty(drawer_results, "ids"),
    _first_or_empty(drawer_results, "documents"),
    _first_or_empty(drawer_results, "metadatas"),
    _first_or_empty(drawer_results, "distances"),
):
    seen_ids.add(rid)
    drawer_candidates.append((rid, doc, meta, dist))
vector_has_acceptable_hit = any(
    max_distance <= 0.0 or dist <= max_distance
    for _rid, _doc, _meta, dist in drawer_candidates
)
if not vector_has_acceptable_hit:
    for rid, doc, meta, dist in _collect_lexical_hits(drawers_col, query, where, n_results * 3):
        if rid not in seen_ids:
            drawer_candidates.append((rid, doc, meta, dist))
            seen_ids.add(rid)

scored = []
for _rid, doc, meta, dist in drawer_candidates:
    ...
```

In `cli.py`, pass the new argument into `search()`:

```python
max_distance=args.max_distance,
```

Add the CLI option near `--results`:

```python
p_search.add_argument(
    "--max-distance",
    type=float,
    default=1.0,
    help="Max cosine distance to display (0 disables filtering; default: 1.0)",
)
```

## Repo-Side Guard

The repo sidecar also defensively drops zero-score CLI blocks. Keep these guards:

- `mempalace_server.py`: skip parsed blocks when `Match <= 0.0`
- `payload/src/services/api_gateway.py`: skip parsed MemPalace blocks when
  `Match <= 0.0` and compute `relevance = match_score * 100.0`

These guards prevent bad CLI output from being promoted into API sources, but
they do not fix the underlying installed MemPalace recall problem. The installed
package patch above is still needed until upstream includes equivalent behavior.

## Post-Patch Validation

Run:

```bash
~/.local/pipx/venvs/mempalace/bin/python -m py_compile \
  ~/.local/pipx/venvs/mempalace/lib/python3.12/site-packages/mempalace/searcher.py \
  ~/.local/pipx/venvs/mempalace/lib/python3.12/site-packages/mempalace/cli.py

mempalace search --help
mempalace search "yescarta" --results 5
mempalace search "esp-idf" --results 5
python3 - <<'PY'
import mempalace_server

for source in mempalace_server._run_search("yescarta", 5):
    print(source["filename"], source["filepath"], source["relevance"])
PY
```

Expected:

- `mempalace search --help` includes `--max-distance`.
- `mempalace search "yescarta"` returns medical Yescarta notes.
- `mempalace search "esp-idf"` returns ESP-IDF notes rather than
  `single-tag-files.csv`.
- Sidecar output returns medical Yescarta notes with positive relevance.
