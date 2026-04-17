from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import getpass
import os
from pathlib import Path
import re
from typing import Any
import unicodedata

from dotenv import load_dotenv
import requests
import yaml

from src.indexing.canonical_metadata import slugify_text


_FRONTMATTER_START = "---"
_YEAR_SUFFIX_PATTERN = re.compile(r"\s*[\(\[](?P<year>\d{4})[\)\]]\s*$")
_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
_CLASSIC_REMAKE_PATTERN = re.compile(r"\b(classic|remake)\b", re.IGNORECASE)
_ORDERED_FRONTMATTER_KEYS = [
    "id",
    "kind",
    "title",
    "year",
    "imdb_id",
    "tmdb_id",
    "jellyfin_item_id",
    "jellyfin_path",
    "jellyfin_url",
    "director",
    "directors",
    "genre",
    "genres",
    "runtime_min",
    "content_rating",
    "imdb_rating",
    "description",
    "poster_url",
    "your_rating",
    "watched",
    "shortlist",
    "mood",
    "energy",
    "watch_context",
    "rewatchable",
    "avoid_if",
    "provenance",
    "collection",
    "quality_apple",
    "quality_nas",
    "top_250",
    "imdb_top_250_rank",
    "match_status",
    "version_notes",
    "streaming_ca",
    "created",
    "tags",
]


def _normalize_base_url(base_url: str) -> str:
    normalized = str(base_url or "").strip().rstrip("/")
    for suffix in ("/web/index.html", "/web/index.htm", "/web"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized.rstrip("/")


def _ascii_fold(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return normalized.encode("ascii", "ignore").decode("ascii")


def _compact_title_key(value: str) -> str:
    text = _ascii_fold(value).lower()
    text = text.replace("&", " and ")
    text = text.replace("'", "")
    text = _CLASSIC_REMAKE_PATTERN.sub("", text)
    text = _NON_ALNUM_PATTERN.sub("", text)
    return text


def _strip_leading_article(value: str) -> str:
    text = str(value or "").strip()
    lowered = text.lower()
    for prefix in ("the ", "a ", "an "):
        if lowered.startswith(prefix):
            return text[len(prefix):].strip()
    return text


def _stem_without_year(value: str) -> str:
    stem = str(value or "").strip()
    match = _YEAR_SUFFIX_PATTERN.search(stem)
    if match:
        return stem[: match.start()].strip()
    return stem


def _title_alias_keys(value: str) -> set[str]:
    keys: set[str] = set()
    for variant in (value, _strip_leading_article(value)):
        compact = _compact_title_key(variant)
        if compact:
            keys.add(compact)
    return keys


def _movie_alias_keys_from_path(path_value: str) -> set[str]:
    if not path_value:
        return set()
    path = Path(path_value)
    keys: set[str] = set()
    for candidate in (path.stem, path.parent.name):
        stem = _stem_without_year(candidate)
        keys.update(_title_alias_keys(stem))
    return keys


@dataclass(frozen=True)
class JellyfinMovie:
    item_id: str
    title: str
    year: int | None
    path: str
    imdb_id: str
    tmdb_id: str
    directors: list[str]
    genres: list[str]
    runtime_min: int | None
    content_rating: str
    imdb_rating: float | None
    overview: str

    @property
    def normalized_title(self) -> str:
        return slugify_text(self.title)

    @property
    def alias_keys(self) -> set[str]:
        keys = _title_alias_keys(self.title)
        keys.update(_movie_alias_keys_from_path(self.path))
        return keys


@dataclass(frozen=True)
class NoteMatch:
    note_path: Path
    movie: JellyfinMovie
    reason: str


def _split_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    if not markdown.startswith(_FRONTMATTER_START):
        return {}, markdown
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != _FRONTMATTER_START:
        return {}, markdown
    end_idx: int | None = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == _FRONTMATTER_START:
            end_idx = idx
            break
    if end_idx is None:
        return {}, markdown
    frontmatter_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1 :]).lstrip("\n")
    try:
        parsed = yaml.safe_load(frontmatter_text) or {}
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    return parsed, body


def _render_note(frontmatter: dict[str, Any], body: str) -> str:
    ordered: dict[str, Any] = {}
    for key in _ORDERED_FRONTMATTER_KEYS:
        if key in frontmatter:
            ordered[key] = frontmatter[key]
    for key, value in frontmatter.items():
        if key not in ordered:
            ordered[key] = value
    dumped = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=False).strip()
    clean_body = body.lstrip("\n")
    if clean_body:
        return f"---\n{dumped}\n---\n\n{clean_body}\n"
    return f"---\n{dumped}\n---\n"


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [text]


def _normalize_provenance(value: Any) -> set[str]:
    raw_items = _text_list(value)
    normalized: set[str] = set()
    for item in raw_items:
        for part in item.replace("+", ",").split(","):
            cleaned = part.strip()
            if cleaned:
                normalized.add(cleaned)
    return normalized


def _normalize_imdb_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("tt"):
        return text
    return ""


def _normalize_tmdb_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text


def _auth_header_value(
    *,
    token: str | None = None,
    client: str = "obsidian_rag",
    device: str = "Codex",
    device_id: str = "obsidian-rag-codex",
    version: str = "1.0.0",
) -> str:
    parts = [
        f'Client="{client}"',
        f'Device="{device}"',
        f'DeviceId="{device_id}"',
        f'Version="{version}"',
    ]
    if token:
        parts.append(f'Token="{token}"')
    return "MediaBrowser " + ", ".join(parts)


def authenticate_jellyfin(
    *,
    base_url: str,
    username: str,
    password: str,
    timeout: int = 15,
) -> tuple[str, str | None]:
    normalized_base = _normalize_base_url(base_url)
    response = requests.post(
        f"{normalized_base}/Users/AuthenticateByName",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Emby-Authorization": _auth_header_value(),
        },
        json={
            "Username": username,
            "Pw": password,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Unexpected Jellyfin authentication response")
    token = str(payload.get("AccessToken") or "").strip()
    user = payload.get("User") if isinstance(payload.get("User"), dict) else {}
    user_id = str(user.get("Id") or "").strip() or None
    if not token:
        raise ValueError("Jellyfin authentication succeeded but returned no access token")
    return token, user_id


def _maybe_int(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _maybe_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _runtime_ticks_to_minutes(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        ticks = int(value)
    except (TypeError, ValueError):
        return None
    if ticks <= 0:
        return None
    return round(ticks / 10_000_000 / 60)


def _director_names(people: Any) -> list[str]:
    if not isinstance(people, list):
        return []
    names: list[str] = []
    for person in people:
        if not isinstance(person, dict):
            continue
        if str(person.get("Type") or "").lower() != "director":
            continue
        name = str(person.get("Name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _coerce_jellyfin_movie(item: dict[str, Any], base_url: str) -> JellyfinMovie | None:
    item_id = str(item.get("Id") or "").strip()
    title = str(item.get("Name") or "").strip()
    if not item_id or not title:
        return None
    provider_ids = item.get("ProviderIds") if isinstance(item.get("ProviderIds"), dict) else {}
    path = str(item.get("Path") or "").strip()
    genres = item.get("Genres") if isinstance(item.get("Genres"), list) else []
    return JellyfinMovie(
        item_id=item_id,
        title=title,
        year=_maybe_int(item.get("ProductionYear")),
        path=path,
        imdb_id=_normalize_imdb_id(
            provider_ids.get("Imdb") or provider_ids.get("IMDb") or provider_ids.get("IMDB")
        ),
        tmdb_id=_normalize_tmdb_id(provider_ids.get("Tmdb") or provider_ids.get("TMDb") or provider_ids.get("TMDB")),
        directors=_director_names(item.get("People")),
        genres=[str(genre).strip() for genre in genres if str(genre).strip()],
        runtime_min=_runtime_ticks_to_minutes(item.get("RunTimeTicks")),
        content_rating=str(item.get("OfficialRating") or "").strip(),
        imdb_rating=_maybe_float(item.get("CommunityRating")),
        overview=str(item.get("Overview") or "").strip(),
    )


def fetch_jellyfin_movies(
    *,
    base_url: str,
    api_key: str | None = None,
    access_token: str | None = None,
    user_id: str | None = None,
    timeout: int = 60,
    page_size: int = 200,
) -> list[JellyfinMovie]:
    normalized_base = _normalize_base_url(base_url)
    endpoint = f"{normalized_base}/Users/{user_id}/Items" if user_id else f"{normalized_base}/Items"
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-Emby-Token"] = api_key
    elif access_token:
        headers["Authorization"] = f"MediaBrowser Token={access_token}"
    base_params = {
        "Recursive": "true",
        "IncludeItemTypes": "Movie",
        "Fields": "Path,ProviderIds,People,Genres,Overview,OfficialRating,CommunityRating,ProductionYear,RunTimeTicks",
        "SortBy": "SortName",
        "SortOrder": "Ascending",
        "Limit": str(page_size),
    }
    movies: list[JellyfinMovie] = []
    start_index = 0
    total_record_count: int | None = None

    while total_record_count is None or start_index < total_record_count:
        params = dict(base_params)
        params["StartIndex"] = str(start_index)
        response = requests.get(endpoint, headers=headers, params=params, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        raw_items = payload.get("Items") if isinstance(payload, dict) else payload
        if not isinstance(raw_items, list):
            raise ValueError("Unexpected Jellyfin response; expected an Items list")
        if isinstance(payload, dict):
            try:
                total_record_count = int(payload.get("TotalRecordCount"))
            except (TypeError, ValueError):
                total_record_count = None

        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            movie = _coerce_jellyfin_movie(raw_item, normalized_base)
            if movie is not None:
                movies.append(movie)

        if not raw_items:
            break
        start_index += len(raw_items)
        if total_record_count is None and len(raw_items) < page_size:
            break
    return movies


def _movie_url(base_url: str, item_id: str) -> str:
    return f"{_normalize_base_url(base_url)}/web/index.html#!/details?id={item_id}"


def _candidate_keys(frontmatter: dict[str, Any], note_path: Path) -> tuple[str, int | None, str, str]:
    title = str(frontmatter.get("title") or note_path.stem).strip() or note_path.stem
    year = _maybe_int(frontmatter.get("year"))
    imdb_id = _normalize_imdb_id(frontmatter.get("imdb_id"))
    tmdb_id = _normalize_tmdb_id(frontmatter.get("tmdb_id"))
    return title, year, imdb_id, tmdb_id


def _build_movie_indexes(movies: list[JellyfinMovie]) -> dict[str, dict[Any, list[JellyfinMovie]]]:
    by_item_id: dict[str, list[JellyfinMovie]] = defaultdict(list)
    by_imdb: dict[str, list[JellyfinMovie]] = defaultdict(list)
    by_tmdb: dict[str, list[JellyfinMovie]] = defaultdict(list)
    by_title_year: dict[tuple[str, int | None], list[JellyfinMovie]] = defaultdict(list)
    by_title: dict[str, list[JellyfinMovie]] = defaultdict(list)
    for movie in movies:
        by_item_id[movie.item_id].append(movie)
        if movie.imdb_id:
            by_imdb[movie.imdb_id].append(movie)
        if movie.tmdb_id:
            by_tmdb[movie.tmdb_id].append(movie)
        for alias_key in movie.alias_keys:
            by_title_year[(alias_key, movie.year)].append(movie)
            by_title[alias_key].append(movie)
    return {
        "item_id": by_item_id,
        "imdb": by_imdb,
        "tmdb": by_tmdb,
        "title_year": by_title_year,
        "title": by_title,
    }


def _choose_unique_movie(candidates: list[JellyfinMovie]) -> JellyfinMovie | None:
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        return None
    provider_keys = {
        (
            candidate.imdb_id,
            candidate.tmdb_id,
            candidate.year,
            tuple(sorted(candidate.alias_keys)),
        )
        for candidate in candidates
    }
    if len(provider_keys) == 1:
        return sorted(candidates, key=lambda item: (item.path.count("/"), item.path, item.item_id))[0]
    return None


def match_note_to_movie(
    note_path: Path,
    frontmatter: dict[str, Any],
    indexes: dict[str, dict[Any, list[JellyfinMovie]]],
) -> NoteMatch | None:
    title, year, imdb_id, tmdb_id = _candidate_keys(frontmatter, note_path)
    current_item_id = str(frontmatter.get("jellyfin_item_id") or "").strip()

    if current_item_id:
        selected = _choose_unique_movie(indexes["item_id"].get(current_item_id, []))
        if selected is not None:
            return NoteMatch(note_path=note_path, movie=selected, reason="jellyfin_item_id")

    if imdb_id:
        selected = _choose_unique_movie(indexes["imdb"].get(imdb_id, []))
        if selected is not None:
            return NoteMatch(note_path=note_path, movie=selected, reason="imdb_id")

    if tmdb_id:
        selected = _choose_unique_movie(indexes["tmdb"].get(tmdb_id, []))
        if selected is not None:
            return NoteMatch(note_path=note_path, movie=selected, reason="tmdb_id")

    alias_candidates = set()
    alias_candidates.update(_title_alias_keys(title))
    alias_candidates.update(_title_alias_keys(_stem_without_year(note_path.stem)))

    for alias_key in alias_candidates:
        selected = _choose_unique_movie(indexes["title_year"].get((alias_key, year), []))
        if selected is not None:
            return NoteMatch(note_path=note_path, movie=selected, reason="title+year")

    if year is None:
        for alias_key in alias_candidates:
            selected = _choose_unique_movie(indexes["title"].get(alias_key, []))
            if selected is not None:
                return NoteMatch(note_path=note_path, movie=selected, reason="title")
    return None


def _set_if_blank(frontmatter: dict[str, Any], key: str, value: Any) -> bool:
    if _is_blank(value) or not _is_blank(frontmatter.get(key)):
        return False
    frontmatter[key] = value
    return True


def update_note_frontmatter(
    frontmatter: dict[str, Any],
    movie: JellyfinMovie,
    *,
    base_url: str,
) -> tuple[dict[str, Any], list[str]]:
    updated = dict(frontmatter)
    changes: list[str] = []

    if _set_if_blank(updated, "imdb_id", movie.imdb_id or None):
        changes.append("imdb_id")
    if _set_if_blank(updated, "tmdb_id", movie.tmdb_id or None):
        changes.append("tmdb_id")
    if _set_if_blank(updated, "year", movie.year):
        changes.append("year")
    if "director" in updated or "directors" not in updated:
        if _set_if_blank(updated, "director", movie.directors[0] if movie.directors else None):
            changes.append("director")
    else:
        if _set_if_blank(updated, "directors", movie.directors):
            changes.append("directors")
    if "genre" in updated or "genres" not in updated:
        if _set_if_blank(updated, "genre", movie.genres):
            changes.append("genre")
    else:
        if _set_if_blank(updated, "genres", movie.genres):
            changes.append("genres")
    if _set_if_blank(updated, "runtime_min", movie.runtime_min):
        changes.append("runtime_min")
    if _set_if_blank(updated, "content_rating", movie.content_rating or None):
        changes.append("content_rating")
    if _set_if_blank(updated, "imdb_rating", movie.imdb_rating):
        changes.append("imdb_rating")
    if "description" in updated and _set_if_blank(updated, "description", movie.overview or None):
        changes.append("description")

    current_item_id = str(updated.get("jellyfin_item_id") or "").strip()
    if current_item_id != movie.item_id:
        updated["jellyfin_item_id"] = movie.item_id
        changes.append("jellyfin_item_id")

    current_path = str(updated.get("jellyfin_path") or "").strip()
    if movie.path and current_path != movie.path:
        updated["jellyfin_path"] = movie.path
        changes.append("jellyfin_path")

    movie_url = _movie_url(base_url, movie.item_id)
    current_url = str(updated.get("jellyfin_url") or "").strip()
    if current_url != movie_url:
        updated["jellyfin_url"] = movie_url
        changes.append("jellyfin_url")

    return updated, changes


def sync_jellyfin_notes(
    *,
    vault_root: str | Path,
    base_url: str,
    api_key: str | None = None,
    username: str | None = None,
    password: str | None = None,
    user_id: str | None = None,
    dry_run: bool = False,
    timeout: int = 60,
    page_size: int = 200,
) -> dict[str, Any]:
    access_token = None
    effective_user_id = user_id
    if not api_key and username:
        access_token, authenticated_user_id = authenticate_jellyfin(
            base_url=base_url,
            username=username,
            password=password or "",
            timeout=timeout,
        )
        if not effective_user_id:
            effective_user_id = authenticated_user_id

    movies = fetch_jellyfin_movies(
        base_url=base_url,
        api_key=api_key,
        access_token=access_token,
        user_id=effective_user_id,
        timeout=timeout,
        page_size=page_size,
    )
    indexes = _build_movie_indexes(movies)
    movie_dir = Path(vault_root) / "Media" / "Movies"
    matched = 0
    updated_count = 0
    skipped = 0
    unmatched: list[str] = []
    updated_notes: list[dict[str, Any]] = []

    for note_path in sorted(movie_dir.glob("*.md")):
        text = note_path.read_text(encoding="utf-8")
        frontmatter, body = _split_frontmatter(text)
        if str(frontmatter.get("kind") or "").strip().lower() != "movie":
            skipped += 1
            continue
        if "NAS" not in _normalize_provenance(frontmatter.get("provenance")):
            skipped += 1
            continue

        match = match_note_to_movie(note_path, frontmatter, indexes)
        if match is None:
            unmatched.append(str(note_path))
            continue

        matched += 1
        updated_frontmatter, changes = update_note_frontmatter(frontmatter, match.movie, base_url=base_url)
        if not changes:
            continue
        updated_count += 1
        updated_notes.append(
            {
                "path": str(note_path),
                "reason": match.reason,
                "changes": changes,
            }
        )
        if not dry_run:
            note_path.write_text(_render_note(updated_frontmatter, body), encoding="utf-8")

    return {
        "movies_fetched": len(movies),
        "matched_notes": matched,
        "updated_notes": updated_count,
        "skipped_notes": skipped,
        "unmatched_notes": unmatched,
        "updated_note_details": updated_notes,
        "dry_run": dry_run,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backfill movie note metadata from Jellyfin")
    parser.add_argument("--vault-root", required=True, help="Vault root to update")
    parser.add_argument("--url", help="Jellyfin base URL, e.g. http://host:8096 (or set JELLYFIN_URL in .env)")
    parser.add_argument("--api-key", help="Jellyfin API key")
    parser.add_argument("--username", help="Jellyfin username")
    parser.add_argument("--password", help="Jellyfin password; omit to prompt securely")
    parser.add_argument("--user-id", help="Optional Jellyfin user id")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds for Jellyfin requests")
    parser.add_argument("--page-size", type=int, default=200, help="Jellyfin items fetched per request page")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing notes")
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = _build_parser()
    args = parser.parse_args(argv)

    url = args.url or os.environ.get("JELLYFIN_URL")
    if not url:
        parser.error("--url is required (or set JELLYFIN_URL in .env)")
    api_key = args.api_key or os.environ.get("JELLYFIN_API_KEY")
    username = args.username or os.environ.get("JELLYFIN_USERNAME")
    password = args.password or os.environ.get("JELLYFIN_PASSWORD")
    if username and password is None:
        password = getpass.getpass("Jellyfin password: ")
    summary = sync_jellyfin_notes(
        vault_root=args.vault_root,
        base_url=url,
        api_key=api_key,
        username=username,
        password=password,
        user_id=args.user_id,
        dry_run=args.dry_run,
        timeout=args.timeout,
        page_size=args.page_size,
    )
    print(yaml.safe_dump(summary, sort_keys=False, allow_unicode=False).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
