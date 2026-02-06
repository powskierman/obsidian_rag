#!/usr/bin/env bash
set -euo pipefail

VAULT_PATH="${VAULT_PATH:-$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel}"
DB_PATH="${DB_PATH:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/ data/graph_data/lightrag_db}"
INDEX_FILE="$DB_PATH/indexed_files.txt"

echo "Vault: $VAULT_PATH"
echo "DB:    $DB_PATH"
echo

python - "$VAULT_PATH" "$INDEX_FILE" <<'PY'
from pathlib import Path
import unicodedata
import sys
from collections import Counter

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
missing_pdf = [m for m in missing if m.lower().endswith(".pdf")]

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

