#!/usr/bin/env bash
set -euo pipefail

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.benchmark.yml"

VAULT_PATH="${OBSIDIAN_BENCH_VAULT_PATH:-/tmp/obsidian_subset}"
BASE_URL="${LMSTUDIO_BASE_URL:-http://localhost:1234/v1}"
EMBED_ASYNC="${EMBED_ASYNC:-1}"
LLM_ASYNC="${LLM_ASYNC:-1}"
LIGHTRAG_BATCH_SIZE="${LIGHTRAG_BATCH_SIZE:-3}"
LIGHTRAG_BATCH_TIMEOUT="${LIGHTRAG_BATCH_TIMEOUT:-1200}"
LIGHTRAG_TEST_TIMEOUT="${LIGHTRAG_TEST_TIMEOUT:-10800}"

MODEL_A="${MODEL_A:-}"
MODEL_B="${MODEL_B:-}"

if [[ -z "$MODEL_A" || -z "$MODEL_B" ]]; then
  echo "Set MODEL_A and MODEL_B to LM Studio model IDs."
  echo "Example:"
  echo "  MODEL_A=qwen/qwen3-8b-4bit MODEL_B=qwen/qwen3-8b-8bit $0"
  exit 1
fi

if [[ ! -d "$VAULT_PATH" ]]; then
  echo "Subset vault not found: $VAULT_PATH"
  exit 1
fi

run_model() {
  local model_id="$1"
  local label="$2"
  local bench_dir="/tmp/lightrag_benchmark_db_${label}"

  echo ""
  echo "=== Running benchmark for ${model_id} (${label}) ==="
  rm -rf "$bench_dir"
  mkdir -p "$bench_dir"

  $COMPOSE stop lightrag-benchmark >/dev/null || true
  $COMPOSE rm -f lightrag-benchmark >/dev/null || true

  OBSIDIAN_BENCH_VAULT_PATH="$VAULT_PATH" \
  LIGHTRAG_BENCH_DIR="$bench_dir" \
  LLM_PROVIDER=lmstudio \
  LLM_MODEL="$model_id" \
  LMSTUDIO_BASE_URL="$BASE_URL" \
  EMBED_ASYNC="$EMBED_ASYNC" \
  LLM_ASYNC="$LLM_ASYNC" \
  LIGHTRAG_BATCH_SIZE="$LIGHTRAG_BATCH_SIZE" \
  LIGHTRAG_BATCH_TIMEOUT="$LIGHTRAG_BATCH_TIMEOUT" \
  $COMPOSE up -d lightrag-benchmark

  LIGHTRAG_FORCE_REINDEX=1 \
  INDEXING_BENCHMARK_LIGHTRAG=1 \
  LIGHTRAG_SERVICE_URL=http://localhost:8003 \
  OBSIDIAN_TEST_VAULT="$VAULT_PATH" \
  LIGHTRAG_VAULT_PATH=/app/vault \
  LIGHTRAG_DIR="$bench_dir" \
  LIGHTRAG_TEST_TIMEOUT="$LIGHTRAG_TEST_TIMEOUT" \
  pytest tests/integration/test_lightrag_indexing_benchmark.py -m integration

  local latest
  latest=$(ls -t data/indexing/benchmarks/lightrag_indexing_benchmark_*.json | head -1)
  local stamp
  stamp=$(date +"%Y%m%d_%H%M%S")
  local target="data/indexing/benchmarks/lightrag_indexing_benchmark_${label}_${stamp}.json"
  cp "$latest" "$target"
  echo "Saved: $target"
}

run_model "$MODEL_A" "model_a"
run_model "$MODEL_B" "model_b"
