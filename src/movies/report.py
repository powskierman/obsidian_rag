from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .schema import CanonicalMovie, ReviewItem, summarise_counts


def write_unresolved_report(review_items: Iterable[ReviewItem], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(review_items)
    lines = [
        "# Unresolved Movie Matches",
        "",
        f"- Review items: **{len(rows)}**",
        "",
    ]
    if not rows:
        lines.append("No unresolved movie matches.")
    else:
        for item in rows:
            lines.extend(
                [
                    f"## `{item.normalized_title}`",
                    "",
                    f"- Reason: `{item.reason}`",
                    f"- Candidate years: {', '.join(str(year) for year in item.candidate_years) or 'none'}",
                    f"- Suggested action: {item.suggested_action}",
                    "- Raw titles:",
                ]
            )
            for raw_title in item.raw_titles:
                lines.append(f"  - {raw_title}")
            lines.append("")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def write_summary_report(
    movies: Iterable[CanonicalMovie],
    review_items: Iterable[ReviewItem],
    output_path: str | Path,
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    movie_list = list(movies)
    review_list = list(review_items)
    counts = summarise_counts(movie_list, review_list)
    lines = [
        "# Movie Sync Summary",
        "",
        f"- Canonical movies: **{counts['movies']}**",
        f"- Resolved: **{counts['resolved']}**",
        f"- Needs review: **{counts['needs_review']}**",
        f"- Review queue items: **{counts['review_items']}**",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
