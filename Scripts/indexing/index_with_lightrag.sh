#!/bin/bash
# Index Obsidian vault with LightRAG

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="$(cd "${SCRIPTS_ROOT}/.." && pwd)"
DOCKER_START="${SCRIPTS_ROOT}/docker/docker_start.sh"

echo "📚 Indexing Obsidian Vault with LightRAG"
echo "=========================================="
echo ""

# Check if LightRAG service is running, try to start if not
if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "⚠️  LightRAG service is not running"
    if [ -x "$DOCKER_START" ]; then
        echo "▶️  Attempting to start LightRAG via $DOCKER_START"
        "$DOCKER_START"
        for _ in {1..30}; do
            if curl -s http://localhost:8001/health > /dev/null 2>&1; then
                break
            fi
            sleep 2
        done
    else
        echo "❌ Missing docker start script at: $DOCKER_START"
    fi
fi

if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "❌ LightRAG service is not running"
    echo "   Start it with: $DOCKER_START"
    exit 1
fi

echo "✅ LightRAG service is ready"
echo ""

FORCE_REINDEX=false
DEFAULT_VAULT_PATH="/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
VAULT_PATH="${OBSIDIAN_VAULT_PATH:-$DEFAULT_VAULT_PATH}"
LIGHTRAG_INCLUDE_EXTENSIONS="${LIGHTRAG_INCLUDE_EXTENSIONS:-.md}"
LIGHTRAG_EXCLUDE_EXTENSIONS="${LIGHTRAG_EXCLUDE_EXTENSIONS:-.pdf}"
LIGHTRAG_EXCLUDE_PATHS="${LIGHTRAG_EXCLUDE_PATHS:-${LIGHTRAG_EXCLUDE_PATH_PATTERNS:-}}"
LIGHTRAG_BYPASS_REINDEX_GUARD="${LIGHTRAG_BYPASS_REINDEX_GUARD:-0}"

for arg in "$@"; do
    case "$arg" in
        --force)
            FORCE_REINDEX=true
            ;;
        -*)
            echo "Unknown option: $arg"
            exit 1
            ;;
        *)
            VAULT_PATH="$arg"
            ;;
    esac
done

echo "📂 Vault path: $VAULT_PATH"
echo "🧩 Include extensions: $LIGHTRAG_INCLUDE_EXTENSIONS"
echo "🚫 Exclude extensions: $LIGHTRAG_EXCLUDE_EXTENSIONS"
echo "🚫 Exclude paths: ${LIGHTRAG_EXCLUDE_PATHS:-<none>}"
echo "🛡️  Bypass reindex guard: $LIGHTRAG_BYPASS_REINDEX_GUARD"
echo ""
echo "🔄 Starting indexing process..."
echo "   (This may take several minutes for large vaults)"
echo ""

VAULT_PATH_FOR_REQUEST="$VAULT_PATH"
if [ -d "$VAULT_PATH" ]; then
    VAULT_PATH_FOR_REQUEST="$(cd "$VAULT_PATH" && pwd)"
fi

if command -v docker > /dev/null 2>&1; then
    if docker ps --format '{{.Names}}' | grep -q '^obsidian-lightrag$'; then
        MOUNT_SRC="$(docker inspect -f '{{ range .Mounts }}{{ if eq .Destination \"/app/vault\" }}{{ .Source }}{{ end }}{{ end }}' obsidian-lightrag 2>/dev/null)"
        if [ -n "$VAULT_PATH_FOR_REQUEST" ] && [ -d "$VAULT_PATH_FOR_REQUEST" ] && [ "$MOUNT_SRC" != "$VAULT_PATH_FOR_REQUEST" ]; then
            echo "🔧 Updating LightRAG vault mount to: $VAULT_PATH_FOR_REQUEST"
            (cd "$PROJECT_ROOT" && OBSIDIAN_VAULT_PATH="$VAULT_PATH_FOR_REQUEST" docker-compose up -d lightrag-service)
            for _ in {1..30}; do
                if curl -s http://localhost:8001/health > /dev/null 2>&1; then
                    break
                fi
                sleep 2
            done
        fi
        VAULT_PATH_FOR_REQUEST="/app/vault"
    fi
fi

# Send indexing request
if [ "$FORCE_REINDEX" = true ]; then
    echo "⚠️  Force reindex enabled"
    echo ""
fi

PAYLOAD="$(python3 - "$VAULT_PATH_FOR_REQUEST" "$FORCE_REINDEX" "$LIGHTRAG_INCLUDE_EXTENSIONS" "$LIGHTRAG_EXCLUDE_EXTENSIONS" "$LIGHTRAG_EXCLUDE_PATHS" "$LIGHTRAG_BYPASS_REINDEX_GUARD" <<'PY'
import json
import sys

vault_path = sys.argv[1]
force = sys.argv[2].lower() == "true"
include_raw = sys.argv[3]
exclude_raw = sys.argv[4]
exclude_paths_raw = sys.argv[5]
bypass_guard = sys.argv[6] in {"1", "true", "TRUE", "yes", "YES"}

def split_exts(raw: str):
    values = []
    for token in raw.split(","):
        token = token.strip().lower()
        if not token:
            continue
        if not token.startswith("."):
            token = f".{token}"
        values.append(token)
    return values

def split_paths(raw: str):
    return [token.strip() for token in raw.split(",") if token.strip()]

payload = {
    "vault_path": vault_path,
    "force": force,
    "include_extensions": split_exts(include_raw),
    "exclude_extensions": split_exts(exclude_raw),
    "exclude_paths": split_paths(exclude_paths_raw),
    "bypass_reindex_guard": bypass_guard,
}
print(json.dumps(payload))
PY
)"

RESPONSE=$(curl -s -X POST http://localhost:8001/index-vault \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

# Check response
if echo "$RESPONSE" | grep -q '"status":"success"'; then
    FILES=$(echo "$RESPONSE" | grep -o '"newly_indexed":[0-9]*' | cut -d':' -f2)
    echo ""
    echo "✅ Indexing complete!"
    echo "   Files indexed: $FILES"
    echo ""
    echo "You can now use graph-based queries in the UI:"
    echo "  - graph-local:  Local entity relationships"
    echo "  - graph-global: Global knowledge synthesis"
    echo "  - graph-hybrid: Combined approach"
else
    echo ""
    echo "❌ Indexing failed"
    echo "Response: $RESPONSE"
    exit 1
fi

echo ""
echo "=========================================="
