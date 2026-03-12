import ast
from pathlib import Path
import types

import pytest


@pytest.fixture
def synthesis_config_helpers():
    source_path = Path("src/services/cascading_pipeline.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))

    needed_functions = {
        "_get_env_value",
        "_get_env_int",
        "_get_env_float",
        "_provider_synthesis_timeout_seconds",
        "_provider_synthesis_max_tokens",
        "_query_intent",
        "canonical_cascading_provider_name",
        "is_summary_style_query",
        "is_comparison_style_query",
        "is_relation_style_query",
    }

    selected_nodes = []
    for node in module_ast.body:
        if isinstance(node, ast.FunctionDef) and node.name in needed_functions:
            selected_nodes.append(node)

    test_module = ast.Module(body=selected_nodes, type_ignores=[])
    ast.fix_missing_locations(test_module)
    def _normalize_query_structure_impl(query: str):
        lowered = str(query or "").lower()
        if any(marker in lowered for marker in ("difference between", "compare ", " vs ", " versus ")):
            return {"intent": "comparison"}
        if any(marker in lowered for marker in ("relationship", "relate", "related to")):
            return {"intent": "relation"}
        return {"intent": "lookup"}

    namespace = {
        "os": __import__("os"),
        "re": __import__("re"),
        "Optional": __import__("typing").Optional,
        "_normalize_query_structure_impl": _normalize_query_structure_impl,
        "_is_relation_style_query_impl": lambda query: "related to" in str(query or "").lower(),
    }
    exec(compile(test_module, str(source_path), "exec"), namespace)
    return types.SimpleNamespace(
        timeout=namespace["_provider_synthesis_timeout_seconds"],
        max_tokens=namespace["_provider_synthesis_max_tokens"],
    )


@pytest.mark.unit
def test_openrouter_synthesis_timeout_defaults_above_global_floor(monkeypatch, synthesis_config_helpers):
    monkeypatch.delenv("CASCADING_SYNTHESIS_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("CASCADING_SYNTHESIS_TIMEOUT_SECONDS_REMOTE", raising=False)
    monkeypatch.delenv("CASCADING_SYNTHESIS_TIMEOUT_SECONDS_OPENROUTER", raising=False)

    assert synthesis_config_helpers.timeout("openrouter") == 60.0


@pytest.mark.unit
def test_openrouter_compact_queries_use_smaller_token_budget(monkeypatch, synthesis_config_helpers):
    monkeypatch.delenv("CASCADING_SYNTHESIS_MAX_TOKENS", raising=False)
    monkeypatch.delenv("CASCADING_SYNTHESIS_MAX_TOKENS_REMOTE", raising=False)
    monkeypatch.delenv("CASCADING_SYNTHESIS_MAX_TOKENS_REMOTE_COMPACT", raising=False)
    monkeypatch.delenv("CASCADING_SYNTHESIS_MAX_TOKENS_OPENROUTER", raising=False)

    assert (
        synthesis_config_helpers.max_tokens(
            "openrouter",
            "what is the difference between ollama and mlx",
            False,
        )
        == 320
    )


@pytest.mark.unit
def test_openrouter_full_queries_respect_remote_cap(monkeypatch, synthesis_config_helpers):
    monkeypatch.delenv("CASCADING_SYNTHESIS_MAX_TOKENS", raising=False)
    monkeypatch.delenv("CASCADING_SYNTHESIS_MAX_TOKENS_REMOTE", raising=False)
    monkeypatch.delenv("CASCADING_SYNTHESIS_MAX_TOKENS_OPENROUTER", raising=False)

    assert (
        synthesis_config_helpers.max_tokens(
            "openrouter",
            "explain the detailed migration history of my vault indexing pipeline",
            False,
        )
        == 384
    )
