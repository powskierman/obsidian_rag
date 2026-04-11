from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Protocol

try:
    import requests
except ImportError:  # pragma: no cover - optional runtime dependency in this shell
    requests = None

from .normalize import normalize_imdb_id
from .schema import default_cache_dir
from src.indexing.canonical_metadata import slugify_text


@dataclass
class EnrichmentResult:
    imdb_id: str = ""
    tmdb_id: str = ""
    collection: str = ""
    directors: list[str] | None = None
    cast: list[str] | None = None
    genres: list[str] | None = None
    runtime_minutes: int | None = None
    imdb_rating: float | None = None
    top_250: bool | None = None


class MetadataProvider(Protocol):
    def lookup(self, title: str, year: int | None = None) -> EnrichmentResult | None:
        ...


class NullMovieMetadataProvider:
    def lookup(self, title: str, year: int | None = None) -> EnrichmentResult | None:
        return None


class OmdbMovieMetadataProvider:
    def __init__(self, api_key: str, cache_dir: Path | None = None):
        self.api_key = api_key
        self.cache_dir = cache_dir or (default_cache_dir() / "omdb")

    def _cache_path(self, title: str, year: int | None) -> Path:
        parts = [slugify_text(title)]
        if year:
            parts.append(str(year))
        filename = "-".join(part for part in parts if part) or "lookup"
        return self.cache_dir / f"{filename}.json"

    def lookup(self, title: str, year: int | None = None) -> EnrichmentResult | None:
        if requests is None:
            raise RuntimeError("requests is required for OMDb lookups")
        cache_path = self._cache_path(title, year)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict | None = None
        if cache_path.exists():
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
            except Exception:
                payload = None

        if payload is None:
            params = {"apikey": self.api_key, "t": title}
            if year:
                params["y"] = year
            response = requests.get("https://www.omdbapi.com/", params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
            cache_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

        if not payload or str(payload.get("Response", "")).lower() != "true":
            return None

        runtime_minutes = None
        runtime_text = str(payload.get("Runtime", "")).strip().lower()
        if runtime_text.endswith(" min"):
            try:
                runtime_minutes = int(runtime_text.replace(" min", "").strip())
            except ValueError:
                runtime_minutes = None

        imdb_rating = None
        rating_text = str(payload.get("imdbRating", "")).strip()
        if rating_text and rating_text != "N/A":
            try:
                imdb_rating = float(rating_text)
            except ValueError:
                imdb_rating = None

        return EnrichmentResult(
            imdb_id=normalize_imdb_id(payload.get("imdbID")),
            directors=[value.strip() for value in str(payload.get("Director", "")).split(",") if value.strip()],
            cast=[value.strip() for value in str(payload.get("Actors", "")).split(",") if value.strip()],
            genres=[value.strip() for value in str(payload.get("Genre", "")).split(",") if value.strip()],
            runtime_minutes=runtime_minutes,
            imdb_rating=imdb_rating,
        )


def build_metadata_provider(
    provider_name: str,
    *,
    omdb_api_key: str | None = None,
    cache_dir: Path | None = None,
) -> MetadataProvider:
    provider = str(provider_name or "none").strip().lower()
    if provider == "omdb":
        key = omdb_api_key or os.getenv("OMDB_API_KEY")
        if key:
            return OmdbMovieMetadataProvider(key, cache_dir=cache_dir)
    return NullMovieMetadataProvider()
