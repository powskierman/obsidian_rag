# Code Review — Query Mode Consolidation + Timeout Fixes

**Date:** 2026-04-18
**Commits reviewed:** `0e038c8` (mode consolidation), `b980bd1` (timeout + service status)
**Scope:** `src/services/query_dispatch.py`, `src/services/api_gateway.py`,
`webapp/src/context/AppContext.tsx`, `webapp/src/app/api/query/route.ts`,
`webapp/src/lib/types.ts`, dispatch tests.

## Critical

None. The core migration is solid.

## Medium

### 1. `_canonical_to_legacy_dispatch_key` silently falls through to `"vector"` for web-only ask
**File:** `src/services/api_gateway.py:3575-3583`

```python
if canonical_mode == "ask":
    if canonical_sources == ("mempalace",): return "mempalace"
    if "vault" in canonical_sources:        return "vector"
    if "mempalace" in canonical_sources:    return "mempalace"
    return "vector"   # <-- catches sources=("web",) and dispatches to VAULT
```

A client sending `mode="ask", sources=["web"]` gets vault results silently.
Either raise `HTTPException(400)` or add a real web-only branch. Same concern
for any unknown source string — `normalize_legacy_request` does not validate
`explicit_sources` values.

**Fix:** validate sources against the `Source` literal inside
`normalize_legacy_request`; raise `UnsupportedMode` for unknown values. Or
explicitly 400 in the adapter when no known source matches.

---

### 2. `explicit_depth` is not validated
**File:** `src/services/query_dispatch.py:121,137`

`explicit_depth or spec.get("depth", "auto")` passes any string through. A
request with `depth="evil"` reaches `_canonical_to_legacy_dispatch_key`,
doesn't match `"full"`/`"shallow"`, and silently lands on `"cascading"`. Low
exploit risk (no code injection), but it hides client bugs.

**Fix:** raise `UnsupportedMode` when `explicit_depth` is non-None and not in
`{"auto","shallow","staged","full"}`.

---

### 3. `GATEWAY_QUERY_TIMEOUT_MS_LOCAL` is undocumented
**File:** `webapp/src/app/api/query/route.ts:51`

Grep turned up only the one reference in `route.ts` — not in any `.md`,
`.env.example`, or `docker-compose`. Operators tuning local-provider timeouts
will guess.

**Fix:** add it to `Documentation/integrations/mcp/MCP_SETUP_INSTRUCTIONS.md`
or the env example alongside existing `GATEWAY_QUERY_TIMEOUT_MS_CASCADING`
entries.

---

### 4. `LEGACY_SEARCH_MODE_MAP` is missing older persisted values
**File:** `webapp/src/lib/types.ts:152-160`

Git history shows prior `SearchMode` unions included `'knowledge-graph'`,
`'notes'`, `'entities'`, `'notes+vector'`, `'entities+vector'`,
`'dual-graph'`. These are unmapped. `migrateSearchMode()` returns `null` for
them → silent fallback to the `'research'` initial state. Users on a very
old install see their mode reset without explanation.

**Fix:** add these keys mapping to `'research'` (sensible default for
graph-leaning queries), and log once when an unknown mode is seen.

---

### 5. `X-Deprecated-Mode` header is dropped on `HTTPException` paths
**File:** `src/services/api_gateway.py:3647-3648`

Handler sets `response.headers["X-Deprecated-Mode"] = deprecated`, then later
code can `raise HTTPException`. Starlette discards the pre-set header on the
error response — the `test_legacy_cascading_mode_emits_deprecation_header`
test comment explicitly acknowledges this. Legacy-mode 4xx/5xx responses
have no deprecation signal, degrading migration telemetry for exactly the
calls most likely to need attention.

**Design choice — middleware vs. exception handler:**

*Option A — `@app.exception_handler(HTTPException)`:* intercept every
`HTTPException`, copy `X-Deprecated-Mode` from `request.state` if present.
Requires storing the value on `request.state` in `unified_query` before any
raise, and rewriting the default JSON error body (which you have to do anyway
to preserve existing error shape). Fragile: a second exception handler or
`HTTPException` subclass can bypass it.

*Option B — `@app.middleware("http")` (recommended):* read the raw `mode`
field from the JSON body in middleware, classify it once (just the legacy-name
check, not the full normalize call), stash the deprecated name on
`request.state.deprecated_mode`. After `await call_next(request)`, if
`request.state.deprecated_mode` is set, add the header to the response
unconditionally — it works for both 2xx and 4xx because middleware wraps the
full response object Starlette ultimately sends.

Starlette's request body can only be consumed once, so cache it:

```python
@app.middleware("http")
async def _tag_deprecated_mode(request: Request, call_next):
    deprecated = None
    if request.method == "POST" and request.url.path == "/api/v1/query":
        try:
            body = await request.body()          # caches bytes on request._body
            import json as _json
            raw_mode = _json.loads(body).get("mode", "")
            if raw_mode in _LEGACY_MODE_NAMES:   # existing frozenset
                deprecated = raw_mode
        except Exception:
            pass
    response = await call_next(request)
    if deprecated:
        response.headers["X-Deprecated-Mode"] = deprecated
    return response
```

Register it **after** `CORSMiddleware` (Starlette middleware runs in
registration-reverse order, so registering last means it executes outermost —
headers set here survive the full lifecycle including error responses). Remove
the `response.headers["X-Deprecated-Mode"] = deprecated` line in
`unified_query`; it becomes redundant and confusing.

**Success-path header stays correct** because the middleware writes to the
same `response` object regardless of status code — the existing
success-path test passes unchanged.

## Low

### 6. `refreshServices()` has no in-flight guard
**File:** `webapp/src/context/AppContext.tsx:399-448,451`

VaultInfoModal + ServicesPanel opening simultaneously triggers two concurrent
runs. React state setters are safe, but last-response-wins ordering means an
earlier-issued call that resolves later will clobber fresher data. Not a
data-corruption bug, just a flicker risk under flaky gateways.

**Fix — ref + promise dedup with unmount safety:**

```tsx
const inflightRef = useRef<Promise<void> | null>(null);
const mountedRef = useRef(true);

useEffect(() => {
  mountedRef.current = true;
  return () => { mountedRef.current = false; };
}, []);

const refreshServices = (): Promise<void> => {
  if (inflightRef.current) return inflightRef.current;   // deduplicate

  const run = (async () => {
    try {
      const stats = await api.getStats();
      const [ollamaModels, lmstudioStatus] = await Promise.all([
        api.getOllamaModels(),
        api.getLmStudioModelStatus(),
      ]);
      if (!mountedRef.current) return;                   // unmount guard
      // ... existing updateServices(...) call unchanged ...
    } catch (error) {
      console.error('Failed to check services:', error);
      if (!mountedRef.current) return;
      // ... existing error updateServices(...) unchanged ...
    } finally {
      inflightRef.current = null;
    }
  })();

  inflightRef.current = run;
  return run;
};
```

**Why `useRef` instead of `useState`:** storing the promise in state would
trigger a re-render on every start/finish; a ref holds it stably without
causing renders. The `mountedRef` check after the awaits prevents
`updateServices` from flushing into an unmounted context (React 18 batching
makes this unlikely to crash, but it still logs a noisy warning in dev mode).

**Correctness note on dedup:** returning the in-flight promise means both
callers await the same resolution — they see the same data snapshot, which is
correct for concurrent UI panels. A debounce of 500 ms is an alternative but
deduplication is strictly better here: it avoids the extra delay on the
*first* call (which users feel on panel open) while still collapsing
concurrent triggers.

---

### 7. Dead fields on `UnifiedQueryRequest`
**File:** `src/services/api_gateway.py:3555-3556`

`force_mode` and `require_llm` are declared but never read anywhere in
`api_gateway.py`. They're either orphaned from a prior refactor or will
confuse clients who think they do something.

**Fix:** remove, or wire through if intended.

---

### 8. Legacy `deep-thinking` / `deep-research` strings rejected by backend, accepted by frontend
**Files:** `src/services/query_dispatch.py:76-81` vs `webapp/src/lib/types.ts:158-159`

Frontend migrates `'deep-thinking'` → `'investigate'` locally, so REST never
sees it from the webapp. But an MCP/legacy REST client still sending
`mode="deep-thinking"` gets a 400 with a message that doesn't mention it.

**Fix:** include `deep-thinking` / `deep-research` in the error message with
a pointer to `/api/v1/deep-research`.

---

### 9. `migrateSearchMode` runs inside the mount effect, not before first render
**File:** `webapp/src/context/AppContext.tsx:154,230`

`useState<SearchMode>('research')` → first render shows `research`, then
effect fires, migration may change to `'ask'`/`'investigate'`. One-frame
flash of the default mode before the persisted one is applied. Not
corruption, just UX jitter. Acceptable for the scope of this refactor.

## Tests — gaps

**Files:** `tests/unit/test_query_dispatch.py`,
`tests/public_contract/test_canonical_modes.py`

- **Missing:** `normalize_legacy_request(None)` — null-safety contract test
  (handler builds `raw_mode = (request.mode or "").strip()` but the
  normalizer's own contract should be asserted).
- **Missing:** empty-string mode test (`""` should raise `UnsupportedMode`).
- **Missing:** invalid depth test (see issue #2).
- **Missing:** invalid sources test (see issue #1).
- **Missing:** web-only ask dispatch test — would currently return vault
  results (see issue #1).
- `test_legacy_cascading_mode_emits_deprecation_header` acknowledges it
  can't verify the header due to the 599 short-circuit. Replace with a test
  that uses the success path so the header is observable.
- Contract tests are `@pytest.mark.integration` and use
  `TestClient(api_gateway.app)` — they exercise the live FastAPI app with
  monkeypatched AsyncClient. Integration-level but no real network — good
  for CI isolation.

## Summary

Core design is sound: `normalize_legacy_request` is small, legacy map is
tight, `allow_auto_route` logic is correct for all four
`(canonical_mode, canonical_depth)` combos traced. The migration has two
real silent-fallback bugs (#1, #4), one documentation gap (#3), and one
observability gap (#5). Everything else is hygiene.
