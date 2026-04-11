from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]


def default_movies_data_dir() -> Path:
    data_dir = str(os.getenv("OBSIDIAN_RAG_DATA_DIR", "")).strip()
    if data_dir:
        return Path(data_dir).expanduser() / "movies"
    return REPO_ROOT / "data" / "movies"


def default_database_path() -> Path:
    return default_movies_data_dir() / "canonical_movies.db"


def default_report_dir() -> Path:
    return default_movies_data_dir() / "reports"


def default_cache_dir() -> Path:
    return default_movies_data_dir() / "cache"


@dataclass
class SourceMovieRecord:
    source_record_id: str
    source_type: str
    source_path: str
    raw_title: str
    title: str
    normalized_title: str
    year: int | None
    version_label: str = ""
    version_key: str = "standard"
    quality: str = ""
    imdb_id: str = ""
    tmdb_id: str = ""
    collection: str = ""
    top_250: bool | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class CanonicalMovie:
    canonical_id: str
    title: str
    year: int | None
    imdb_id: str = ""
    tmdb_id: str = ""
    provenance: list[str] = field(default_factory=list)
    match_status: str = "resolved"
    duplicate_group: str = ""
    version_notes: str = ""
    collection: str = ""
    quality_apple: str = ""
    quality_nas: str = ""
    top_250: bool = False
    your_rating: str = ""
    watched: bool = False
    directors: list[str] = field(default_factory=list)
    cast: list[str] = field(default_factory=list)
    genres: list[str] = field(default_factory=list)
    runtime_minutes: int | None = None
    imdb_rating: float | None = None
    review_required: bool = False
    source_record_ids: list[str] = field(default_factory=list)
    source_titles: list[str] = field(default_factory=list)


@dataclass
class ReviewItem:
    review_key: str
    normalized_title: str
    candidate_years: list[int] = field(default_factory=list)
    source_record_ids: list[str] = field(default_factory=list)
    reason: str = ""
    suggested_action: str = ""
    raw_titles: list[str] = field(default_factory=list)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(db_path: Path) -> None:
    conn = _connect(db_path)
    with conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS canonical_movies (
                canonical_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                year INTEGER,
                imdb_id TEXT,
                tmdb_id TEXT,
                provenance_json TEXT NOT NULL,
                match_status TEXT NOT NULL,
                duplicate_group TEXT,
                version_notes TEXT,
                collection_name TEXT,
                quality_apple TEXT,
                quality_nas TEXT,
                top_250 INTEGER NOT NULL DEFAULT 0,
                your_rating TEXT,
                watched INTEGER NOT NULL DEFAULT 0,
                directors_json TEXT NOT NULL,
                cast_json TEXT NOT NULL,
                genres_json TEXT NOT NULL,
                runtime_minutes INTEGER,
                imdb_rating REAL,
                review_required INTEGER NOT NULL DEFAULT 0,
                source_record_ids_json TEXT NOT NULL,
                source_titles_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS source_records (
                source_record_id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                source_path TEXT NOT NULL,
                raw_title TEXT NOT NULL,
                title TEXT NOT NULL,
                normalized_title TEXT NOT NULL,
                year INTEGER,
                version_label TEXT,
                version_key TEXT NOT NULL,
                quality TEXT,
                imdb_id TEXT,
                tmdb_id TEXT,
                collection_name TEXT,
                top_250 INTEGER,
                raw_payload_json TEXT NOT NULL,
                matched_canonical_id TEXT,
                imported_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS review_queue (
                review_key TEXT PRIMARY KEY,
                normalized_title TEXT NOT NULL,
                candidate_years_json TEXT NOT NULL,
                source_record_ids_json TEXT NOT NULL,
                raw_titles_json TEXT NOT NULL,
                reason TEXT NOT NULL,
                suggested_action TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
    conn.close()


def _load_existing_curation(conn: sqlite3.Connection) -> dict[str, tuple[str, bool]]:
    rows = conn.execute(
        "SELECT canonical_id, your_rating, watched FROM canonical_movies"
    ).fetchall()
    return {
        str(row["canonical_id"]): (
            str(row["your_rating"] or ""),
            bool(row["watched"]),
        )
        for row in rows
    }


def persist_snapshot(
    db_path: Path,
    movies: Iterable[CanonicalMovie],
    source_records: Iterable[SourceMovieRecord],
    review_items: Iterable[ReviewItem],
) -> None:
    ensure_schema(db_path)
    conn = _connect(db_path)
    existing_curation = _load_existing_curation(conn)
    imported_at = _utc_now()

    with conn:
        conn.execute("DELETE FROM canonical_movies")
        conn.execute("DELETE FROM source_records")
        conn.execute("DELETE FROM review_queue")

        for movie in movies:
            current_rating, current_watched = existing_curation.get(
                movie.canonical_id, ("", False)
            )
            if not movie.your_rating and current_rating:
                movie.your_rating = current_rating
            if not movie.watched and current_watched:
                movie.watched = current_watched

            conn.execute(
                """
                INSERT INTO canonical_movies (
                    canonical_id, kind, title, year, imdb_id, tmdb_id,
                    provenance_json, match_status, duplicate_group, version_notes,
                    collection_name, quality_apple, quality_nas, top_250, your_rating,
                    watched, directors_json, cast_json, genres_json, runtime_minutes,
                    imdb_rating, review_required, source_record_ids_json, source_titles_json,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    movie.canonical_id,
                    "movie",
                    movie.title,
                    movie.year,
                    movie.imdb_id,
                    movie.tmdb_id,
                    _json_dump(movie.provenance),
                    movie.match_status,
                    movie.duplicate_group,
                    movie.version_notes,
                    movie.collection,
                    movie.quality_apple,
                    movie.quality_nas,
                    1 if movie.top_250 else 0,
                    movie.your_rating,
                    1 if movie.watched else 0,
                    _json_dump(movie.directors),
                    _json_dump(movie.cast),
                    _json_dump(movie.genres),
                    movie.runtime_minutes,
                    movie.imdb_rating,
                    1 if movie.review_required else 0,
                    _json_dump(movie.source_record_ids),
                    _json_dump(movie.source_titles),
                    _json_dump(asdict(movie)),
                    imported_at,
                    imported_at,
                ),
            )

        canonical_lookup: dict[str, str] = {}
        for movie in movies:
            for record_id in movie.source_record_ids:
                canonical_lookup[record_id] = movie.canonical_id

        for record in source_records:
            conn.execute(
                """
                INSERT INTO source_records (
                    source_record_id, source_type, source_path, raw_title, title,
                    normalized_title, year, version_label, version_key, quality,
                    imdb_id, tmdb_id, collection_name, top_250, raw_payload_json,
                    matched_canonical_id, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.source_record_id,
                    record.source_type,
                    record.source_path,
                    record.raw_title,
                    record.title,
                    record.normalized_title,
                    record.year,
                    record.version_label,
                    record.version_key,
                    record.quality,
                    record.imdb_id,
                    record.tmdb_id,
                    record.collection,
                    None if record.top_250 is None else (1 if record.top_250 else 0),
                    _json_dump(record.raw_payload),
                    canonical_lookup.get(record.source_record_id, ""),
                    imported_at,
                ),
            )

        for item in review_items:
            conn.execute(
                """
                INSERT INTO review_queue (
                    review_key, normalized_title, candidate_years_json, source_record_ids_json,
                    raw_titles_json, reason, suggested_action, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.review_key,
                    item.normalized_title,
                    _json_dump(item.candidate_years),
                    _json_dump(item.source_record_ids),
                    _json_dump(item.raw_titles),
                    item.reason,
                    item.suggested_action,
                    imported_at,
                ),
            )
    conn.close()


def load_canonical_movies(db_path: Path) -> list[CanonicalMovie]:
    ensure_schema(db_path)
    conn = _connect(db_path)
    rows = conn.execute("SELECT * FROM canonical_movies ORDER BY title, year, canonical_id").fetchall()
    movies: list[CanonicalMovie] = []
    for row in rows:
        movies.append(
            CanonicalMovie(
                canonical_id=str(row["canonical_id"]),
                title=str(row["title"]),
                year=row["year"],
                imdb_id=str(row["imdb_id"] or ""),
                tmdb_id=str(row["tmdb_id"] or ""),
                provenance=json.loads(row["provenance_json"] or "[]"),
                match_status=str(row["match_status"] or "resolved"),
                duplicate_group=str(row["duplicate_group"] or ""),
                version_notes=str(row["version_notes"] or ""),
                collection=str(row["collection_name"] or ""),
                quality_apple=str(row["quality_apple"] or ""),
                quality_nas=str(row["quality_nas"] or ""),
                top_250=bool(row["top_250"]),
                your_rating=str(row["your_rating"] or ""),
                watched=bool(row["watched"]),
                directors=json.loads(row["directors_json"] or "[]"),
                cast=json.loads(row["cast_json"] or "[]"),
                genres=json.loads(row["genres_json"] or "[]"),
                runtime_minutes=row["runtime_minutes"],
                imdb_rating=row["imdb_rating"],
                review_required=bool(row["review_required"]),
                source_record_ids=json.loads(row["source_record_ids_json"] or "[]"),
                source_titles=json.loads(row["source_titles_json"] or "[]"),
            )
        )
    conn.close()
    return movies


def summarise_counts(movies: Iterable[CanonicalMovie], review_items: Iterable[ReviewItem]) -> dict[str, int]:
    movie_list = list(movies)
    review_list = list(review_items)
    return {
        "movies": len(movie_list),
        "review_items": len(review_list),
        "resolved": sum(1 for movie in movie_list if movie.match_status == "resolved"),
        "needs_review": sum(1 for movie in movie_list if movie.review_required),
    }
