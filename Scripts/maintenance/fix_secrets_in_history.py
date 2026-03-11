#!/usr/bin/env python3
"""Inspect historical files for hard-coded secrets and print a scrubbed preview."""

import argparse
import re
import subprocess
import tempfile
from typing import Iterable

SECRET_PATTERNS = [
    (re.compile(r"sk-ant-api03-[A-Za-z0-9_-]+"), "your-anthropic-api-key-here"),
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "your-api-key-here"),
]


def scrub_content(content: str) -> str:
    cleaned = content
    for pattern, replacement in SECRET_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def fix_file_in_commit(commit_hash: str, filepath: str):
    """Replace matching secrets in a file from a specific commit."""
    try:
        result = subprocess.run(
            ["git", "show", f"{commit_hash}:{filepath}"],
            capture_output=True,
            text=True,
            check=True,
        )
        content = result.stdout
        content = scrub_content(content)

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".tmp") as f:
            f.write(content)
            temp_path = f.name

        return temp_path, content
    except subprocess.CalledProcessError:
        return None, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print scrubbed previews of historical files from a commit."
    )
    parser.add_argument("commit_hash", nargs="?", default="32c1ad3")
    parser.add_argument(
        "files",
        nargs="*",
        default=[".env.claude"],
        help="Paths to inspect from the target commit.",
    )
    return parser.parse_args()


def main(commit_hash: str, files: Iterable[str]) -> int:
    for filepath in files:
        temp_path, content = fix_file_in_commit(commit_hash, filepath)
        if temp_path:
            print(f"Fixed {filepath}")
            print(f"Content preview: {content[:200]}...")
        else:
            print(f"File {filepath} not found in commit")
    return 0


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(main(args.commit_hash, args.files))
