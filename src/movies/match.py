from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .enrich import EnrichmentResult, MetadataProvider, NullMovieMetadataProvider
from .normalize import build_local_canonical_id
from .schema import CanonicalMovie, ReviewItem, SourceMovieRecord
from src.indexing.canonical_metadata import slugify_text


def _best_quality(records: list[SourceMovieRecord], source_type: str) -> str:
    values = [record.quality for record in records if record.source_type == source_type and record.quality]
    return values[0] if values else ""


def _duplicate_group(records: list[SourceMovieRecord]) -> str:
    return slugify_text(records[0].title) if records else ""


def _provenance(records: list[SourceMovieRecord]) -> list[str]:
    return sorted({record.source_type for record in records})


def _merged_top_250(records: list[SourceMovieRecord], enrichment: EnrichmentResult | None) -> bool:
    if enrichment and enrichment.top_250 is not None:
        return bool(enrichment.top_250)
    return any(record.top_250 for record in records if record.top_250 is not None)


def _preferred_title(records: list[SourceMovieRecord]) -> str:
    return sorted(records, key=lambda record: (len(record.title), record.title.lower(), record.source_record_id))[0].title


def _resolve_enrichment(
    provider: MetadataProvider,
    title: str,
    year: int | None,
) -> EnrichmentResult | None:
    try:
        return provider.lookup(title, year)
    except Exception:
        return None


def _canonical_movie_from_records(
    records: list[SourceMovieRecord],
    *,
    provider: MetadataProvider,
    match_status: str,
) -> CanonicalMovie:
    sorted_records = sorted(records, key=lambda record: record.source_record_id)
    title = _preferred_title(sorted_records)
    year = next((record.year for record in sorted_records if record.year), None)
    imdb_id = next((record.imdb_id for record in sorted_records if record.imdb_id), "")
    tmdb_id = next((record.tmdb_id for record in sorted_records if record.tmdb_id), "")
    collection = next((record.collection for record in sorted_records if record.collection), "")
    version_notes = next((record.version_label for record in sorted_records if record.version_label), "")
    version_key = next((record.version_key for record in sorted_records if record.version_key), "standard")

    enrichment = _resolve_enrichment(provider, title, year) if not imdb_id else None
    if enrichment:
        imdb_id = imdb_id or enrichment.imdb_id
        tmdb_id = tmdb_id or enrichment.tmdb_id
        collection = collection or enrichment.collection

    canonical_id = f"movie:{imdb_id}" if imdb_id else build_local_canonical_id(title, year, version_key)
    review_required = match_status != "resolved"

    return CanonicalMovie(
        canonical_id=canonical_id,
        title=title,
        year=year,
        imdb_id=imdb_id,
        tmdb_id=tmdb_id,
        provenance=_provenance(sorted_records),
        match_status=match_status,
        duplicate_group=_duplicate_group(sorted_records),
        version_notes=version_notes,
        collection=collection,
        quality_apple=_best_quality(sorted_records, "Apple"),
        quality_nas=_best_quality(sorted_records, "NAS"),
        top_250=_merged_top_250(sorted_records, enrichment),
        directors=list(enrichment.directors or []) if enrichment else [],
        cast=list(enrichment.cast or []) if enrichment else [],
        genres=list(enrichment.genres or []) if enrichment else [],
        runtime_minutes=enrichment.runtime_minutes if enrichment else None,
        imdb_rating=enrichment.imdb_rating if enrichment else None,
        review_required=review_required,
        source_record_ids=[record.source_record_id for record in sorted_records],
        source_titles=[record.raw_title for record in sorted_records],
    )


def reconcile_records(
    records: Iterable[SourceMovieRecord],
    provider: MetadataProvider | None = None,
) -> tuple[list[CanonicalMovie], list[ReviewItem]]:
    provider = provider or NullMovieMetadataProvider()
    movie_records = list(records)
    canonical_movies: list[CanonicalMovie] = []
    review_items: list[ReviewItem] = []

    imdb_groups: dict[str, list[SourceMovieRecord]] = defaultdict(list)
    for record in movie_records:
        if record.imdb_id:
            imdb_groups[record.imdb_id].append(record)

    exact_resolved_keys: dict[tuple[str, int, str], str] = {}
    fuzzy_resolved_keys: dict[tuple[str, str], set[str]] = defaultdict(set)
    for imdb_id, group in imdb_groups.items():
        for record in group:
            if record.year:
                exact_resolved_keys[(record.normalized_title, int(record.year), record.version_key)] = imdb_id
            fuzzy_resolved_keys[(record.normalized_title, record.version_key)].add(imdb_id)

    unresolved: list[SourceMovieRecord] = []
    for record in movie_records:
        if record.imdb_id:
            continue
        if record.year:
            imdb_id = exact_resolved_keys.get((record.normalized_title, int(record.year), record.version_key))
            if imdb_id:
                imdb_groups[imdb_id].append(record)
                continue
        candidate_ids = fuzzy_resolved_keys.get((record.normalized_title, record.version_key), set())
        if not record.year and len(candidate_ids) == 1:
            imdb_groups[next(iter(candidate_ids))].append(record)
            continue
        unresolved.append(record)

    for imdb_id, group in sorted(imdb_groups.items()):
        canonical_movies.append(
            _canonical_movie_from_records(group, provider=provider, match_status="resolved")
        )

    title_groups: dict[tuple[str, str], list[SourceMovieRecord]] = defaultdict(list)
    for record in unresolved:
        title_groups[(record.normalized_title, record.version_key)].append(record)

    for (normalized_title, version_key), group in sorted(title_groups.items()):
        by_year: dict[int, list[SourceMovieRecord]] = defaultdict(list)
        yearless: list[SourceMovieRecord] = []
        for record in group:
            if record.year:
                by_year[int(record.year)].append(record)
            else:
                yearless.append(record)

        if len(by_year) == 0:
            canonical_movies.append(
                _canonical_movie_from_records(group, provider=provider, match_status="needs_review")
            )
            continue

        if len(by_year) == 1:
            only_year = next(iter(by_year))
            merged_group = list(by_year[only_year]) + yearless
            canonical_movies.append(
                _canonical_movie_from_records(merged_group, provider=provider, match_status="resolved")
            )
            continue

        for year, year_group in sorted(by_year.items()):
            canonical_movies.append(
                _canonical_movie_from_records(year_group, provider=provider, match_status="resolved")
            )

        if yearless:
            review_items.append(
                ReviewItem(
                    review_key=f"{normalized_title}:{version_key}:ambiguous-year",
                    normalized_title=normalized_title,
                    candidate_years=sorted(by_year.keys()),
                    source_record_ids=[record.source_record_id for record in yearless],
                    raw_titles=[record.raw_title for record in yearless],
                    reason="ambiguous_year",
                    suggested_action="Add year or explicit imdb_id before automatic merge.",
                )
            )

    canonical_movies.sort(
        key=lambda movie: (movie.title.lower(), movie.year or 0, movie.version_notes.lower(), movie.canonical_id)
    )
    review_items.sort(key=lambda item: item.review_key)
    return canonical_movies, review_items
