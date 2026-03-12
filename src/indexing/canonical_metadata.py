"""
Canonical metadata helpers shared by indexing and graph build pipelines.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any


_DATE_PATTERN = re.compile(r"(20\d{2}-\d{2}-\d{2})")
_NON_ALNUM_PATTERN = re.compile(r"[^a-z0-9]+")
_SPLIT_PATTERN = re.compile(r"[,;|]")

_DATE_KEYS = (
    "timeline_date",
    "scan_date",
    "treatment_date",
    "event_date",
    "date",
)

_SLASH_DATE_PATTERN = re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b")
_MONTH_NAME_DATE_PATTERN = re.compile(
    r"\b("
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
    r"\s+\d{1,2}(?:,\s*|\s+)\d{4}"
    r")\b",
    re.IGNORECASE,
)
_LABELED_TEXT_DATE_PATTERNS = (
    re.compile(
        r"\b(?:exam/service|exam|service|study|procedure)\s*date\b\s*[:\-]?\s*"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*|\s+)\d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:^|\n)\s*date\s*[:\-]?\s*"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*|\s+)\d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\breport signed\b\s*[:\-]?\s*"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*|\s+)\d{4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bdictated(?:\s+using[^\n]*)?[\s:.-]*"
        r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*|\s+)\d{4})",
        re.IGNORECASE,
    ),
)


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item not in seen:
            output.append(item)
            seen.add(item)
    return output


def _to_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                output.append(text)
        return output
    text = str(value).strip()
    if not text:
        return []
    # Parse simple list-like strings: "a, b, c"
    if any(sep in text for sep in [",", ";", "|"]):
        return [part.strip() for part in _SPLIT_PATTERN.split(text) if part.strip()]
    return [text]


def slugify_text(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = _NON_ALNUM_PATTERN.sub("-", text)
    return text.strip("-")


def normalize_tags(value: Any) -> list[str]:
    normalized: list[str] = []
    for tag in _to_text_list(value):
        cleaned = str(tag).strip()
        if not cleaned:
            continue
        if cleaned.startswith("#"):
            cleaned = cleaned[1:]
        slug = slugify_text(cleaned)
        if slug:
            normalized.append(f"#{slug}")
    return _dedupe_keep_order(normalized)


def normalize_aliases(value: Any) -> list[str]:
    normalized: list[str] = []
    for alias in _to_text_list(value):
        slug = slugify_text(alias)
        if slug:
            normalized.append(slug)
    return _dedupe_keep_order(normalized)


def _extract_date(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    for pattern, formats in (
        (_DATE_PATTERN, ("%Y-%m-%d",)),
        (_SLASH_DATE_PATTERN, ("%m/%d/%Y", "%m/%d/%y")),
        (_MONTH_NAME_DATE_PATTERN, ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y")),
    ):
        match = pattern.search(text)
        if not match:
            continue
        raw = match.group(1)
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt).date().isoformat()
            except ValueError:
                continue
    return ""


def _timeline_date_from_metadata(metadata: dict[str, Any]) -> str:
    for key in _DATE_KEYS:
        if key not in metadata:
            continue
        candidate = _extract_date(metadata.get(key))
        if candidate:
            return candidate
    return ""


def _timeline_date_from_text(text: str) -> str:
    haystack = str(text or "").strip()
    if not haystack:
        return ""

    for pattern in _LABELED_TEXT_DATE_PATTERNS:
        match = pattern.search(haystack)
        if not match:
            continue
        candidate = _extract_date(match.group("date"))
        if candidate:
            return candidate

    return ""


def _timeline_date_from_path(file_path: Path) -> str:
    path_text = file_path.as_posix()
    match = _DATE_PATTERN.search(path_text)
    if match:
        return match.group(1)
    return ""


def infer_entity_type(file_path: Path, tags: list[str], metadata: dict[str, Any]) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return "pdf_document"

    tag_set = {tag.lstrip("#") for tag in tags}
    title = str(metadata.get("title", "")).lower()
    path = file_path.as_posix().lower()
    combined = " ".join([title, path, " ".join(sorted(tag_set))])

    if {"drug", "medication", "therapy", "treatment", "car-t"} & tag_set:
        return "treatment"
    if {"scan", "imaging", "pet", "ct", "mri"} & tag_set:
        return "imaging"
    if "lymphoma" in combined or "oncology" in combined:
        return "medical_note"
    return "note"


def infer_treatment_phase(file_path: Path, tags: list[str], text: str) -> str:
    path = file_path.as_posix().lower()
    tag_text = " ".join(tags).lower()
    body = str(text or "").lower()
    hay = f"{path} {tag_text} {body[:3000]}"

    if any(token in hay for token in ("r-chop", "epoch", "da-epoch", "chemotherapy", "fludarabine", "cyclophosphamide")):
        return "chemotherapy"
    if any(token in hay for token in ("car-t", "yescarta", "axi-cel", "infusion", "lymphodepleting")):
        return "car_t"
    if any(token in hay for token in ("pet", "ct scan", "mri", "follow-up", "follow up", "scan")):
        return "monitoring"
    if any(token in hay for token in ("progression", "relapse", "refractory")):
        return "progression_assessment"
    return "unspecified"


def build_canonical_metadata(
    *,
    file_path: Path,
    metadata: dict[str, Any] | None = None,
    text: str = "",
    tags: Any = None,
    aliases: Any = None,
) -> dict[str, Any]:
    source = metadata or {}
    normalized_tags = normalize_tags(tags if tags is not None else source.get("tags"))
    normalized_aliases = normalize_aliases(
        aliases if aliases is not None else source.get("aliases")
    )

    canonical_candidates = [
        source.get("canonical_id"),
        source.get("canonical"),
        source.get("title"),
        normalized_aliases[0] if normalized_aliases else "",
        file_path.stem,
    ]
    canonical_id = ""
    for candidate in canonical_candidates:
        slug = slugify_text(str(candidate or ""))
        if slug:
            canonical_id = slug
            break
    if not canonical_id:
        canonical_id = slugify_text(file_path.name)

    timeline_date = _timeline_date_from_metadata(source)
    if not timeline_date:
        timeline_date = _timeline_date_from_text(text)
    if not timeline_date:
        timeline_date = _timeline_date_from_path(file_path)

    return {
        "canonical_id": canonical_id,
        "aliases_normalized": normalized_aliases,
        "tags_normalized": normalized_tags,
        "entity_type": infer_entity_type(file_path=file_path, tags=normalized_tags, metadata=source),
        "timeline_date": timeline_date,
        "treatment_phase": infer_treatment_phase(file_path=file_path, tags=normalized_tags, text=text),
    }
