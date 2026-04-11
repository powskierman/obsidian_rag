from pathlib import Path

import pytest

from src.movies.cli import run_sync


@pytest.mark.integration
def test_movie_sync_creates_store_notes_and_reports(tmp_path: Path):
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    data_root = tmp_path / "movie-data"

    apple_csv = tmp_path / "apple_movies.csv"
    apple_csv.write_text(
        "\n".join(
            [
                "Title,Year,IMDb ID,Quality",
                "Blade Runner,1982,tt0083658,HD",
                "Suspiria,2018,,4K",
            ]
        ),
        encoding="utf-8",
    )

    nas_txt = tmp_path / "nas_titles.txt"
    nas_txt.write_text(
        "\n".join(
            [
                "Blade Runner (1982) [4K]",
                "Suspiria (1977)",
                "Suspiria",
            ]
        ),
        encoding="utf-8",
    )

    summary = run_sync(
        apple_csv=apple_csv,
        nas_txt=nas_txt,
        vault_root=vault_root,
        db_path=data_root / "canonical_movies.db",
        report_dir=data_root / "reports",
        provider_name="none",
    )

    assert summary["movies"] == 3
    assert summary["review_items"] == 1
    assert summary["note_count"] == 3

    blade_runner = vault_root / "Media" / "Movies" / "Blade Runner (1982).md"
    suspiria_1977 = vault_root / "Media" / "Movies" / "Suspiria (1977).md"
    suspiria_2018 = vault_root / "Media" / "Movies" / "Suspiria (2018).md"
    unresolved_report = data_root / "reports" / "unresolved_matches.md"

    assert blade_runner.exists()
    assert suspiria_1977.exists()
    assert suspiria_2018.exists()
    assert unresolved_report.exists()

    first_render = blade_runner.read_text(encoding="utf-8")
    rerun_summary = run_sync(
        apple_csv=apple_csv,
        nas_txt=nas_txt,
        vault_root=vault_root,
        db_path=data_root / "canonical_movies.db",
        report_dir=data_root / "reports",
        provider_name="none",
    )
    second_render = blade_runner.read_text(encoding="utf-8")

    assert rerun_summary["movies"] == summary["movies"]
    assert second_render == first_render
