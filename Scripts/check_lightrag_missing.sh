#!/bin/sh
# Check LightRAG indexed files vs vault files (md/pdf) inside the container.

set -e

docker exec -i obsidian-lightrag sh -lc 'python - <<'"'"'PY'"'"'
from pathlib import Path

vault = Path("/app/vault")
indexed_path = Path("/app/lightrag_db/indexed_files.txt")

files = [
    str(p) for p in vault.rglob("*")
    if p.is_file() and p.suffix.lower() in {".md", ".pdf"}
]
indexed = set(line.strip() for line in indexed_path.read_text().splitlines() if line.strip())

missing = [f for f in files if f not in indexed]

print("total_files:", len(files))
print("indexed_unique:", len(indexed))
print("missing:", len(missing))
print("sample_missing:", missing[:10])
PY'
