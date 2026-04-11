from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import re
from string import Template
from typing import Iterable

from .normalize import movie_note_filename
from .schema import CanonicalMovie


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATE_PATH = REPO_ROOT / "templates" / "movies" / "movie_note.md.tpl"
USER_NOTES_START = "<!-- MOVIE-USER-NOTES-START -->"
USER_NOTES_END = "<!-- MOVIE-USER-NOTES-END -->"
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _load_template(template_path: Path | None = None) -> Template:
    path = template_path or DEFAULT_TEMPLATE_PATH
    return Template(path.read_text(encoding="utf-8"))


def _extract_user_notes(existing_text: str) -> str:
    if USER_NOTES_START not in existing_text or USER_NOTES_END not in existing_text:
        return ""
    _, remainder = existing_text.split(USER_NOTES_START, 1)
    content, _ = remainder.split(USER_NOTES_END, 1)
    return content.strip("\n")


def _extract_frontmatter_fields(existing_text: str) -> dict[str, str]:
    match = FRONTMATTER_PATTERN.match(existing_text)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("-") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        fields[key.strip()] = value.strip().strip("'\"")
    return fields


def _preserve_curation(movie: CanonicalMovie, existing_text: str) -> CanonicalMovie:
    metadata = _extract_frontmatter_fields(existing_text)
    preserved_rating = movie.your_rating
    preserved_watched = movie.watched
    if "your_rating" in metadata and str(metadata.get("your_rating") or "").strip():
        preserved_rating = str(metadata.get("your_rating") or "").strip()
    watched_value = str(metadata.get("watched") or "").strip().lower()
    if watched_value in {"1", "true", "yes"}:
        preserved_watched = True
    elif watched_value in {"0", "false", "no"}:
        preserved_watched = False
    return replace(movie, your_rating=preserved_rating, watched=preserved_watched)


def _frontmatter(movie: CanonicalMovie) -> dict:
    return {
        "id": movie.canonical_id,
        "kind": "movie",
        "title": movie.title,
        "year": movie.year,
        "imdb_id": movie.imdb_id,
        "tmdb_id": movie.tmdb_id,
        "provenance": movie.provenance,
        "collection": movie.collection,
        "quality_apple": movie.quality_apple,
        "quality_nas": movie.quality_nas,
        "top_250": movie.top_250,
        "your_rating": movie.your_rating,
        "watched": movie.watched,
        "match_status": movie.match_status,
        "version_notes": movie.version_notes,
        "duplicate_group": movie.duplicate_group,
        "review_required": movie.review_required,
    }


def _yaml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None or value == "":
        return '""'
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if re.search(r"[:#\[\]\{\},]|^\s|\s$", text):
        return json.dumps(text)
    return text


def _render_frontmatter(mapping: dict) -> str:
    lines: list[str] = []
    for key, value in mapping.items():
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
                continue
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_yaml_scalar(item)}")
            continue
        lines.append(f"{key}: {_yaml_scalar(value)}")
    return "\n".join(lines)


def _string_value(value: object, fallback: str = "unknown") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def render_movie_note(
    movie: CanonicalMovie,
    *,
    template_path: Path | None = None,
    existing_text: str = "",
) -> tuple[CanonicalMovie, str]:
    preserved_movie = _preserve_curation(movie, existing_text) if existing_text else movie
    user_notes = _extract_user_notes(existing_text) if existing_text else ""
    template = _load_template(template_path)
    frontmatter = _render_frontmatter(_frontmatter(preserved_movie)).strip()
    body = template.substitute(
        title=preserved_movie.title,
        canonical_id=preserved_movie.canonical_id,
        imdb_id_display=_string_value(preserved_movie.imdb_id),
        tmdb_id_display=_string_value(preserved_movie.tmdb_id),
        year_display=_string_value(preserved_movie.year, fallback="unknown"),
        collection_display=_string_value(preserved_movie.collection),
        match_status=preserved_movie.match_status,
        review_required="yes" if preserved_movie.review_required else "no",
        provenance_bullets="\n".join(f"- {item}" for item in preserved_movie.provenance) or "- unknown",
        quality_apple_display=_string_value(preserved_movie.quality_apple),
        quality_nas_display=_string_value(preserved_movie.quality_nas),
        duplicate_group=_string_value(preserved_movie.duplicate_group),
        version_notes_display=_string_value(preserved_movie.version_notes),
        top_250_display="yes" if preserved_movie.top_250 else "no",
        directors_display=", ".join(preserved_movie.directors) or "unknown",
        cast_display=", ".join(preserved_movie.cast) or "unknown",
        genres_display=", ".join(preserved_movie.genres) or "unknown",
        runtime_display=f"{preserved_movie.runtime_minutes} min" if preserved_movie.runtime_minutes else "unknown",
        imdb_rating_display=str(preserved_movie.imdb_rating) if preserved_movie.imdb_rating is not None else "unknown",
        user_notes=user_notes,
    ).strip()
    return preserved_movie, f"---\n{frontmatter}\n---\n\n{body}\n"


def write_movie_notes(
    movies: Iterable[CanonicalMovie],
    *,
    vault_root: str | Path,
    template_path: str | Path | None = None,
) -> list[Path]:
    root = Path(vault_root)
    movie_dir = root / "Media" / "Movies"
    movie_dir.mkdir(parents=True, exist_ok=True)
    rendered_paths: list[Path] = []
    template = Path(template_path) if template_path else None

    for movie in movies:
        path = movie_dir / movie_note_filename(movie.title, movie.year, movie.version_notes)
        existing_text = path.read_text(encoding="utf-8") if path.exists() else ""
        _, note_text = render_movie_note(movie, template_path=template, existing_text=existing_text)
        path.write_text(note_text, encoding="utf-8")
        rendered_paths.append(path)
    return rendered_paths
