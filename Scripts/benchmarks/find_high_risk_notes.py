#!/usr/bin/env python3
"""
Identify high-risk notes for LightRAG extraction timeouts/noisy parsing.
"""

import argparse
import json
import re
from pathlib import Path


def _is_note(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".md"


def _score_note(text: str) -> dict:
    lines = text.splitlines()
    total_lines = len(lines)
    total_chars = len(text)

    table_sep_re = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$")
    ascii_arrow_re = re.compile(r"(<--|-->|<->)")

    table_like = 0
    table_seps = 0
    ascii_diagram = 0
    very_long_lines = 0

    for line in lines:
        s = line.strip()
        if s.count("|") >= 3:
            table_like += 1
        if table_sep_re.match(s):
            table_seps += 1
        if ascii_arrow_re.search(s) and "|" in s:
            ascii_diagram += 1
        if len(s) > 240:
            very_long_lines += 1

    risk = 0
    risk += total_chars / 2000
    risk += table_like * 0.8
    risk += table_seps * 0.5
    risk += ascii_diagram * 1.2
    risk += very_long_lines * 0.6

    return {
        "total_chars": total_chars,
        "total_lines": total_lines,
        "table_like_lines": table_like,
        "table_separator_lines": table_seps,
        "ascii_diagram_lines": ascii_diagram,
        "very_long_lines": very_long_lines,
        "risk_score": round(risk, 2),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Find high-risk notes for LightRAG indexing.")
    parser.add_argument("vault_path", help="Path to vault/subset directory")
    parser.add_argument("--top", type=int, default=20, help="Show top N high-risk notes")
    parser.add_argument("--min-score", type=float, default=20.0, help="Minimum risk score to include")
    parser.add_argument("--json-out", default="", help="Optional output JSON path")
    args = parser.parse_args()

    vault = Path(args.vault_path).expanduser().resolve()
    if not vault.exists():
        print(f"Vault not found: {vault}")
        return 1

    results = []
    for path in vault.rglob("*.md"):
        if not _is_note(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = path.read_text(encoding="latin-1")
            except Exception:
                continue
        except Exception:
            continue

        metrics = _score_note(text)
        if metrics["risk_score"] >= args.min_score:
            results.append({"path": str(path), **metrics})

    results.sort(key=lambda x: x["risk_score"], reverse=True)

    print(f"Found {len(results)} high-risk notes (min-score={args.min_score})")
    for row in results[: args.top]:
        print(
            f"{row['risk_score']:7.2f}  chars={row['total_chars']:6d}  "
            f"tables={row['table_like_lines']:4d}  ascii={row['ascii_diagram_lines']:3d}  "
            f"long={row['very_long_lines']:3d}  {row['path']}"
        )

    if args.json_out:
        out_path = Path(args.json_out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Saved JSON report: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
