#!/usr/bin/env bash
set -euo pipefail

LIGHTRAG_URL="${LIGHTRAG_URL:-http://localhost:8001}"
LIGHTRAG_EXCLUDE_PATHS="${LIGHTRAG_EXCLUDE_PATHS:-${LIGHTRAG_EXCLUDE_PATH_PATTERNS:-}}"
LIGHTRAG_BYPASS_REINDEX_GUARD="${LIGHTRAG_BYPASS_REINDEX_GUARD:-0}"
VAULT_PATH="${VAULT_PATH:-$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel}"
VAULT_PATH_IN_CONTAINER="${VAULT_PATH_IN_CONTAINER:-/app/vault}"
DATA_ROOT="${OBSIDIAN_RAG_DATA_DIR:-$HOME/obsidian_rag_local_data}"
DB_PATH="${DB_PATH:-$DATA_ROOT/lightrag_db}"
INDEX_FILE="$DB_PATH/indexed_files.txt"
DRY_RUN="${DRY_RUN:-0}"
SCAN_ONLY="${SCAN_ONLY:-0}"
CONFIRM_INDEXING="${CONFIRM_INDEXING:-1}"
LIST_LIMIT="${LIST_LIMIT:-200}"
HEALTH_RETRIES="${HEALTH_RETRIES:-60}"
HEALTH_SLEEP_SECONDS="${HEALTH_SLEEP_SECONDS:-2}"
REQUEST_RETRIES="${REQUEST_RETRIES:-8}"
REQUEST_SLEEP_SECONDS="${REQUEST_SLEEP_SECONDS:-3}"

echo "LightRAG: $LIGHTRAG_URL"
echo "Vault:    $VAULT_PATH"
echo "Vault(in):$VAULT_PATH_IN_CONTAINER"
echo "DB:       $DB_PATH"
echo "Dry run:  $DRY_RUN"
echo "Scan only:$SCAN_ONLY"
echo "Confirm:  $CONFIRM_INDEXING"
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

verify_extension_filters() {
  local probe_code
  probe_code="$(curl -sS -o /tmp/reindex_md_only_probe.json -w "%{http_code}" \
    -X POST "$LIGHTRAG_URL/index-vault" \
    -H "Content-Type: application/json" \
    -d "{\"vault_path\":\"$VAULT_PATH_IN_CONTAINER\",\"include_extensions\":[\".txt\"]}")"

  if [ "$probe_code" -ne 400 ] || ! rg -q "No valid extensions to index" /tmp/reindex_md_only_probe.json; then
    echo "ERROR: Running LightRAG service does not appear to honor extension filters."
    echo "       Rebuild/restart lightrag-service before running MD-only reindex."
    echo "       Probe response:"
    cat /tmp/reindex_md_only_probe.json
    echo
    exit 1
  fi
}

if [ "$DRY_RUN" != "1" ]; then
  if ! wait_for_lightrag; then
    echo "ERROR: LightRAG is not reachable/ready at $LIGHTRAG_URL"
    exit 1
  fi
  verify_extension_filters
fi

tmp_folders="$(mktemp)"
tmp_missing_md="$(mktemp)"
python - "$VAULT_PATH" "$INDEX_FILE" "$tmp_folders" "$tmp_missing_md" <<'PY'
from pathlib import Path
import unicodedata
from collections import Counter
import sys

vault = Path(sys.argv[1]).expanduser()
idx = Path(sys.argv[2]).expanduser()
folders_path = Path(sys.argv[3]).expanduser()
missing_md_path = Path(sys.argv[4]).expanduser()

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
with folders_path.open("w", encoding="utf-8") as f:
    for folder, count in folders.most_common():
        f.write(f"{count}\t{folder}\n")

with missing_md_path.open("w", encoding="utf-8") as f:
    for path in missing_md:
        f.write(f"{path}\n")
PY

FOLDERS=()
while IFS= read -r line; do
  [ -n "$line" ] && FOLDERS+=("$line")
done < "$tmp_folders"

MISSING_MD=()
while IFS= read -r line; do
  [ -n "$line" ] && MISSING_MD+=("$line")
done < "$tmp_missing_md"

rm -f "$tmp_folders" "$tmp_missing_md"

if [ "${#FOLDERS[@]}" -eq 0 ]; then
  echo "No missing markdown files found. Nothing to reindex."
  exit 0
fi

echo "Missing markdown files: ${#MISSING_MD[@]}"
if [ "${#MISSING_MD[@]}" -le "$LIST_LIMIT" ]; then
  printf '%s\n' "${MISSING_MD[@]}"
else
  printf '%s\n' "${MISSING_MD[@]:0:$LIST_LIMIT}"
  echo "... truncated list (${#MISSING_MD[@]} total, showing first $LIST_LIMIT)"
fi
echo

echo "Missing markdown folders (desc):"
printf '%s\n' "${FOLDERS[@]}"
echo

if [ "$SCAN_ONLY" = "1" ] || [ "$DRY_RUN" = "1" ]; then
  echo "Scan completed. No indexing performed."
  exit 0
fi

if [ "$CONFIRM_INDEXING" = "1" ]; then
  if [ -t 0 ]; then
    read -r -p "Proceed with indexing these markdown files? [y/N] " confirm
    case "$confirm" in
      y|Y) ;;
      *) echo "Cancelled."; exit 0 ;;
    esac
  else
    echo "ERROR: confirmation required but no interactive TTY."
    echo "Set CONFIRM_INDEXING=0 to run non-interactively."
    exit 1
  fi
fi

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

  payload="$(python - "$target_request" "$LIGHTRAG_EXCLUDE_PATHS" "$LIGHTRAG_BYPASS_REINDEX_GUARD" <<'PY'
import json,sys
exclude_paths = [token.strip() for token in sys.argv[2].split(",") if token.strip()]
bypass_guard = (sys.argv[3] if len(sys.argv) > 3 else "0") in {"1", "true", "TRUE", "yes", "YES"}
print(json.dumps({
  "vault_path": sys.argv[1],
  "force": False,
  "include_extensions": [".md"],
  "exclude_extensions": [".pdf"],
  "exclude_paths": exclude_paths,
  "bypass_reindex_guard": bypass_guard
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
