#!/usr/bin/env bash
set -euo pipefail

LIGHTRAG_URL="${LIGHTRAG_URL:-http://localhost:8001}"
VAULT_PATH="${VAULT_PATH:-$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel}"
VAULT_PATH_IN_CONTAINER="${VAULT_PATH_IN_CONTAINER:-/app/vault}"
DATA_ROOT="${OBSIDIAN_RAG_DATA_DIR:-$HOME/obsidian_rag_local_data}"
DB_PATH="${DB_PATH:-$DATA_ROOT/lightrag_db}"
INDEX_FILE="$DB_PATH/indexed_files.txt"
DRY_RUN="${DRY_RUN:-0}"
THROTTLE_SECONDS="${THROTTLE_SECONDS:-3}"
MAX_FILES_PER_CALL="${MAX_FILES_PER_CALL:-0}"

echo "LightRAG: $LIGHTRAG_URL"
echo "Vault:    $VAULT_PATH"
echo "Vault(in):$VAULT_PATH_IN_CONTAINER"
echo "DB:       $DB_PATH"
echo "Dry run:  $DRY_RUN"
echo "Throttle: ${THROTTLE_SECONDS}s"
echo "max_files per call: $MAX_FILES_PER_CALL (0=unlimited)"
echo

if [ "$DRY_RUN" != "1" ]; then
  if ! curl -fsS "$LIGHTRAG_URL/health" >/dev/null; then
    echo "ERROR: LightRAG is not reachable at $LIGHTRAG_URL"
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
missing_pdf = [m for m in missing if m.lower().endswith(".pdf")]

folders = Counter(str(Path(m).parent) for m in missing_pdf)
for folder, count in folders.most_common():
    print(f"{count}\t{folder}")
PY

FOLDERS=()
while IFS= read -r line; do
  [ -n "$line" ] && FOLDERS+=("$line")
done < "$tmp_folders"
rm -f "$tmp_folders"

if [ "${#FOLDERS[@]}" -eq 0 ]; then
  echo "No missing PDF files found. Nothing to reindex."
  exit 0
fi

echo "Missing PDF folders (desc):"
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

  echo ">>> Reindexing PDF folder [$count missing-pdf] $target_local"

  if [ "$DRY_RUN" = "1" ]; then
    continue
  fi

  http_code="$(curl -sS -o /tmp/reindex_remaining_pdf_only_resp.json -w "%{http_code}" -X POST "$LIGHTRAG_URL/index-vault" \
    -H "Content-Type: application/json" \
    -d "$(python - "$target_request" "$MAX_FILES_PER_CALL" <<'PY'
import json,sys
payload = {"vault_path": sys.argv[1], "force": False}
payload["include_extensions"] = [".pdf"]
payload["exclude_extensions"] = [".md"]
try:
    max_files = int(sys.argv[2])
except Exception:
    max_files = 0
if max_files > 0:
    payload["max_files"] = max_files
print(json.dumps(payload))
PY
)" \
  )"

  if [ "$http_code" -ge 400 ]; then
    echo "Request failed for: $target_request"
    cat /tmp/reindex_remaining_pdf_only_resp.json
    echo
    exit 1
  fi
  cat /tmp/reindex_remaining_pdf_only_resp.json
  echo

  if [ "${THROTTLE_SECONDS}" != "0" ]; then
    sleep "$THROTTLE_SECONDS"
  fi
done

echo "Done."
echo "Verify: Scripts/list_remaining_missing_files.sh"
