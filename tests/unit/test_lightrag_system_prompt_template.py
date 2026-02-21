"""Unit tests for LightRAG user system-prompt placeholder handling."""

import ast
from pathlib import Path
import types

import pytest


@pytest.fixture
def prompt_template_helpers():
    source_path = Path("src/integrations/lightrag_service.py")
    source = source_path.read_text(encoding="utf-8")
    module_ast = ast.parse(source, filename=str(source_path))

    needed_assigns = {
        "SYSTEM_PROMPT_PLACEHOLDER_PATTERN",
        "SYSTEM_PROMPT_PLACEHOLDER_ALIASES",
        "SYSTEM_PROMPT_ALLOWED_PLACEHOLDERS",
    }
    needed_functions = {
        "_escape_braces_for_format",
        "_normalize_system_prompt_template",
        "_extract_prompt_placeholders",
        "_validate_system_prompt_template",
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
    namespace = {"re": __import__("re")}
    exec(compile(test_module, str(source_path), "exec"), namespace)
    return types.SimpleNamespace(
        normalize=namespace["_normalize_system_prompt_template"],
        validate=namespace["_validate_system_prompt_template"],
        extract=namespace["_extract_prompt_placeholders"],
    )


@pytest.mark.unit
def test_normalize_maps_legacy_aliases_and_injects_memory(prompt_template_helpers):
    normalized = prompt_template_helpers.normalize(
        "Context: {context}\nVault: {vault_context}\nQ: {question}\nM: {memory_context}",
        "Personal detail",
    )
    assert "{context_data}" in normalized
    assert "{query}" in normalized
    assert "Personal detail" in normalized
    assert "{memory_context}" not in normalized


@pytest.mark.unit
def test_normalize_escapes_braces_in_memory_context(prompt_template_helpers):
    normalized = prompt_template_helpers.normalize("Memory: {memory_context}", "has {braces}")
    assert "{{braces}}" in normalized


@pytest.mark.unit
def test_validate_rejects_unknown_placeholders(prompt_template_helpers):
    invalid = prompt_template_helpers.validate("A {context_data} B {totally_unknown}")
    assert invalid == ["totally_unknown"]


@pytest.mark.unit
def test_validate_accepts_supported_placeholders(prompt_template_helpers):
    invalid = prompt_template_helpers.validate(
        "A {context_data} B {content_data} C {query} D {response_type} E {user_prompt}"
    )
    assert invalid == []

