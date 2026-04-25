"""Unit tests for LightRAG prompt override verification."""

import ast
import importlib.util
from pathlib import Path
import types

import pytest


def _load_override_module():
    module_path = Path("src/lightrag_overrides/lightrag/prompt_overrides.py")
    spec = importlib.util.spec_from_file_location("test_prompt_overrides", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def prompt_override_helper():
    source_path = Path("src/integrations/lightrag_service.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))

    needed_assigns = {
        "_PROMPT_OVERRIDE_STATUS_MARKERS",
    }
    needed_functions = {
        "_build_prompt_override_fingerprint",
    }

    selected_nodes = []
    for node in module_ast.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in needed_assigns:
                    selected_nodes.append(node)
                    break
        elif isinstance(node, ast.FunctionDef) and node.name in needed_functions:
            selected_nodes.append(node)

    test_module = ast.Module(body=selected_nodes, type_ignores=[])
    ast.fix_missing_locations(test_module)
    namespace = {
        "LIGHTRAG_REQUIRE_PROMPT_OVERRIDES": True,
        "PROMPTS": {},
        "importlib": __import__("importlib"),
    }
    exec(compile(test_module, str(source_path), "exec"), namespace)
    return types.SimpleNamespace(
        fingerprint=namespace["_build_prompt_override_fingerprint"],
        namespace=namespace,
    )


@pytest.mark.unit
def test_prompt_override_fingerprint_reports_active_when_real_override_applied(
    prompt_override_helper, monkeypatch
):
    override_module = _load_override_module()
    prompts = {
        "entity_extraction_system_prompt": "stock system prompt",
        "entity_continue_extraction_user_prompt": "stock continue prompt",
    }
    override_module.apply_overrides(prompts)
    prompt_override_helper.namespace["PROMPTS"] = prompts

    monkeypatch.setattr(
        prompt_override_helper.namespace["importlib"],
        "import_module",
        lambda name: override_module,
    )

    fingerprint = prompt_override_helper.fingerprint()

    assert fingerprint["module_available"] is True
    assert fingerprint["override_active"] is True
    assert fingerprint["system_prompt_matches_override"] is True
    assert fingerprint["continue_prompt_matches_override"] is True
    assert fingerprint["system_prompt_marker_present"] is True
    assert fingerprint["continue_prompt_marker_present"] is True


@pytest.mark.unit
def test_prompt_override_fingerprint_reports_inactive_when_stock_prompt_present(
    prompt_override_helper, monkeypatch
):
    override_module = _load_override_module()
    prompt_override_helper.namespace["PROMPTS"] = {
        "entity_extraction_system_prompt": "stock system prompt",
        "entity_continue_extraction_user_prompt": "stock continue prompt",
    }

    monkeypatch.setattr(
        prompt_override_helper.namespace["importlib"],
        "import_module",
        lambda name: override_module,
    )

    fingerprint = prompt_override_helper.fingerprint()

    assert fingerprint["module_available"] is True
    assert fingerprint["override_active"] is False
    assert fingerprint["system_prompt_matches_override"] is False
    assert fingerprint["continue_prompt_matches_override"] is False
