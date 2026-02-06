#!/usr/bin/env python3
"""
Compare two LightRAG benchmark JSON reports.
"""

import argparse
import json
from pathlib import Path


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fmt(value):
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two LightRAG benchmark reports")
    parser.add_argument("report_a")
    parser.add_argument("report_b")
    args = parser.parse_args()

    a = _load(args.report_a)
    b = _load(args.report_b)

    fields = [
        ("elapsed_seconds", "elapsed_seconds"),
        ("response_body.total_files", ("response_body", "total_files")),
        ("response_body.newly_indexed", ("response_body", "newly_indexed")),
        ("chunk_stats_delta.chunk_count", ("chunk_stats_delta", "chunk_count")),
        ("chunk_stats_delta.token_total", ("chunk_stats_delta", "token_total")),
        ("chunk_stats_delta.content_chars_total", ("chunk_stats_delta", "content_chars_total")),
    ]

    print("Report A:", args.report_a)
    print("Report B:", args.report_b)
    print("")

    for label, key in fields:
        if isinstance(key, tuple):
            a_val = a
            b_val = b
            for k in key:
                a_val = a_val.get(k) if isinstance(a_val, dict) else None
                b_val = b_val.get(k) if isinstance(b_val, dict) else None
        else:
            a_val = a.get(key)
            b_val = b.get(key)

        delta = None
        if isinstance(a_val, (int, float)) and isinstance(b_val, (int, float)):
            delta = b_val - a_val

        delta_str = f" (Δ {delta:+.2f})" if isinstance(delta, float) else f" (Δ {delta:+d})" if isinstance(delta, int) else ""
        print(f"{label:35s} A={_fmt(a_val):>8s}  B={_fmt(b_val):>8s}{delta_str}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
