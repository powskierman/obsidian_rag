#!/usr/bin/env bash
# full_cleanup_and_reindex.sh
# Clean vault contamination, reset LightRAG state, and kick off a fresh
# .md-only reindex against LMStudio (Gemma-4-26B-A4B-4bit MLX).
#
# Generated 2026-04-21. Review before running. Safe to rerun.
#
# What this script does (in order):
#   1. Sanity-checks paths
#   2. Archives vault contaminants (venv/, Users/, two 146MB tarballs) to ~/vault_cleanup_archive_<stamp>/
#   3. Verifies post-cleanup .md count (~3,203 expected)
#   4. Backs up .env and patches it for LMStudio + .md-only scope + exclude paths
#   5. Removes the stale hash cache
#   6. Stops lightrag-service, backs up and wipes lightrag_db
#   7. Rebuilds/recreates lightrag-service with current .env
#   8. Runs the indexer with --force against the clean slate
#
# Second pass for PDFs is documented at the bottom — run separately AFTER
# the .md pass completes successfully.

set -euo pipefail

### ---- Paths --------------------------------------------------------------
VAULT="${OBSIDIAN_VAULT_PATH:-$HOME/vault}"
REPO="/Users/michel/dev/obsidian_rag"
LIGHTRAG_DIR="/Users/michel/obsidian_rag_local_data/lightrag_db"
HASH_CACHE="$REPO/data/indexing/index_vault_hashes_97a8ed17ea03.json"
STAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE="$HOME/vault_cleanup_archive_$STAMP"

### ---- 1. Sanity checks ---------------------------------------------------
echo "=========================================="
echo "Obsidian RAG: full cleanup + reindex"
echo "Archive will be created at: $ARCHIVE"
echo "=========================================="
echo ""
for d in "$VAULT" "$REPO" "$(dirname "$LIGHTRAG_DIR")"; do
  [ -d "$d" ] || { echo "Missing directory: $d"; exit 1; }
done
[ -f "$REPO/.env" ] || { echo "Missing .env at $REPO/.env"; exit 1; }

mkdir -p "$ARCHIVE"

### ---- 2. Move contaminants out of the vault ------------------------------
echo "[2/8] Archiving vault contaminants..."

# venv/ (~366 MB, 37 indexable .md files in site-packages)
if [ -d "$VAULT/venv" ]; then
  echo "  - moving $VAULT/venv -> $ARCHIVE/venv"
  mv "$VAULT/venv" "$ARCHIVE/venv"
else
  echo "  - venv/: already gone"
fi

# Users/ (orphan path-shaped notes from a drag-drop mishap)
if [ -d "$VAULT/Users" ]; then
  echo "  - moving $VAULT/Users -> $ARCHIVE/Users"
  mv "$VAULT/Users" "$ARCHIVE/Users"
else
  echo "  - Users/: already gone"
fi

# .smtcmp_vector_db*.tar.gz (292 MB of stale Smart Composer backups)
shopt -s nullglob
for f in "$VAULT/.smtcmp_vector_db"*.tar.gz; do
  echo "  - moving $(basename "$f") -> $ARCHIVE/"
  mv "$f" "$ARCHIVE/"
done
shopt -u nullglob

### ---- 3. Verify post-cleanup count ---------------------------------------
echo ""
echo "[3/8] Counting legitimate .md files (should be ~3,203)..."
MD_COUNT="$(find "$VAULT" -type f -name '*.md' \
  -not -path "$VAULT/.*/*" \
  -not -path "$VAULT/Templates/*" \
  -not -path "$VAULT/Excalidraw/*" \
  | wc -l | tr -d ' ')"
echo "  .md files in scope: $MD_COUNT"
if [ "$MD_COUNT" -gt 3500 ] || [ "$MD_COUNT" -lt 2800 ]; then
  echo "  WARNING: count is outside expected 2800-3500 range. Pausing."
  echo "  Press ENTER to continue anyway, Ctrl-C to abort."
  read -r
fi

### ---- 4. Back up and patch .env ------------------------------------------
echo ""
echo "[4/8] Patching .env for LMStudio + .md-only scope..."
cp "$REPO/.env" "$REPO/.env.bak.$STAMP"
echo "  - backup: $REPO/.env.bak.$STAMP"

python3 - "$REPO/.env" <<'PY'
import sys, re
path = sys.argv[1]
with open(path) as f:
    txt = f.read()

def set_kv(text, key, value, comment=None):
    """Set KEY=VALUE, inserting if missing."""
    pattern = re.compile(rf'^{re.escape(key)}=.*$', re.MULTILINE)
    line = f'{key}={value}'
    if pattern.search(text):
        return pattern.sub(line, text)
    # append with optional comment
    suffix = '' if text.endswith('\n') else '\n'
    block = suffix
    if comment:
        block += f'# {comment}\n'
    block += f'{line}\n'
    return text + block

# --- LLM provider switch ---
txt = set_kv(txt, 'LLM_PROVIDER', 'lmstudio',
             comment='Indexer-time LLM provider (added by full_cleanup_and_reindex.sh)')

# --- Scope: .md only on first pass, exclude .pdf ---
txt = set_kv(txt, 'LIGHTRAG_INCLUDE_EXTENSIONS', '.md')
txt = set_kv(txt, 'LIGHTRAG_EXCLUDE_EXTENSIONS', '.pdf')

# --- Path excludes (both vars so legacy + partial scripts agree) ---
excl = 'venv/*,.venv/*,**/site-packages/*,.trash/*,.obsidian/*,.obsidian-mobile/*,.obsidianBak/*,.BAKobsidian/*,.obsidian_capture/*,.smart-connections/*,.smart-env/*,.smtcmp_json_db/*,.space/*,.makemd/*,.git/*,node_modules/*,__pycache__/*,Templates/*,Excalidraw/*,Users/*'
txt = set_kv(txt, 'LIGHTRAG_EXCLUDE_PATHS', excl)
txt = set_kv(txt, 'LIGHTRAG_EXCLUDE_PATH_PATTERNS', excl)

with open(path, 'w') as f:
    f.write(txt)
print("  .env patched")
PY

echo "  - key .env values now:"
grep -E '^(LLM_PROVIDER|LIGHTRAG_INCLUDE_EXTENSIONS|LIGHTRAG_EXCLUDE_EXTENSIONS|LIGHTRAG_EXCLUDE_PATHS|LMSTUDIO_MODEL|LMSTUDIO_BASE_URL)=' "$REPO/.env" || true

### ---- 5. Wipe stale hash cache ------------------------------------------
echo ""
echo "[5/8] Removing stale hash cache..."
if [ -f "$HASH_CACHE" ]; then
  mv "$HASH_CACHE" "$HASH_CACHE.bak.$STAMP"
  echo "  - moved to $HASH_CACHE.bak.$STAMP"
else
  echo "  - no hash cache present"
fi

### ---- 6. LMStudio reachability check -------------------------------------
echo ""
echo "[6/8] Checking LMStudio endpoint reachability..."
set -a; source "$REPO/.env"; set +a
LMS_URL="${LMSTUDIO_BASE_URL:-http://100.79.226.47:8090/v1}"
if curl -sSf --max-time 5 "${LMS_URL%/v1}/v1/models" >/dev/null 2>&1 \
   || curl -sSf --max-time 5 "$LMS_URL/models" >/dev/null 2>&1; then
  echo "  - LMStudio reachable at $LMS_URL"
else
  echo "  !! LMStudio NOT reachable at $LMS_URL"
  echo "     Start LMStudio Developer Server on port 8090 with model:"
  echo "     $LMSTUDIO_MODEL"
  echo "     Verify sampling preset: temp=0.1 top_p=0.8 top_k=40 min_p=0 repeat_penalty=1.05-1.1"
  echo "     Then re-run this script."
  exit 1
fi

### ---- 7. Wipe LightRAG store + rebuild service --------------------------
echo ""
echo "[7/8] Wiping LightRAG store and rebuilding service..."
if docker ps --format '{{.Names}}' | grep -q '^obsidian-lightrag$'; then
  echo "  - stopping lightrag-service"
  (cd "$REPO" && docker compose stop lightrag-service) || true
fi

if [ -d "$LIGHTRAG_DIR" ]; then
  mv "$LIGHTRAG_DIR" "${LIGHTRAG_DIR}.bak.$STAMP"
  echo "  - archived old DB to ${LIGHTRAG_DIR}.bak.$STAMP"
fi
mkdir -p "$LIGHTRAG_DIR"

echo "  - recreating lightrag-service with --build --force-recreate"
(cd "$REPO" && docker compose up -d --build --force-recreate lightrag-service)

# Wait for health
echo "  - waiting for health on http://localhost:8001/health"
for i in $(seq 1 60); do
  if curl -s http://localhost:8001/health >/dev/null 2>&1; then
    echo "  - service healthy"
    break
  fi
  sleep 2
  if [ "$i" = "60" ]; then
    echo "  !! lightrag-service did not become healthy in 120s"
    exit 1
  fi
done

### ---- 8. Kick off the .md-only reindex ----------------------------------
echo ""
echo "[8/8] Launching .md-only reindex (this can take an hour+)..."
echo "  Tail logs in another terminal with:"
echo "    docker logs -f obsidian-lightrag"
echo ""
"$REPO/Scripts/indexing/index_with_lightrag.sh" --force

echo ""
echo "=========================================="
echo "Done. Verify with:"
echo "  curl -s http://localhost:8001/stats | python3 -m json.tool"
echo ""
echo "SECOND PASS — PDFs (~249 files) — run AFTER the .md pass succeeds:"
echo ""
echo "  cd $REPO"
echo "  # Flip scope back on"
echo '  sed -i.bak "s|^LIGHTRAG_INCLUDE_EXTENSIONS=.*|LIGHTRAG_INCLUDE_EXTENSIONS=.md,.pdf|" .env'
echo '  sed -i.bak "s|^LIGHTRAG_EXCLUDE_EXTENSIONS=.*|LIGHTRAG_EXCLUDE_EXTENSIONS=|" .env'
echo "  ./Scripts/indexing/reindex_remaining_pdf_only.sh"
echo "=========================================="
