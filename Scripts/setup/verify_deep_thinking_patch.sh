#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

SERVICE="${1:-api-gateway}"
LOCAL_FILE="deep_thinking/orchestrator.py"
CONTAINER_FILE="/app/deep_thinking/orchestrator.py"

SIG_1="_should_force_web_step"
SIG_2="No web evidence retrieved; running fallback web search"
SIG_3="DEEP_THINKING_REQUIRE_VAULT_STEP"
SIG_4="max_sources: int = 12"

if [[ ! -f "$LOCAL_FILE" ]]; then
  echo "❌ Local file missing: $LOCAL_FILE"
  exit 1
fi

echo "== verify deep thinking patch =="
echo "repo:    $ROOT_DIR"
echo "service: $SERVICE"
echo

echo "== mount check =="
docker inspect "obsidian-${SERVICE}" --format '{{range .Mounts}}{{println .Source " -> " .Destination}}{{end}}' \
  | grep '/app/deep_thinking' || {
  echo "❌ /app/deep_thinking is not mounted in container obsidian-${SERVICE}"
  exit 1
}
echo "✅ deep_thinking mount present"
echo

echo "== sha256 =="
LOCAL_SHA="$(shasum -a 256 "$LOCAL_FILE" | awk '{print $1}')"
CONTAINER_SHA="$(docker compose exec -T "$SERVICE" sh -lc "cat '$CONTAINER_FILE'" | shasum -a 256 | awk '{print $1}')"
echo "local:     $LOCAL_SHA"
echo "container: $CONTAINER_SHA"
if [[ "$LOCAL_SHA" != "$CONTAINER_SHA" ]]; then
  echo "❌ File content mismatch between local and running container"
  exit 1
fi
echo "✅ Local and container orchestrator match"
echo

echo "== signatures (local) =="
grep -nE "$SIG_1|$SIG_2|$SIG_3|$SIG_4" "$LOCAL_FILE"
echo
echo "== signatures (container) =="
docker compose exec -T "$SERVICE" sh -lc "grep -nE '$SIG_1|$SIG_2|$SIG_3|$SIG_4' '$CONTAINER_FILE'"
echo
echo "✅ Patch signatures found locally and in running container"
