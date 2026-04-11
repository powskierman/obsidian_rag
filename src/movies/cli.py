from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from .enrich import build_metadata_provider
from .ingest_apple import parse_apple_export
from .ingest_nas import parse_nas_title_list
from .match import reconcile_records
from .project_obsidian import write_movie_notes
from .report import write_summary_report, write_unresolved_report
from .schema import (
    default_cache_dir,
    default_database_path,
    default_report_dir,
    persist_snapshot,
)


def run_sync(
    *,
    apple_csv: str | Path | None = None,
    nas_txt: str | Path | None = None,
    vault_root: str | Path | None = None,
    db_path: str | Path | None = None,
    report_dir: str | Path | None = None,
    provider_name: str = "none",
    omdb_api_key: str | None = None,
    skip_projection: bool = False,
) -> dict[str, Any]:
    records = []
    if apple_csv:
        records.extend(parse_apple_export(apple_csv))
    if nas_txt:
        records.extend(parse_nas_title_list(nas_txt))
    if not records:
        raise ValueError("At least one movie input is required.")

    provider = build_metadata_provider(
        provider_name,
        omdb_api_key=omdb_api_key,
        cache_dir=default_cache_dir(),
    )
    movies, review_items = reconcile_records(records, provider=provider)

    database_path = Path(db_path) if db_path else default_database_path()
    persist_snapshot(database_path, movies, records, review_items)

    report_root = Path(report_dir) if report_dir else default_report_dir()
    unresolved_report = write_unresolved_report(
        review_items,
        report_root / "unresolved_matches.md",
    )
    summary_report = write_summary_report(
        movies,
        review_items,
        report_root / "movie_sync_summary.md",
    )

    written_paths = []
    if not skip_projection:
        if not vault_root:
            raise ValueError("vault_root is required unless --skip-projection is used.")
        written_paths = write_movie_notes(movies, vault_root=vault_root)

    return {
        "db_path": str(database_path),
        "movies": len(movies),
        "review_items": len(review_items),
        "note_count": len(written_paths),
        "unresolved_report": str(unresolved_report),
        "summary_report": str(summary_report),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync canonical movies into Obsidian notes")
    parser.add_argument("--apple-csv", help="Path to Apple movie export CSV")
    parser.add_argument("--nas-txt", help="Path to NAS movie title list")
    parser.add_argument("--vault-root", help="Vault root. Defaults to OBSIDIAN_VAULT_PATH when provided.")
    parser.add_argument("--db-path", help="Override SQLite database path")
    parser.add_argument("--report-dir", help="Override report output directory")
    parser.add_argument("--provider", default="none", choices=["none", "omdb"], help="Metadata provider")
    parser.add_argument("--omdb-api-key", help="Explicit OMDb API key override")
    parser.add_argument("--skip-projection", action="store_true", help="Skip note generation")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    summary = run_sync(
        apple_csv=args.apple_csv,
        nas_txt=args.nas_txt,
        vault_root=args.vault_root or os.getenv("OBSIDIAN_VAULT_PATH") or Path.cwd(),
        db_path=args.db_path,
        report_dir=args.report_dir,
        provider_name=args.provider,
        omdb_api_key=args.omdb_api_key,
        skip_projection=args.skip_projection,
    )
    print("Movie sync completed:")
    for key, value in summary.items():
        print(f"- {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
