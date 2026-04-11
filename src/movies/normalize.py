from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

from src.indexing.canonical_metadata import slugify_text


_TRAILING_YEAR_PATTERN = re.compile(r"[\s._-]*[\(\[](?P<year>19\d{2}|20\d{2})[\)\]]\s*$")
_QUALITY_PATTERN = re.compile(r"\[(?:4k|uhd|hd|sd|1080p|720p|2160p|hdr)\]$", re.IGNORECASE)
_WHITESPACE_PATTERN = re.compile(r"\s+")

_VERSION_MARKERS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\bfinal cut\b", re.IGNORECASE), "Final Cut", "final-cut"),
    (re.compile(r"\bdirector'?s cut\b", re.IGNORECASE), "Director's Cut", "directors-cut"),
    (re.compile(r"\bextended (?:edition|cut)\b", re.IGNORECASE), "Extended Edition", "extended"),
    (re.compile(r"\btheatrical (?:cut|version)\b", re.IGNORECASE), "Theatrical Cut", "theatrical"),
    (re.compile(r"\bunrated\b", re.IGNORECASE), "Unrated", "unrated"),
    (re.compile(r"\bremaster(?:ed)?\b", re.IGNORECASE), "Remastered", "remastered"),
    (re.compile(r"\bspecial edition\b", re.IGNORECASE), "Special Edition", "special-edition"),
]


@dataclass(frozen=True)
class NormalizedMovieTitle:
    raw_title: str
    title: str
    normalized_title: str
    year_hint: int | None
    version_label: str
    version_key: str


def _collapse_ws(text: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", text).strip(" -._")


def _extract_version(text: str) -> tuple[str, str, str]:
    labels: list[str] = []
    keys: list[str] = []
    base = text
    for pattern, label, key in _VERSION_MARKERS:
        if pattern.search(base):
            labels.append(label)
            keys.append(key)
            base = pattern.sub("", base)
    version_label = ", ".join(dict.fromkeys(labels))
    version_key = "+".join(dict.fromkeys(keys)) if keys else "standard"
    return _collapse_ws(base), version_label, version_key


def parse_movie_title(raw_title: str) -> NormalizedMovieTitle:
    original = str(raw_title or "").strip()
    cleaned = original.replace("_", " ").replace(".", " ")
    cleaned = _collapse_ws(cleaned)
    cleaned = _QUALITY_PATTERN.sub("", cleaned).strip()

    year_hint = None
    year_match = _TRAILING_YEAR_PATTERN.search(cleaned)
    if year_match:
        year_hint = int(year_match.group("year"))
        cleaned = cleaned[: year_match.start()].strip()

    base, version_label, version_key = _extract_version(cleaned)
    base = _collapse_ws(base or cleaned or original)
    return NormalizedMovieTitle(
        raw_title=original,
        title=base,
        normalized_title=slugify_text(base),
        year_hint=year_hint,
        version_label=version_label,
        version_key=version_key,
    )


def normalize_imdb_id(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    match = re.search(r"(tt\d{5,10})", text)
    return match.group(1) if match else ""


def parse_year(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"(19\d{2}|20\d{2})", text)
    if not match:
        return None
    return int(match.group(1))


def parse_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def build_local_canonical_id(title: str, year: int | None, version_key: str) -> str:
    slug_parts = [slugify_text(title)]
    if year:
        slug_parts.append(str(year))
    if version_key and version_key != "standard":
        slug_parts.append(version_key)
    slug = "-".join(part for part in slug_parts if part)
    return f"movie:local:{slug}"


def movie_note_stem(title: str, year: int | None, version_label: str = "") -> str:
    stem = title.strip() or "Untitled Movie"
    if year:
        stem = f"{stem} ({year})"
    if version_label:
        stem = f"{stem} - {version_label}"
    return stem


def movie_note_filename(title: str, year: int | None, version_label: str = "") -> str:
    return movie_note_stem(title, year, version_label) + ".md"


def movie_note_relative_path(title: str, year: int | None, version_label: str = "") -> str:
    return str(Path("Media") / "Movies" / movie_note_filename(title, year, version_label))
