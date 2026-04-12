#!/usr/bin/env bash
# deploy_sample_notes.sh
# Copies sample movie notes + Movie Template into the vault.
# Usage: bash Scripts/movies/deploy_sample_notes.sh [VAULT_PATH]
#
# Default vault path: /Volumes/work/vault
# Override: bash Scripts/movies/deploy_sample_notes.sh /path/to/vault

set -euo pipefail

VAULT="${1:-/Volumes/work/vault}"
MOVIES_DEST="$VAULT/Media/Movies"
TMPL_DEST="$VAULT/Templates"
SRC="$(cd "$(dirname "$0")/sample_notes" && pwd)"

echo "Vault      : $VAULT"
echo "Movies dest: $MOVIES_DEST"
echo "Template   : $TMPL_DEST"
echo

if [[ ! -d "$VAULT" ]]; then
  echo "❌  Vault not found at $VAULT — pass the correct path as first argument."
  exit 1
fi

# ── Movie notes ───────────────────────────────────────────────────────
mkdir -p "$MOVIES_DEST"
count=0
for f in "$SRC"/*.md; do
  name="$(basename "$f")"
  [[ "$name" == "Movie Template.md" ]] && continue   # handled separately
  echo "  [note]     $name"
  cp "$f" "$MOVIES_DEST/$name"
  (( count++ )) || true
done

# ── Templater template ────────────────────────────────────────────────
if [[ -d "$TMPL_DEST" ]]; then
  echo "  [template] Movie Template.md → Templates/"
  cp "$SRC/Movie Template.md" "$TMPL_DEST/Movie Template.md"
else
  echo "  ⚠️  Templates folder not found at $TMPL_DEST — copy Movie Template.md manually."
fi

echo
echo "✅  $count movie notes → $MOVIES_DEST"
echo "✅  Template → $TMPL_DEST/Movie Template.md"
