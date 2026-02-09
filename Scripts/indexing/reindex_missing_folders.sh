#!/usr/bin/env bash
set -euo pipefail

# --- Config ---
LIGHTRAG_URL="${LIGHTRAG_URL:-http://localhost:8001}"
VAULT_PATH="${VAULT_PATH:-$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel}"
DB_PATH="${DB_PATH:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/ data/graph_data/lightrag_db}"
INDEX_FILE="$DB_PATH/indexed_files.txt"
VAULT_PATH_IN_CONTAINER="${VAULT_PATH_IN_CONTAINER:-/app/vault}"

echo "LightRAG: $LIGHTRAG_URL"
echo "Vault:    $VAULT_PATH"
echo "Vault(in):$VAULT_PATH_IN_CONTAINER"
echo "DB:       $DB_PATH"
echo

# 0) Health check
if ! curl -fsS "$LIGHTRAG_URL/health" >/dev/null; then
  echo "ERROR: LightRAG is not reachable at $LIGHTRAG_URL"
  exit 1
fi

# 1) Compute missing folders (NFC-normalized), descending by missing count
FOLDERS=()
tmp_out="$(mktemp)"
python - "$VAULT_PATH" "$INDEX_FILE" <<'PY' > "$tmp_out"
from pathlib import Path
import unicodedata
from collections import Counter
import sys

vault = Path(sys.argv[1]).expanduser()
idx = Path(sys.argv[2]).expanduser()

if not vault.exists():
    print("ERROR: vault not found", file=sys.stderr)
    sys.exit(2)
if not idx.exists():
    print("ERROR: indexed_files.txt not found", file=sys.stderr)
    sys.exit(3)

def nfc(s): return unicodedata.normalize("NFC", s)

indexed = set()
for ln in idx.read_text(encoding="utf-8", errors="ignore").splitlines():
    ln = ln.strip()
    if not ln:
        continue
    p = ln.split("|", 1)[0]
    if p.startswith("/app/vault/"):
        indexed.add(p[len("/app/vault/"):])

current = set(
    str(p.relative_to(vault))
    for p in vault.rglob("*")
    if p.is_file() and p.suffix.lower() in {".md", ".pdf"}
)

cur_map, idx_map = {}, {}
for s in current: cur_map.setdefault(nfc(s), set()).add(s)
for s in indexed: idx_map.setdefault(nfc(s), set()).add(s)

missing_keys = set(cur_map) - set(idx_map)
missing = [next(iter(cur_map[k])) for k in missing_keys]

folders = Counter(str(Path(m).parent) for m in missing)
for folder, count in folders.most_common():
    # print as: count<TAB>folder
    print(f"{count}\t{folder}")
PY

while IFS= read -r line; do
  [ -n "$line" ] && FOLDERS+=("$line")
done < "$tmp_out"
rm -f "$tmp_out"

if [ "${#FOLDERS[@]}" -eq 0 ]; then
  echo "No missing folders found. Nothing to reindex."
  exit 0
fi

echo "Missing folders (desc):"
printf '%s\n' "${FOLDERS[@]}"
echo

# 2) Reindex each missing folder incrementally (force=false)
for line in "${FOLDERS[@]}"; do
  count="${line%%$'\t'*}"
  folder="${line#*$'\t'}"

  # "." means vault root
  if [ "$folder" = "." ]; then
    target_local="$VAULT_PATH"
    target_request="$VAULT_PATH_IN_CONTAINER"
  else
    target_local="$VAULT_PATH/$folder"
    target_request="$VAULT_PATH_IN_CONTAINER/$folder"
  fi

  echo ">>> Reindexing [$count missing] $target_local"
  http_code="$(curl -sS -o /tmp/reindex_missing_folders_resp.json -w "%{http_code}" -X POST "$LIGHTRAG_URL/index-vault" \
    -H "Content-Type: application/json" \
    -d "$(python - "$target_request" <<'PY'
import json,sys
print(json.dumps({"vault_path": sys.argv[1], "force": False}))
PY
)"
)"
  if [ "$http_code" -ge 400 ]; then
    echo "Request failed for: $target_request"
    cat /tmp/reindex_missing_folders_resp.json
    echo
    exit 1
  fi
  cat /tmp/reindex_missing_folders_resp.json
  echo
done

echo "Done."
echo "Check progress: curl -s $LIGHTRAG_URL/index-progress"
echo "Check stats:    curl -s $LIGHTRAG_URL/stats"
