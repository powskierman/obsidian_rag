#!/usr/bin/env bash
set -euo pipefail

LIGHTRAG_URL="${LIGHTRAG_URL:-http://localhost:8001}"
VAULT_PATH="${VAULT_PATH:-$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel}"
VAULT_PATH_IN_CONTAINER="${VAULT_PATH_IN_CONTAINER:-/app/vault}"
DATA_ROOT="${OBSIDIAN_RAG_DATA_DIR:-$HOME/obsidian_rag_local_data}"
DB_PATH="${DB_PATH:-$DATA_ROOT/lightrag_db}"
INDEX_FILE="$DB_PATH/indexed_files.txt"
DRY_RUN="${DRY_RUN:-0}"
HEALTH_RETRIES="${HEALTH_RETRIES:-60}"
HEALTH_SLEEP_SECONDS="${HEALTH_SLEEP_SECONDS:-2}"
REQUEST_RETRIES="${REQUEST_RETRIES:-8}"
REQUEST_SLEEP_SECONDS="${REQUEST_SLEEP_SECONDS:-3}"

echo "LightRAG: $LIGHTRAG_URL"
echo "Vault:    $VAULT_PATH"
echo "Vault(in):$VAULT_PATH_IN_CONTAINER"
echo "DB:       $DB_PATH"
echo "Dry run:  $DRY_RUN"
echo

wait_for_lightrag() {
  local i=1
  while [ "$i" -le "$HEALTH_RETRIES" ]; do
    if curl -fsS "$LIGHTRAG_URL/health" >/dev/null; then
      return 0
    fi
    echo "Waiting for LightRAG... ($i/$HEALTH_RETRIES)"
    sleep "$HEALTH_SLEEP_SECONDS"
    i=$((i + 1))
  done
  return 1
}

if [ "$DRY_RUN" != "1" ]; then
  if ! wait_for_lightrag; then
    echo "ERROR: LightRAG is not reachable/ready at $LIGHTRAG_URL"
    exit 1
  fi
fi

tmp_folders="$(mktemp)"
python - "$VAULT_PATH" "$INDEX_FILE" <<'PY' > "$tmp_folders"
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

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)

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
for s in current:
    cur_map.setdefault(nfc(s), set()).add(s)
for s in indexed:
    idx_map.setdefault(nfc(s), set()).add(s)

missing = [next(iter(cur_map[k])) for k in sorted(set(cur_map) - set(idx_map))]
missing_md = [m for m in missing if m.lower().endswith(".md")]

folders = Counter(str(Path(m).parent) for m in missing_md)
for folder, count in folders.most_common():
    print(f"{count}\t{folder}")
PY

FOLDERS=()
while IFS= read -r line; do
  [ -n "$line" ] && FOLDERS+=("$line")
done < "$tmp_folders"
rm -f "$tmp_folders"

if [ "${#FOLDERS[@]}" -eq 0 ]; then
  echo "No missing markdown files found. Nothing to reindex."
  exit 0
fi

echo "Missing markdown folders (desc):"
printf '%s\n' "${FOLDERS[@]}"
echo

for line in "${FOLDERS[@]}"; do
  count="${line%%$'\t'*}"
  folder="${line#*$'\t'}"

  if [ "$folder" = "." ]; then
    target_local="$VAULT_PATH"
    target_request="$VAULT_PATH_IN_CONTAINER"
  else
    target_local="$VAULT_PATH/$folder"
    target_request="$VAULT_PATH_IN_CONTAINER/$folder"
  fi

  echo ">>> Reindexing MD folder [$count missing-md] $target_local"

  if [ "$DRY_RUN" = "1" ]; then
    continue
  fi

  payload="$(python - "$target_request" <<'PY'
import json,sys
print(json.dumps({
  "vault_path": sys.argv[1],
  "force": False,
  "include_extensions": [".md"],
  "exclude_extensions": [".pdf"]
}))
PY
)"

  attempt=1
  while true; do
    http_code="$(curl -sS -o /tmp/reindex_remaining_md_only_resp.json -w "%{http_code}" -X POST "$LIGHTRAG_URL/index-vault" \
      -H "Content-Type: application/json" \
      -d "$payload")"

    if [ "$http_code" -lt 400 ]; then
      break
    fi

    if rg -q "LightRAG initializing" /tmp/reindex_remaining_md_only_resp.json && [ "$attempt" -lt "$REQUEST_RETRIES" ]; then
      echo "LightRAG initializing; retrying $attempt/$REQUEST_RETRIES for $target_request..."
      sleep "$REQUEST_SLEEP_SECONDS"
      attempt=$((attempt + 1))
      continue
    fi

    echo "Request failed for: $target_request"
    cat /tmp/reindex_remaining_md_only_resp.json
    echo
    exit 1
  done

  cat /tmp/reindex_remaining_md_only_resp.json
  echo
done

echo "Done."
echo "Verify: Scripts/list_remaining_missing_files.sh"
