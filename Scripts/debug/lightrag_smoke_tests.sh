#!/usr/bin/env bash
set -euo pipefail

base_url="${LIGHTRAG_URL:-http://localhost:8001}"

echo "== LightRAG smoke tests =="

echo "-- Health"
curl -s "$base_url/health" | jq .

echo "-- Local query (should be fast, no LLM)"
payload=$(jq -nc --arg query "1st pet scan" --arg mode "local" '{query:$query,mode:$mode}')
curl --max-time 10 -s -H "Content-Type: application/json" -d "$payload" "$base_url/query" | jq .

echo "-- Hybrid query (should return or timeout with fallback)"
payload=$(jq -nc --arg query "Yescarta" --arg mode "hybrid" '{query:$query,mode:$mode}')
curl --max-time 20 -s -H "Content-Type: application/json" -d "$payload" "$base_url/query" | jq .

echo "-- Stats"
curl -s "$base_url/stats" | jq .

echo "== Done =="
