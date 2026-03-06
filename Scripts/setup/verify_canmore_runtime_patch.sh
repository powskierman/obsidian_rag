#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "== verify canmore runtime patch =="
echo "repo: $ROOT_DIR"
echo

check_local() {
  local file="$1"
  local pattern="$2"
  if ! grep -qE "$pattern" "$file"; then
    echo "❌ Local check failed: $file missing pattern: $pattern"
    return 1
  fi
  echo "✅ Local: $file"
}

check_container() {
  local service="$1"
  local file="$2"
  local pattern="$3"
  if ! docker compose exec -T "$service" sh -lc "grep -qE \"$pattern\" \"$file\""; then
    echo "❌ Container check failed: $service:$file missing pattern: $pattern"
    return 1
  fi
  echo "✅ Container: $service:$file"
}

echo "== local file signatures =="
check_local "src/services/api_gateway.py" "_looks_like_mlx_transport_failure_text"
check_local "src/services/api_gateway.py" "Deep research request:"
check_local "src/services/api_gateway.py" "Detected MLX transport failure in synthesized result"
check_local "webapp/src/app/page.tsx" "const isDeepThinkingMode = searchMode === 'deep-thinking';"
check_local "webapp/src/app/page.tsx" "console.warn\\('Deep Thinking Error:'"
check_local "webapp/src/context/AppContext.tsx" "savedMode === 'deep-thinking'"
check_local "deep_thinking/orchestrator.py" "No web evidence retrieved; running fallback web search"
check_local "docker-compose.yml" "./deep_thinking:/app/deep_thinking:ro"
echo

echo "== container signatures =="
check_container "api-gateway" "/app/src/services/api_gateway.py" "_looks_like_mlx_transport_failure_text"
check_container "api-gateway" "/app/src/services/api_gateway.py" "Deep research request:"
check_container "api-gateway" "/app/src/services/api_gateway.py" "Detected MLX transport failure in synthesized result"
check_container "api-gateway" "/app/deep_thinking/orchestrator.py" "No web evidence retrieved; running fallback web search"
check_container "webapp" "/app/src/app/page.tsx" "isDeepThinkingMode = searchMode ==="
check_container "webapp" "/app/src/app/page.tsx" "console.warn\\('Deep Thinking Error:'"
echo

echo "== active mounts =="
docker inspect obsidian-api-gateway --format '{{range .Mounts}}{{println .Source " -> " .Destination}}{{end}}' | grep '/app/deep_thinking' \
  && echo "✅ api-gateway has /app/deep_thinking mount" \
  || (echo "❌ api-gateway missing /app/deep_thinking mount" && exit 1)
echo

echo "== hashes =="
shasum -a 256 \
  src/services/api_gateway.py \
  webapp/src/app/page.tsx \
  webapp/src/context/AppContext.tsx \
  deep_thinking/orchestrator.py \
  docker-compose.yml
echo

echo "✅ Runtime patch verification complete"
