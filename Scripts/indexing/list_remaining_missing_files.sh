#!/usr/bin/env bash
set -euo pipefail

VAULT_PATH="${VAULT_PATH:-$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel}"
OBSIDIAN_RAG_DATA_DIR="${OBSIDIAN_RAG_DATA_DIR:-$HOME/obsidian_rag_local_data}"
DB_PATH="${DB_PATH:-$OBSIDIAN_RAG_DATA_DIR/lightrag_db}"
INDEX_FILE="$DB_PATH/indexed_files.txt"
DOC_STATUS_FILE="$DB_PATH/kv_store_doc_status.json"

echo "Vault: $VAULT_PATH"
echo "DB:    $DB_PATH"
echo

python - "$VAULT_PATH" "$INDEX_FILE" "$DOC_STATUS_FILE" <<'PY'
from pathlib import Path
import unicodedata
import sys
import json
from collections import Counter

vault = Path(sys.argv[1]).expanduser()
idx = Path(sys.argv[2]).expanduser()
doc_status = Path(sys.argv[3]).expanduser()

if not vault.exists():
    print("ERROR: vault not found", file=sys.stderr)
    sys.exit(2)
def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)

# Prefer doc_status as authoritative source. Fall back to indexed_files.txt.
indexed = set()
status_counter = Counter()
source_mode = "indexed_files.txt"

if doc_status.exists():
    try:
        data = json.loads(doc_status.read_text(encoding="utf-8", errors="ignore"))
        for v in data.values():
            if not isinstance(v, dict):
                continue
            fp = v.get("file_path") or ""
            st = v.get("status", "unknown")
            if isinstance(fp, str) and fp:
                p = fp
                if p.startswith("/app/vault/"):
                    p = p[len("/app/vault/"):]
                elif p.startswith("app/vault/"):
                    p = p[len("app/vault/"):]
                elif p.startswith("./"):
                    p = p[2:]
                if not p.startswith("/"):
                    indexed.add(p)
                    status_counter[st] += 1
        source_mode = "kv_store_doc_status.json"
    except Exception:
        # If doc_status is malformed, silently fall back to indexed_files.
        indexed.clear()
        status_counter.clear()

if not indexed:
    if not idx.exists():
        print("ERROR: neither kv_store_doc_status.json nor indexed_files.txt can be used", file=sys.stderr)
        sys.exit(3)
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
    source_mode = "indexed_files.txt"

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
missing_pdf = [m for m in missing if m.lower().endswith(".pdf")]

print(f"Index source: {source_mode}")
if status_counter:
    print("Doc status counts:")
    for k in sorted(status_counter):
        print(f"  {k}: {status_counter[k]}")
print()

print(f"Missing total: {len(missing)}")
print(f"Missing md:    {len(missing_md)}")
print(f"Missing pdf:   {len(missing_pdf)}")
print()

print("Top folders:")
folder_counts = Counter(str(Path(m).parent) for m in missing)
for folder, count in folder_counts.most_common(20):
    print(f"{count}\t{folder}")
print()

print("[Missing markdown files]")
for p in missing_md:
    print(p)
print()

print("[Missing PDF files]")
for p in missing_pdf:
    print(p)
PY
