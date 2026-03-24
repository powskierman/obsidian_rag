import pytest

from src.utils.prompt_builder import (
    build_prompt_appendix,
    build_vault_system_prompt,
    is_medical_imaging_query,
    prefers_full_vault_answer,
)


@pytest.mark.unit
def test_is_medical_imaging_query_matches_pet_ct():
    assert is_medical_imaging_query("Review my PET and CT scans")


@pytest.mark.unit
def test_build_prompt_appendix_adds_chatgpt_guardrails():
    appendix = build_prompt_appendix("CT scan findings", "chatgpt")
    assert "Do not ask for permissions" in appendix


@pytest.mark.unit
def test_build_vault_system_prompt_includes_context():
    prompt = build_vault_system_prompt(
        context_text="Source 1: test content",
        user_query="CT scan details",
        provider="chatgpt",
        custom_prompt=None,
    )
    assert "Context from notes" in prompt


@pytest.mark.unit
def test_prefers_full_vault_answer_for_review_queries():
    assert prefers_full_vault_answer("Review my PET and CT scans and provide your assessment")
    assert prefers_full_vault_answer("Analyze the tradeoffs in my Docker setup")
    assert not prefers_full_vault_answer("What is Yescarta")
