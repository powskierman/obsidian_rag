from __future__ import annotations

from pathlib import Path
import re

from .normalize import parse_movie_title
from .schema import SourceMovieRecord


_LINE_PATTERN = re.compile(
    r"^\s*(?P<title>.+?)(?:\s*\((?P<year>19\d{2}|20\d{2})\))?(?:\s*\[(?P<quality>[^\]]+)\])?\s*$"
)


def parse_nas_title_list(txt_path: str | Path) -> list[SourceMovieRecord]:
    path = Path(txt_path)
    records: list[SourceMovieRecord] = []
    for index, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _LINE_PATTERN.match(stripped)
        title_text = stripped
        year = None
        quality = ""
        if match:
            title_text = match.group("title").strip()
            year_text = match.group("year")
            year = int(year_text) if year_text else None
            quality = str(match.group("quality") or "").strip()
        parsed = parse_movie_title(title_text)
        records.append(
            SourceMovieRecord(
                source_record_id=f"nas:{path.name}:{index}",
                source_type="NAS",
                source_path=str(path),
                raw_title=stripped,
                title=parsed.title,
                normalized_title=parsed.normalized_title,
                year=year or parsed.year_hint,
                version_label=parsed.version_label,
                version_key=parsed.version_key,
                quality=quality,
                raw_payload={"line": stripped},
            )
        )
    return records
