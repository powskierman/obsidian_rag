#!/usr/bin/env python3
"""
Create a random subset of Markdown notes from a vault into a target folder.
"""

import argparse
import os
import random
import shutil
from pathlib import Path


def _is_valid_note(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() != ".md":
        return False
    parts = path.parts
    if any(part.startswith(".") or part.startswith("_") for part in parts):
        return False
    obsidian_skip = [".obsidian", ".trash", "Templates", "Excalidraw"]
    if any(skip_dir in str(path) for skip_dir in obsidian_skip):
        return False
    try:
        return path.stat().st_size > 0
    except OSError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a random subset of notes.")
    parser.add_argument("vault_path", help="Path to the source Obsidian vault")
    parser.add_argument("target_path", help="Path to the subset output folder")
    parser.add_argument("-n", "--count", type=int, required=True, help="Number of notes to copy")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--clean", action="store_true", help="Delete target folder before copying")

    args = parser.parse_args()

    vault_path = Path(args.vault_path).expanduser().resolve()
    target_path = Path(args.target_path).expanduser().resolve()

    if not vault_path.exists():
        print(f"Vault path not found: {vault_path}")
        return 1

    if args.clean and target_path.exists():
        shutil.rmtree(target_path)

    target_path.mkdir(parents=True, exist_ok=True)

    notes = [path for path in vault_path.rglob("*.md") if _is_valid_note(path)]
    if not notes:
        print("No notes found to sample.")
        return 1

    if args.count <= 0:
        print("Count must be greater than 0.")
        return 1

    if args.count > len(notes):
        print(f"Requested {args.count} notes but only {len(notes)} available.")
        return 1

    if args.seed is not None:
        random.seed(args.seed)

    selected = random.sample(notes, args.count)

    for note in selected:
        rel_path = note.relative_to(vault_path)
        dest = target_path / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(note, dest)

    print(f"Copied {len(selected)} notes to {target_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
