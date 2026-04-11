from __future__ import annotations

import csv
from pathlib import Path

from .normalize import normalize_imdb_id, parse_bool, parse_movie_title, parse_year
from .schema import SourceMovieRecord


_TITLE_FIELDS = ("Title", "title", "Name", "name", "Movie", "movie", "Sort Name")
_YEAR_FIELDS = ("Year", "year", "Release Year", "release_year")
_IMDB_FIELDS = ("IMDb ID", "IMDB ID", "imdb_id", "imdb")
_TMDB_FIELDS = ("TMDb ID", "TMDB ID", "tmdb_id", "tmdb")
_QUALITY_FIELDS = ("Quality", "quality", "Video Quality", "Resolution", "resolution")
_COLLECTION_FIELDS = ("Collection", "collection", "Franchise", "franchise", "Series", "series")
_TOP_250_FIELDS = ("Top 250", "top_250", "IMDb Top 250", "imdb_top_250")


def _first_value(row: dict[str, str], candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        value = row.get(candidate)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def parse_apple_export(csv_path: str | Path) -> list[SourceMovieRecord]:
    path = Path(csv_path)
    records: list[SourceMovieRecord] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader, start=1):
            raw_title = _first_value(row, _TITLE_FIELDS)
            if not raw_title:
                continue
            parsed = parse_movie_title(raw_title)
            year = parse_year(_first_value(row, _YEAR_FIELDS)) or parsed.year_hint
            records.append(
                SourceMovieRecord(
                    source_record_id=f"apple:{path.name}:{index}",
                    source_type="Apple",
                    source_path=str(path),
                    raw_title=raw_title,
                    title=parsed.title,
                    normalized_title=parsed.normalized_title,
                    year=year,
                    version_label=parsed.version_label,
                    version_key=parsed.version_key,
                    quality=_first_value(row, _QUALITY_FIELDS),
                    imdb_id=normalize_imdb_id(_first_value(row, _IMDB_FIELDS)),
                    tmdb_id=_first_value(row, _TMDB_FIELDS),
                    collection=_first_value(row, _COLLECTION_FIELDS),
                    top_250=parse_bool(_first_value(row, _TOP_250_FIELDS)),
                    raw_payload=dict(row),
                )
            )
    return records
