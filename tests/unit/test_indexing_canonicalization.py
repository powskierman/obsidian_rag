"""
Unit tests for canonical metadata extraction used by indexing pipelines.
"""

from pathlib import Path

import pytest

from src.indexing.canonical_metadata import build_canonical_metadata, normalize_tags


@pytest.mark.unit
def test_build_canonical_metadata_prefers_explicit_canonical_id():
    meta = build_canonical_metadata(
        file_path=Path("Medical/Lymphoma/Yescarta.md"),
        metadata={
            "canonical_id": "Yescarta Therapy",
            "aliases": ["Axi-Cel", "Yescarta"],
            "tags": ["Drug", "CAR-T"],
        },
        text="CAR-T infusion details",
    )
    assert meta["canonical_id"] == "yescarta-therapy"
    assert "axi-cel" in meta["aliases_normalized"]
    assert "#drug" in meta["tags_normalized"]


@pytest.mark.unit
def test_build_canonical_metadata_extracts_timeline_date_from_path():
    meta = build_canonical_metadata(
        file_path=Path("Medical/Lymphoma/Lymphoma Progress report 2025-12-31.md"),
        metadata={},
        text="Progress review after treatment",
    )
    assert meta["timeline_date"] == "2025-12-31"


@pytest.mark.unit
def test_build_canonical_metadata_extracts_exam_date_from_medical_text():
    meta = build_canonical_metadata(
        file_path=Path("Medical/Lymphoma/media/CT Scan 04-25.pdf"),
        metadata={},
        text="CT CHEST ABDOMEN PELVIS ENHANCED\nDATE: 4/18/2025 11:40 AM\nReport Signed: 4/18/2025 2:40 PM",
    )
    assert meta["timeline_date"] == "2025-04-18"


@pytest.mark.unit
def test_build_canonical_metadata_extracts_dictated_date_when_no_exam_date_present():
    meta = build_canonical_metadata(
        file_path=Path("Medical/Lymphoma/media/CT Scan 01-26.pdf"),
        metadata={},
        text="CT MASS BIOPSY\nProcedure performed by: Dr. Bashir\nDictated using Voice Recognition Technology.\n12/5/2024 2:34 PM",
    )
    assert meta["timeline_date"] == "2024-12-05"


@pytest.mark.unit
def test_build_canonical_metadata_infers_treatment_phase_and_entity_type():
    meta = build_canonical_metadata(
        file_path=Path("Medical/Lymphoma/Yescarta Treatment Plan.md"),
        metadata={"tags": ["#lymphoma", "therapy"]},
        text="Lymphodepleting chemotherapy followed by one-time CAR-T infusion.",
    )
    assert meta["entity_type"] in {"treatment", "medical_note"}
    assert meta["treatment_phase"] == "chemotherapy"


@pytest.mark.unit
def test_normalize_tags_handles_mixed_formats():
    assert normalize_tags(["CAR-T", "#Lymphoma", ""]) == ["#car-t", "#lymphoma"]
