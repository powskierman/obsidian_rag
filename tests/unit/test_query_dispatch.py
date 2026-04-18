"""Contract tests for the legacy-mode alias map and canonical normalizer.

These tests are the contract we promise to older REST/MCP clients during the
deprecation window. If any of them fail, a caller breaks.
"""

from __future__ import annotations

import pytest

from src.services.query_dispatch import (
    LEGACY_MODE_MAP,
    REST_ACCEPTED_MODES,
    UnsupportedMode,
    normalize_legacy_request,
)


# ---------------------------------------------------------------------------
# Alias map — one parametrized sweep per legacy name
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "legacy,expected_mode,expected_depth,expected_sources",
    [
        ("vector",       "ask",      "shallow", ("vault",)),       # depth defaulted for ask
        ("mempalace",    "ask",      "shallow", ("mempalace",)),
        ("cascading",    "research", "auto",    ("vault",)),
        ("vault_review", "research", "full",    ("vault",)),
        ("VECTOR",       "ask",      "shallow", ("vault",)),       # case-insensitive
        (" cascading ",  "research", "auto",    ("vault",)),       # whitespace-tolerant
    ],
)
def test_legacy_names_project_to_canonical(
    legacy, expected_mode, expected_depth, expected_sources
):
    mode, depth, sources, deprecation = normalize_legacy_request(legacy)
    assert mode == expected_mode
    assert depth == expected_depth
    assert sources == expected_sources
    assert deprecation == legacy.strip().lower()  # emitted so we can log migration


def test_canonical_mode_names_skip_deprecation_header():
    mode, depth, sources, deprecation = normalize_legacy_request("research")
    assert mode == "research"
    assert deprecation is None  # signals "no deprecation needed"


def test_unknown_mode_raises():
    with pytest.raises(UnsupportedMode) as ei:
        normalize_legacy_request("quantum-search")
    msg = str(ei.value)
    # Error lists both canonical and legacy names during the deprecation window.
    assert "ask, research" in msg
    assert "vector, cascading" in msg


def test_explicit_depth_overrides_legacy_default():
    # Client says `cascading` but also passes depth=shallow — explicit wins.
    mode, depth, _, _ = normalize_legacy_request("cascading", explicit_depth="shallow")
    assert mode == "research"
    assert depth == "shallow"


def test_explicit_sources_override_legacy_default():
    mode, _, sources, _ = normalize_legacy_request(
        "vector", explicit_sources=("vault", "mempalace")
    )
    assert mode == "ask"
    assert sources == ("vault", "mempalace")


def test_web_search_toggle_folds_into_sources():
    # Old clients set web_search=true as a separate boolean; new contract
    # treats it as a source.
    _, _, sources, _ = normalize_legacy_request("cascading", web_search_toggle=True)
    assert "web" in sources
    assert "vault" in sources


def test_web_search_toggle_is_idempotent_when_already_selected():
    _, _, sources, _ = normalize_legacy_request(
        "cascading", explicit_sources=("vault", "web"), web_search_toggle=True
    )
    # No duplicate "web" in sources tuple.
    assert sources.count("web") == 1


def test_investigate_accepted_by_normalizer_rejected_at_rest_layer():
    # Normalizer accepts it — mode is valid, just served on WS.
    mode, _, _, _ = normalize_legacy_request("investigate")
    assert mode == "investigate"
    # But the REST layer filters via REST_ACCEPTED_MODES.
    assert "investigate" not in REST_ACCEPTED_MODES


@pytest.mark.parametrize(
    "deprecated",
    ["graph", "networkx", "lightrag", "notes", "entities",
     "notes+vector", "entities+vector", "dual-graph", "hybrid"],
)
def test_historical_deprecated_modes_still_raise(deprecated):
    # These mode names existed in very old clients but were never valid
    # production modes. The original handler 400'd on them (by projecting
    # to unsupported aliases); the normalizer must keep doing so rather
    # than silently routing them to `cascading`.
    with pytest.raises(UnsupportedMode):
        normalize_legacy_request(deprecated)


def test_legacy_map_covers_every_production_mode_from_api_gateway():
    # Guard against silent mode additions: the LEGACY_MODE_MAP must include
    # every mode api_gateway.py declares in supported_modes.
    must_cover = {"vector", "cascading", "vault_review", "mempalace"}
    assert must_cover.issubset(LEGACY_MODE_MAP.keys())


# ---------------------------------------------------------------------------
# Validation tests for #1 (sources), #2 (depth), and null-safety
# ---------------------------------------------------------------------------

def test_none_mode_normalizes_to_empty_string():
    # null-safety contract: None mode is coerced to "" and then raises.
    with pytest.raises(UnsupportedMode):
        normalize_legacy_request(None)


def test_empty_string_mode_raises():
    # Empty string after strip should raise, not fall through to legacy map.
    with pytest.raises(UnsupportedMode) as ei:
        normalize_legacy_request("")
    assert "Unsupported mode" in str(ei.value)


@pytest.mark.parametrize(
    "invalid_depth",
    ["evil", "deep", "comprehensive", "thorough", "max", "invalid"],
)
def test_invalid_explicit_depth_raises(invalid_depth):
    # Any explicit_depth not in {auto,shallow,staged,full} should raise.
    with pytest.raises(UnsupportedMode) as ei:
        normalize_legacy_request("research", explicit_depth=invalid_depth)
    msg = str(ei.value)
    assert "Invalid depth" in msg
    assert invalid_depth in msg


@pytest.mark.parametrize(
    "invalid_source",
    ["web-only", "graph", "api", "unknown", "database"],
)
def test_invalid_explicit_sources_raises(invalid_source):
    # Any source not in {vault,mempalace,web} should raise.
    with pytest.raises(UnsupportedMode) as ei:
        normalize_legacy_request("research", explicit_sources=(invalid_source,))
    msg = str(ei.value)
    assert "Invalid source" in msg
    assert invalid_source in msg


def test_web_only_ask_raises():
    # Ask mode with only web sources is unsupported — should raise.
    # (Previously fell through silently to "vector" / vault results.)
    with pytest.raises(UnsupportedMode):
        normalize_legacy_request("ask", explicit_sources=("web",))


@pytest.mark.parametrize(
    "valid_depth",
    ["auto", "shallow", "staged", "full"],
)
def test_valid_explicit_depth_accepted(valid_depth):
    # Valid depths should be accepted without error.
    mode, depth, _, _ = normalize_legacy_request("research", explicit_depth=valid_depth)
    assert depth == valid_depth


@pytest.mark.parametrize(
    "valid_sources",
    [("vault",), ("mempalace",), ("web",), ("vault", "web"), ("vault", "mempalace", "web")],
)
def test_valid_explicit_sources_accepted(valid_sources):
    # Valid source combinations should be accepted.
    _, _, sources, _ = normalize_legacy_request("research", explicit_sources=valid_sources)
    assert sources == valid_sources
