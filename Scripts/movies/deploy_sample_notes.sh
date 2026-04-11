#!/usr/bin/env bash
# deploy_sample_notes.sh
# Copies sample movie notes from staging into the vault's Media/Movies/ folder.
# Usage: bash Scripts/movies/deploy_sample_notes.sh [VAULT_PATH]
#
# Default vault path: /Volumes/work/vault
# Override: bash Scripts/movies/deploy_sample_notes.sh /path/to/vault

set -euo pipefail

VAULT="${1:-/Volumes/work/vault}"
DEST="$VAULT/Media/Movies"
SRC="$(dirname "$0")/sample_notes"

echo "Vault : $VAULT"
echo "Dest  : $DEST"
echo "Source: $SRC"
echo

if [[ ! -d "$VAULT" ]]; then
  echo "❌  Vault not found at $VAULT — pass the correct path as first argument."
  exit 1
fi

mkdir -p "$DEST"

for f in "$SRC"/*.md; do
  name="$(basename "$f")"
  echo "  → $name"
  cp "$f" "$DEST/$name"
done

echo
echo "✅  $(ls "$SRC"/*.md | wc -l | tr -d ' ') notes deployed to $DEST"
