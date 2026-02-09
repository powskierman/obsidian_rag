#!/usr/bin/env bash
set -euo pipefail

LIGHTRAG_URL="${LIGHTRAG_URL:-http://localhost:8001}"
LIGHTRAG_EXCLUDE_PATHS="${LIGHTRAG_EXCLUDE_PATHS:-${LIGHTRAG_EXCLUDE_PATH_PATTERNS:-}}"
LIGHTRAG_BYPASS_REINDEX_GUARD="${LIGHTRAG_BYPASS_REINDEX_GUARD:-0}"
VAULT_PATH="${VAULT_PATH:-$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel}"
VAULT_PATH_IN_CONTAINER="${VAULT_PATH_IN_CONTAINER:-/app/vault}"
DATA_ROOT="${OBSIDIAN_RAG_DATA_DIR:-$HOME/obsidian_rag_local_data}"
LIGHTRAG_DIR_CONTAINER="${LIGHTRAG_DIR_CONTAINER:-${LIGHTRAG_DIR:-/app/lightrag_db}}"
DB_SUFFIX=""
if [[ "$LIGHTRAG_DIR_CONTAINER" == /app/lightrag_db/* ]]; then
  DB_SUFFIX="${LIGHTRAG_DIR_CONTAINER#/app/lightrag_db}"
fi
DB_PATH="${DB_PATH:-$DATA_ROOT/lightrag_db$DB_SUFFIX}"
INDEX_FILE="$DB_PATH/indexed_files.txt"
DRY_RUN="${DRY_RUN:-0}"
SCAN_ONLY="${SCAN_ONLY:-0}"
CONFIRM_INDEXING="${CONFIRM_INDEXING:-1}"
LIST_LIMIT="${LIST_LIMIT:-200}"
HEALTH_RETRIES="${HEALTH_RETRIES:-60}"
HEALTH_SLEEP_SECONDS="${HEALTH_SLEEP_SECONDS:-2}"
REQUEST_RETRIES="${REQUEST_RETRIES:-8}"
REQUEST_SLEEP_SECONDS="${REQUEST_SLEEP_SECONDS:-3}"
INCLUDE_LIST_FILE="${INCLUDE_LIST_FILE:-}"
INCLUDE_LIST_MODE="${INCLUDE_LIST_MODE:-only}" # only|missing
FORCE_REINDEX="${FORCE_REINDEX:-0}"
INDEX_AS_SINGLE_BATCH="${INDEX_AS_SINGLE_BATCH:-0}"

echo "LightRAG: $LIGHTRAG_URL"
echo "Vault:    $VAULT_PATH"
echo "Vault(in):$VAULT_PATH_IN_CONTAINER"
echo "DB:       $DB_PATH"
echo "Dry run:  $DRY_RUN"
echo "Scan only:$SCAN_ONLY"
echo "Confirm:  $CONFIRM_INDEXING"
echo "Force:    $FORCE_REINDEX"
echo "Single-batch mode: $INDEX_AS_SINGLE_BATCH"
if [ -n "$INCLUDE_LIST_FILE" ]; then
  echo "Include file: $INCLUDE_LIST_FILE (mode=$INCLUDE_LIST_MODE)"
fi
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
    elif p.startswith("app/vault/"):
        indexed.add(p[len("app/vault/"):])
    elif not p.startswith("/"):
        if p.startswith("./"):
            p = p[2:]
        indexed.add(p)

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

TARGET_MD=()
if [ -n "$INCLUDE_LIST_FILE" ]; then
  if [ ! -f "$INCLUDE_LIST_FILE" ]; then
    echo "ERROR: include list file not found: $INCLUDE_LIST_FILE"
    exit 2
  fi
  INCLUDE_MD=()
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    [ -z "$line" ] && continue
    case "$line" in
      \#*) continue ;;
    esac
    INCLUDE_MD+=("$line")
  done < "$INCLUDE_LIST_FILE"

  if [ "${#INCLUDE_MD[@]}" -eq 0 ]; then
    echo "ERROR: include list is empty: $INCLUDE_LIST_FILE"
    exit 2
  fi

  if [ "$INCLUDE_LIST_MODE" = "missing" ]; then
    for rel_path in "${INCLUDE_MD[@]}"; do
      for miss in "${MISSING_MD[@]}"; do
        if [ "$rel_path" = "$miss" ]; then
          TARGET_MD+=("$rel_path")
          break
        fi
      done
    done
  else
    TARGET_MD=("${INCLUDE_MD[@]}")
  fi
else
  TARGET_MD=("${MISSING_MD[@]}")
fi

if [ "${#TARGET_MD[@]}" -eq 0 ]; then
  echo "No target markdown files to process."
  exit 0
fi

echo "Target markdown files: ${#TARGET_MD[@]}"
if [ "${#TARGET_MD[@]}" -le "$LIST_LIMIT" ]; then
  printf '%s\n' "${TARGET_MD[@]}"
else
  printf '%s\n' "${TARGET_MD[@]:0:$LIST_LIMIT}"
  echo "... truncated list (${#TARGET_MD[@]} total, showing first $LIST_LIMIT)"
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

if [ "$INDEX_AS_SINGLE_BATCH" = "1" ]; then
  echo ">>> Reindexing in single request (files=${#TARGET_MD[@]})"
  tmp_include_paths="$(mktemp)"
  printf '%s\n' "${TARGET_MD[@]}" > "$tmp_include_paths"
  payload="$(python - "$VAULT_PATH_IN_CONTAINER" "$LIGHTRAG_EXCLUDE_PATHS" "$LIGHTRAG_BYPASS_REINDEX_GUARD" "$FORCE_REINDEX" "$tmp_include_paths" <<'PY'
import json,sys
exclude_paths = [token.strip() for token in sys.argv[2].split(",") if token.strip()]
bypass_guard = (sys.argv[3] if len(sys.argv) > 3 else "0") in {"1", "true", "TRUE", "yes", "YES"}
force_reindex = (sys.argv[4] if len(sys.argv) > 4 else "0") in {"1", "true", "TRUE", "yes", "YES"}
include_file = sys.argv[5]
with open(include_file, "r", encoding="utf-8") as f:
    include_paths = [ln.strip() for ln in f.readlines() if ln.strip()]
print(json.dumps({
  "vault_path": sys.argv[1],
  "force": force_reindex,
  "include_extensions": [".md"],
  "exclude_extensions": [".pdf"],
  "exclude_paths": exclude_paths,
  "include_paths": include_paths,
  "bypass_reindex_guard": bypass_guard
}))
PY
)"
  rm -f "$tmp_include_paths"

  attempt=1
  while true; do
    http_code="$(curl -sS -o /tmp/reindex_remaining_md_only_resp.json -w "%{http_code}" -X POST "$LIGHTRAG_URL/index-vault" \
      -H "Content-Type: application/json" \
      -d "$payload")"
    if [ "$http_code" -lt 400 ]; then
      cat /tmp/reindex_remaining_md_only_resp.json
      echo
      echo "Done."
      echo "Verify: Scripts/list_remaining_missing_files.sh"
      exit 0
    fi
    echo "WARN: single-batch attempt $attempt failed (HTTP $http_code)"
    cat /tmp/reindex_remaining_md_only_resp.json || true
    if [ "$attempt" -ge "$REQUEST_RETRIES" ]; then
      echo "ERROR: single-batch indexing failed after $REQUEST_RETRIES attempts."
      exit 1
    fi
    attempt=$((attempt + 1))
    sleep "$REQUEST_SLEEP_SECONDS"
  done
fi

failures=0
processed=0
for rel_path in "${TARGET_MD[@]}"; do
  processed=$((processed + 1))
  target_local="$VAULT_PATH/$rel_path"
  echo ">>> Reindexing MD file [$processed/${#TARGET_MD[@]}] $target_local"

  if [ "$DRY_RUN" = "1" ]; then
    continue
  fi

  payload="$(python - "$VAULT_PATH_IN_CONTAINER" "$LIGHTRAG_EXCLUDE_PATHS" "$LIGHTRAG_BYPASS_REINDEX_GUARD" "$rel_path" "$FORCE_REINDEX" <<'PY'
import json,sys
exclude_paths = [token.strip() for token in sys.argv[2].split(",") if token.strip()]
bypass_guard = (sys.argv[3] if len(sys.argv) > 3 else "0") in {"1", "true", "TRUE", "yes", "YES"}
rel_path = sys.argv[4]
force_reindex = (sys.argv[5] if len(sys.argv) > 5 else "0") in {"1", "true", "TRUE", "yes", "YES"}
print(json.dumps({
  "vault_path": sys.argv[1],
  "force": force_reindex,
  "include_extensions": [".md"],
  "exclude_extensions": [".pdf"],
  "exclude_paths": exclude_paths,
  "include_paths": [rel_path],
  "bypass_reindex_guard": bypass_guard
}))
PY
)"

  attempt=1
  success=0
  while true; do
    http_code="$(curl -sS -o /tmp/reindex_remaining_md_only_resp.json -w "%{http_code}" -X POST "$LIGHTRAG_URL/index-vault" \
      -H "Content-Type: application/json" \
      -d "$payload")"

    if [ "$http_code" -lt 400 ]; then
      success=1
      break
    fi

    if rg -q "LightRAG initializing" /tmp/reindex_remaining_md_only_resp.json && [ "$attempt" -lt "$REQUEST_RETRIES" ]; then
      echo "LightRAG initializing; retrying $attempt/$REQUEST_RETRIES for $rel_path..."
      sleep "$REQUEST_SLEEP_SECONDS"
      attempt=$((attempt + 1))
      continue
    fi

    break
  done

  if [ "$success" -eq 1 ]; then
    cat /tmp/reindex_remaining_md_only_resp.json
    echo
  else
    echo "Request failed for: $rel_path"
    cat /tmp/reindex_remaining_md_only_resp.json
    echo
    failures=$((failures + 1))
  fi
done

if [ "$failures" -gt 0 ]; then
  echo "Completed with failures: $failures"
  exit 1
fi

echo "Done."
echo "Verify: Scripts/list_remaining_missing_files.sh"
