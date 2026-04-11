from src.movies.match import reconcile_records
from src.movies.normalize import movie_note_filename, parse_movie_title
from src.movies.schema import SourceMovieRecord


def _record(
    source_record_id: str,
    source_type: str,
    raw_title: str,
    year: int | None,
    *,
    title: str,
    normalized_title: str,
    version_label: str = "",
    version_key: str = "standard",
) -> SourceMovieRecord:
    return SourceMovieRecord(
        source_record_id=source_record_id,
        source_type=source_type,
        source_path=f"/tmp/{source_type.lower()}",
        raw_title=raw_title,
        title=title,
        normalized_title=normalized_title,
        year=year,
        version_label=version_label,
        version_key=version_key,
    )


def test_parse_movie_title_extracts_year_and_version():
    parsed = parse_movie_title("Blade.Runner.Final Cut (1982) [4K]")
    assert parsed.title == "Blade Runner"
    assert parsed.year_hint == 1982
    assert parsed.version_label == "Final Cut"
    assert parsed.version_key == "final-cut"


def test_movie_note_filename_is_stable():
    assert movie_note_filename("Blade Runner", 1982) == "Blade Runner (1982).md"
    assert (
        movie_note_filename("Blade Runner", 1982, "Final Cut")
        == "Blade Runner (1982) - Final Cut.md"
    )


def test_reconcile_records_merges_duplicate_ownership_variants():
    records = [
        _record("apple:1", "Apple", "Blade Runner (1982)", 1982, title="Blade Runner", normalized_title="blade-runner"),
        _record("nas:1", "NAS", "Blade Runner (1982)", 1982, title="Blade Runner", normalized_title="blade-runner"),
    ]
    movies, review_items = reconcile_records(records)
    assert len(movies) == 1
    assert not review_items
    assert set(movies[0].provenance) == {"Apple", "NAS"}


def test_reconcile_records_separates_remakes_and_alternate_cuts():
    records = [
        _record("a1", "Apple", "Suspiria (1977)", 1977, title="Suspiria", normalized_title="suspiria"),
        _record("a2", "Apple", "Suspiria (2018)", 2018, title="Suspiria", normalized_title="suspiria"),
        _record(
            "a3",
            "Apple",
            "Blade Runner Final Cut (1982)",
            1982,
            title="Blade Runner",
            normalized_title="blade-runner",
            version_label="Final Cut",
            version_key="final-cut",
        ),
        _record("a4", "Apple", "Blade Runner (1982)", 1982, title="Blade Runner", normalized_title="blade-runner"),
    ]
    movies, review_items = reconcile_records(records)
    assert len(movies) == 4
    assert not review_items


def test_reconcile_records_flags_yearless_ambiguous_title():
    records = [
        _record("a1", "Apple", "Suspiria (1977)", 1977, title="Suspiria", normalized_title="suspiria"),
        _record("a2", "Apple", "Suspiria (2018)", 2018, title="Suspiria", normalized_title="suspiria"),
        _record("n1", "NAS", "Suspiria", None, title="Suspiria", normalized_title="suspiria"),
    ]
    movies, review_items = reconcile_records(records)
    assert len(movies) == 2
    assert len(review_items) == 1
    assert review_items[0].reason == "ambiguous_year"
