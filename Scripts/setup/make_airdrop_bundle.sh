#!/bin/bash
# Build an AirDrop-ready bundle of critical patched files for Canmore.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_DIR="${1:-$HOME/Desktop}"
BUNDLE_NAME="obsidian_rag_sync_bundle_${TIMESTAMP}"
STAGING_DIR="$(mktemp -d "/tmp/${BUNDLE_NAME}.XXXX")"
PAYLOAD_DIR="$STAGING_DIR/payload"

FILES=(
  "deep_thinking/orchestrator.py"
  "deep_thinking/supervisor.py"
  "deep_thinking/synthesizer.py"
  "deep_thinking/reflector.py"
  "deep_thinking/policy.py"
  "src/services/api_gateway.py"
  "webapp/src/app/page.tsx"
  "webapp/src/context/AppContext.tsx"
  "webapp/src/components/chat/SourcesDisplay.tsx"
  "Scripts/setup/recover_api_gateway_and_mlx.sh"
  "Scripts/setup/install_recovery_launch_agent.sh"
)

cleanup() {
  rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

mkdir -p "$PAYLOAD_DIR" "$OUTPUT_DIR"

echo "📦 Preparing AirDrop bundle from: $PROJECT_ROOT"

for rel_path in "${FILES[@]}"; do
  src="$PROJECT_ROOT/$rel_path"
  dst="$PAYLOAD_DIR/$rel_path"
  if [ ! -f "$src" ]; then
    echo "❌ Missing file: $rel_path" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$dst")"
  cp -p "$src" "$dst"
done

cat > "$STAGING_DIR/README.txt" <<'EOF'
Obsidian RAG sync bundle

Target: Canmore repo root
  /Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag

Apply steps on Canmore:
1) Unzip this bundle
2) Copy payload contents into repo root
   rsync -a payload/ "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/"
3) Ensure recovery scripts are executable
   chmod 755 Scripts/setup/recover_api_gateway_and_mlx.sh Scripts/setup/install_recovery_launch_agent.sh
4) Rebuild/restart services
   docker compose build --no-cache api-gateway webapp
   docker compose up -d --force-recreate api-gateway webapp
5) Hard refresh browser (Cmd+Shift+R)
EOF

(
  cd "$PAYLOAD_DIR"
  find . -type f | sort | sed 's#^\./##' > "$STAGING_DIR/file-list.txt"
  # macOS has shasum by default
  while IFS= read -r file; do
    shasum -a 256 "$file"
  done < "$STAGING_DIR/file-list.txt" > "$STAGING_DIR/sha256sums.txt"
)

ZIP_PATH="$OUTPUT_DIR/${BUNDLE_NAME}.zip"
(
  cd "$STAGING_DIR"
  /usr/bin/zip -r "$ZIP_PATH" README.txt file-list.txt sha256sums.txt payload >/dev/null
)

echo "✅ Bundle created:"
echo "   $ZIP_PATH"
echo ""
echo "Included files:"
cat "$STAGING_DIR/file-list.txt"
