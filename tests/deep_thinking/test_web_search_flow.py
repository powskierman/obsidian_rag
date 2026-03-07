import pytest
import os
from unittest.mock import MagicMock, patch
from deep_thinking.policy import PolicyAgent
from deep_thinking.planner import PlannerAgent
from deep_thinking.supervisor import RetrievalSupervisor
from deep_thinking.state import RAGState

@pytest.fixture
def mock_anthropic():
    return MagicMock()

@pytest.fixture
def policy_agent(mock_anthropic):
    return PolicyAgent(mock_anthropic)

@pytest.fixture
def planner_agent(mock_anthropic):
    return PlannerAgent(mock_anthropic)

@pytest.fixture
def retrieval_supervisor():
    # Mock services URLs
    return RetrievalSupervisor("http://mock-vector", "http://mock-graph", enable_reranking=False)

def test_policy_forces_revise_plan_for_medical_context(policy_agent, mock_anthropic):
    """
    Test that PolicyAgent forces REVISE_PLAN when medical context is found 
    but no web search has been performed or planned, even if LLM says FINISH.
    """
    # Setup state with medical context but no web search
    state: RAGState = {
        "original_question": "What is the treatment for DLBCL?",
        "user_context": {},
        "plan": [
            {"step_number": 1, "sub_question": "Search local notes", "search_strategy": "vector", "keywords": ["DLBCL"], "target_folders": [], "reasoning": ""}
        ],
        "current_step_index": 1, # Plan completed
        "past_steps": [
            {
                "step": {"step_number": 1, "sub_question": "Search local notes", "search_strategy": "vector", "keywords": ["DLBCL"], "target_folders": [], "reasoning": ""},
                "documents_found": 5,
                "key_findings": "Found notes mentioning Diffuse Large B-Cell Lymphoma (DLBCL) and R-CHOP treatment.",
                "confidence": 0.8
            }
        ],
        "accumulated_context": "",
        "retrieved_documents": [],
        "iteration_count": 1,
        "max_iterations": 5,
        "should_continue": True,
        "final_answer": "",
        "citations": []
    }

    # Mock LLM to say "FINISH" but with needs_external_enrichment=True
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"decision": "FINISH", "reasoning": "Found relevant notes.", "needs_external_enrichment": true}')]
    mock_anthropic.messages.create.return_value = mock_message

    decision = policy_agent.decide(state)

    # Should be overridden to REVISE_PLAN because needs_external_enrichment is True
    assert decision == "REVISE_PLAN"

def test_policy_forces_revise_plan_for_technical_context(policy_agent, mock_anthropic):
    """
    Test that PolicyAgent forces REVISE_PLAN for technical queries (e.g. ESP32)
    when enrichment is needed.
    """
    state: RAGState = {
        "original_question": "What are the specs of ESP32?",
        "user_context": {},
        "plan": [
            {"step_number": 1, "sub_question": "Search local notes", "search_strategy": "vector", "keywords": ["ESP32"], "target_folders": [], "reasoning": ""}
        ],
        "current_step_index": 1,
        "past_steps": [
            {
                "step": {"step_number": 1, "sub_question": "Search local notes", "search_strategy": "vector", "keywords": ["ESP32"], "target_folders": [], "reasoning": ""},
                "documents_found": 2,
                "key_findings": "Found project notes using ESP32.",
                "confidence": 0.8
            }
        ],
        "accumulated_context": "",
        "retrieved_documents": [],
        "iteration_count": 1,
        "max_iterations": 5,
        "should_continue": True,
        "final_answer": "",
        "citations": []
    }

    # Mock LLM to say "FINISH" but with needs_external_enrichment=True
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"decision": "FINISH", "reasoning": "Found project notes.", "needs_external_enrichment": true}')]
    mock_anthropic.messages.create.return_value = mock_message

    decision = policy_agent.decide(state)

    assert decision == "REVISE_PLAN"

def test_planner_extends_plan_with_web_search(planner_agent, mock_anthropic):
    """
    Test that PlannerAgent adds a web search step when requested.
    """
    state: RAGState = {
        "original_question": "What is the treatment for DLBCL?",
        "past_steps": [
             {
                "step": {"step_number": 1, "sub_question": "Search local notes", "search_strategy": "vector", "keywords": ["DLBCL"], "target_folders": [], "reasoning": ""},
                "documents_found": 5,
                "key_findings": "Found notes mentioning DLBCL and R-CHOP.",
                "confidence": 0.8
            }
        ],
        "plan": [{"step_number": 1}], # Dummy existing plan
        "current_step_index": 1,
        "user_context": {},
        "accumulated_context": "",
        "retrieved_documents": [],
        "iteration_count": 1,
        "max_iterations": 5,
        "should_continue": True,
        "final_answer": "",
        "citations": []
    }

    # Mock LLM response for extend_plan
    new_steps_json = """
    [
        {
            "sub_question": "What are the side effects of R-CHOP?",
            "search_strategy": "web",
            "keywords": ["R-CHOP side effects", "DLBCL standard treatment"],
            "target_folders": [],
            "reasoning": "Need external context on treatment side effects."
        }
    ]
    """
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=new_steps_json)]
    mock_anthropic.messages.create.return_value = mock_message

    new_steps = planner_agent.extend_plan(state)

    assert len(new_steps) == 1
    assert new_steps[0]["search_strategy"] == "web"
    assert new_steps[0]["step_number"] == 2 # Should continue numbering

def test_retrieval_supervisor_executes_web_search(retrieval_supervisor):
    """
    Test that RetrievalSupervisor calls TavilyClient when strategy is 'web'.
    """
    step = {
        "step_number": 2,
        "sub_question": "What are the side effects of R-CHOP?",
        "search_strategy": "web",
        "keywords": ["R-CHOP"],
        "target_folders": [],
        "reasoning": "External search"
    }

    # Mock TavilyClient
    with patch('deep_thinking.supervisor.WEB_SEARCH_AVAILABLE', True):
        with patch('deep_thinking.supervisor.TavilyClient', create=True) as MockTavily:
            mock_tavily_instance = MockTavily.return_value
            
            # Mock search results
            mock_tavily_instance.search.return_value = {
                "results": [
                    {"title": "R-CHOP Side Effects", "content": "Common side effects include...", "url": "http://cancer.org/r-chop", "score": 0.9}
                ]
            }

            # Mock environment variable
            with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
                results = retrieval_supervisor.execute_step(step, {})

        assert len(results) == 1
        assert results[0]["type"] == "web"
        assert results[0]["source"] == "http://cancer.org/r-chop"
        assert "Side Effects" in results[0]["content"]

def test_retrieval_supervisor_canonicalizes_and_dedupes_tracking_urls(retrieval_supervisor):
    step = {
        "step_number": 2,
        "sub_question": "What are the side effects of R-CHOP?",
        "search_strategy": "web",
        "keywords": ["R-CHOP"],
        "target_folders": [],
        "reasoning": "External search"
    }

    with patch('deep_thinking.supervisor.WEB_SEARCH_AVAILABLE', True):
        with patch('deep_thinking.supervisor.TavilyClient', create=True) as MockTavily:
            mock_tavily_instance = MockTavily.return_value
            mock_tavily_instance.search.return_value = {
                "results": [
                    {
                        "title": "R-CHOP Side Effects",
                        "content": "Common side effects include...",
                        "url": "https://www.cancer.org/r-chop?utm_source=newsletter&srsltid=abc",
                        "score": 0.9
                    },
                    {
                        "title": "R-CHOP Side Effects Copy",
                        "content": "Duplicate canonical page",
                        "url": "https://cancer.org/r-chop?utm_medium=email",
                        "score": 0.8
                    }
                ]
            }

            with patch.dict(os.environ, {"TAVILY_API_KEY": "test-key"}):
                results = retrieval_supervisor.execute_step(step, {})

        assert len(results) == 1
        assert results[0]["source"] == "https://cancer.org/r-chop"
        assert results[0]["filepath"] == "https://cancer.org/r-chop"
