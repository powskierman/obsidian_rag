#!/usr/bin/env bash
set -euo pipefail

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.benchmark.yml"

BENCH_VAULT="${OBSIDIAN_BENCH_VAULT_PATH:-/tmp/obsidian_subset}"
BENCH_DB="${LIGHTRAG_BENCH_DIR:-/tmp/lightrag_benchmark_db}"

echo "Stopping benchmark container..."
$COMPOSE stop lightrag-benchmark >/dev/null || true

echo "Removing benchmark container..."
$COMPOSE rm -f lightrag-benchmark >/dev/null || true

echo "Resetting benchmark DB..."
rm -rf "$BENCH_DB"
mkdir -p "$BENCH_DB"

if [[ ! -d "$BENCH_VAULT" ]]; then
  echo "Subset vault not found: $BENCH_VAULT"
  echo "Create it first (example):"
  echo "  mkdir -p $BENCH_VAULT"
  exit 1
fi

echo "Rebuilding benchmark image..."
$COMPOSE build lightrag-benchmark

echo "Starting benchmark service..."
$COMPOSE up -d lightrag-benchmark

echo "Done."
