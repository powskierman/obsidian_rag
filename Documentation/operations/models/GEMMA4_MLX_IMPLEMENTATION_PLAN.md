# Gemma 4 via MLX Implementation Plan

## Goal

Use Gemma 4 with `obsidian_rag` without relying on LM Studio, because LM Studio does not currently support Gemma 4.

The intended deployment is:

- Gemma 4 runs on the MacBook at `macbook-pro.taila61df4.ts.net`
- `obsidian_rag` calls that model over an OpenAI-compatible HTTP endpoint
- The existing `lmstudio` / `mlx` provider path in `obsidian_rag` is reused instead of adding a new provider

## Codebase Findings

After reviewing the current repo, the important implementation details are:

1. The backend already supports an OpenAI-compatible local-model route.
   - `src/services/api_gateway.py` treats `mlx` as an alias of `lmstudio`.
   - For `provider in {"lmstudio", "mlx"}`, the gateway sends requests to:
     - `LMSTUDIO_BASE_URL` or `QUERY_LMSTUDIO_BASE_URL`
     - fallback `MLX_BASE_URL` or `QUERY_MLX_BASE_URL`
     - endpoint shape: `.../chat/completions`

2. Provider defaults already support MLX-specific env vars.
   - Model resolution falls back through `LMSTUDIO_MODEL`, `MLX_MODEL`, and `LLM_MODEL_PATH`.
   - API key resolution falls back through `QUERY_LMSTUDIO_API_KEY`, `LMSTUDIO_API_KEY`, `QUERY_MLX_API_KEY`, and `MLX_API_KEY`.

3. The web UI is only partially generic.
   - Query execution can use any OpenAI-compatible endpoint through the gateway.
   - But `webapp/src/app/api/lmstudio/models/route.ts` still probes LM Studio's `GET /api/v0/models`.
   - A pure OpenAI-compatible MLX server will usually expose `GET /v1/models`, not `GET /api/v0/models`.
   - Result: Gemma 4 over MLX can work for inference while the UI still reports "LM Studio offline" or shows no loaded models.

4. Startup and recovery scripts assume MLX runs locally on the same machine as `obsidian_rag`.
   - `start_mlx.sh`
   - `Scripts/setup/start_obsidian_rag.sh`
   - `Scripts/setup/recover_api_gateway_and_mlx.sh`
   - These scripts assume `http://127.0.0.1:8090/v1/models` and try to start or restart MLX locally.
   - That assumption is wrong if Gemma 4 is hosted remotely on the MacBook.

## Recommended Architecture

### Host placement

Use the MacBook as the Gemma 4 inference host. This matches the machine-role guidance in `AGENTS.md`: the MacBook is an acceptable occasional heavy-compute node.

### Transport

Expose Gemma 4 through an OpenAI-compatible MLX server on the MacBook, reachable over Tailscale.

Recommended endpoint:

- `http://macbook-pro.taila61df4.ts.net:8090/v1`

Recommended model identifier:

- `mlx-community/gemma-4-26b-a4b-it-4bit`

Port `8090` is preferred because the existing project scripts and recovery logic already use it for MLX.

## Proposed Implementation

### Phase 1: Remote Gemma 4 serving on the MacBook

Install and validate Gemma 4 on the MacBook.

Example operator flow:

```bash
cd /work
python -m venv .venv-gemma4
source .venv-gemma4/bin/activate
pip install -U mlx-vlm mlx-openai-server
python -m mlx_vlm.generate \
  --model mlx-community/gemma-4-26b-a4b-it-4bit \
  --prompt "Test prompt" \
  --max-tokens 64
```

Then start the OpenAI-compatible server:

```bash
mlx-openai-server \
  --model mlx-community/gemma-4-26b-a4b-it-4bit \
  --host 0.0.0.0 \
  --port 8090
```

Validation from another machine:

```bash
curl -s http://macbook-pro.taila61df4.ts.net:8090/v1/models
```

Expected outcome:

- The server responds with a `data` array containing the Gemma 4 model id.

### Phase 2: Point `obsidian_rag` at the remote MLX server

Update the `.env` used by the `obsidian_rag` runtime.

Minimum settings:

```bash
LMSTUDIO_BASE_URL=http://macbook-pro.taila61df4.ts.net:8090/v1
LMSTUDIO_API_KEY=lmstudio
LMSTUDIO_MODEL=mlx-community/gemma-4-26b-a4b-it-4bit

MLX_BASE_URL=http://macbook-pro.taila61df4.ts.net:8090/v1
MLX_API_KEY=mlx
MLX_MODEL=mlx-community/gemma-4-26b-a4b-it-4bit

QUERY_LMSTUDIO_BASE_URL=http://macbook-pro.taila61df4.ts.net:8090/v1
QUERY_LMSTUDIO_API_KEY=lmstudio
QUERY_MLX_BASE_URL=http://macbook-pro.taila61df4.ts.net:8090/v1
QUERY_MLX_API_KEY=mlx
```

Recommended defaults if Gemma 4 should become the main local reasoning path:

```bash
DEFAULT_LLM_PROVIDER=lmstudio
CASCADING_LLM_PROVIDER=lmstudio
QUERY_LLM_PROVIDER=lmstudio
```

If LightRAG indexing or extraction should also use Gemma 4:

```bash
LLM_PROVIDER=mlx
LLM_MODEL=mlx-community/gemma-4-26b-a4b-it-4bit
LLM_MODEL_PATH=mlx-community/gemma-4-26b-a4b-it-4bit
```

Notes:

- `lmstudio` is the current user-facing provider name in the UI.
- `mlx` is a backend alias and remains valid for older scripts and envs.
- A dummy API key is acceptable if the MLX server does not enforce auth.

### Phase 3: Validate gateway integration

After restarting the stack, validate the actual request path through the gateway instead of relying on the sidebar status first.

Gateway test:

```bash
curl -s -X POST http://localhost:4000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is this vault about?",
    "mode": "cascading",
    "llm_provider": "lmstudio",
    "model": "mlx-community/gemma-4-26b-a4b-it-4bit",
    "max_results": 5
  }'
```

Expected outcome:

- The request succeeds through the gateway.
- The answer is synthesized by the remote Gemma 4 server.

### Phase 4: Fix the UI/status mismatch

This is the main code change recommended before calling the integration complete.

Current problem:

- `webapp/src/app/api/lmstudio/models/route.ts` only probes `GET /api/v0/models`.
- That works for LM Studio, but not for a generic OpenAI-compatible MLX server.

Recommended change:

1. Try LM Studio-native discovery first:
   - `GET {serverRoot}/api/v0/models`
2. If that fails, fall back to OpenAI-compatible discovery:
   - `GET {base}/models` or `GET {serverRoot}/v1/models`
3. Normalize both responses into:
   - `models`
   - `installedModels`
   - `reachable`

Expected result:

- The sidebar no longer incorrectly reports the remote Gemma 4 server as offline.
- The settings panel can show the served model ID even when LM Studio is not involved.

### Phase 5: Make startup and recovery remote-aware

Current problem:

- `Scripts/setup/start_obsidian_rag.sh` and `Scripts/setup/recover_api_gateway_and_mlx.sh` assume MLX is local and managed by this repo.
- With a remote MacBook-hosted Gemma 4 server, those scripts may try to start or restart the wrong thing.

Recommended change:

Add a remote-MLX guard:

- If `MLX_BASE_URL` or `LMSTUDIO_BASE_URL` points to `host.docker.internal`, local startup/recovery remains enabled.
- If the URL points to a remote Tailscale host such as `macbook-pro.taila61df4.ts.net`, skip local MLX startup and skip local MLX restart attempts.

Expected result:

- `obsidian_rag` stops treating remote Gemma 4 as if it were a crashed local MLX process.

## Suggested File Changes

These are the repo changes I would recommend after document approval:

1. `webapp/src/app/api/lmstudio/models/route.ts`
   - Add `/v1/models` fallback for OpenAI-compatible servers.

2. `Scripts/setup/start_obsidian_rag.sh`
   - Do not auto-start local MLX when `MLX_BASE_URL` is remote.

3. `Scripts/setup/recover_api_gateway_and_mlx.sh`
   - Do not restart local MLX when `MLX_BASE_URL` is remote.

4. Optional UI copy cleanup:
   - Rename "LM Studio" to "Local OpenAI-compatible" or "LM Studio / MLX".
   - This better reflects current backend behavior.

## Risks

1. Remote inference latency
   - Gemma 4 on the MacBook will be slower than smaller local models.
   - Timeouts may need adjustment for cascading and deep-research requests.

2. Recovery false positives
   - Without the remote-aware script changes, transport failures may trigger misleading "recovery running" messages.

3. UI confusion
   - Without the `/v1/models` fallback, the model can work while the sidebar claims it is unavailable.

4. Exposure scope
   - The MLX server should be reachable only through Tailscale or another trusted private network path.

## Acceptance Criteria

This implementation should be considered complete when all of the following are true:

1. `curl http://macbook-pro.taila61df4.ts.net:8090/v1/models` returns the Gemma 4 model id.
2. `POST /api/v1/query` succeeds with `llm_provider="lmstudio"` and the Gemma 4 model id.
3. The webapp can select the provider and run successful queries against Gemma 4.
4. The sidebar/settings model-status flow correctly detects the remote MLX server.
5. Startup and recovery scripts do not try to manage a local MLX process when the configured endpoint is remote.

## Recommendation

Proceed in two steps:

1. Ship the env-only remote Gemma 4 integration first, because the backend already supports it.
2. Immediately follow with the UI discovery and remote-aware recovery fixes, because those are the main gaps between "works" and "operationally correct."











