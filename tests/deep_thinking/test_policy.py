import unittest
from unittest.mock import MagicMock
from deep_thinking.policy import PolicyAgent

class TestPolicyAgent(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.policy = PolicyAgent(self.mock_client)

    def test_decide_continue(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"decision": "CONTINUE", "reasoning": "more to do"}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "q",
            "past_steps": [],
            "plan": [{}, {}],
            "current_step_index": 1,
            "iteration_count": 1,
            "max_iterations": 5
        }
        
        decision = self.policy.decide(state)
        self.assertEqual(decision, "CONTINUE")

    def test_decide_finish(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"decision": "FINISH", "reasoning": "done"}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "q",
            "past_steps": [],
            "plan": [{}],
            "current_step_index": 1,
            "iteration_count": 1,
            "max_iterations": 5
        }
        
        decision = self.policy.decide(state)
        self.assertEqual(decision, "FINISH")

    def test_decide_invalid(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"decision": "UNKNOWN"}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "q",
            "past_steps": [],
            "plan": [],
            "current_step_index": 0,
            "iteration_count": 0,
            "max_iterations": 5
        }
        
        decision = self.policy.decide(state)
        self.assertEqual(decision, "CONTINUE")

    def test_decide_empty_content_returns_continue(self):
        mock_response = MagicMock()
        mock_response.content = []
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "q",
            "past_steps": [],
            "plan": [],
            "current_step_index": 0,
            "iteration_count": 0,
            "max_iterations": 5
        }

        decision = self.policy.decide(state)
        self.assertEqual(decision, "CONTINUE")

    def test_decide_summary_query_does_not_force_external_enrichment(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"decision": "FINISH", "reasoning": "done", "needs_external_enrichment": true}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "Provide a point form summary of The Wisdom of Psychopaths",
            "past_steps": [{
                "step": {"step_number": 1, "sub_question": "Search local note", "search_strategy": "vector", "keywords": [], "target_folders": [], "reasoning": ""},
                "confidence": 0.8,
                "key_findings": "Found the book note.",
            }],
            "plan": [{"step_number": 1, "search_strategy": "vector"}],
            "current_step_index": 1,
            "iteration_count": 1,
            "max_iterations": 5,
        }

        decision = self.policy.decide(state)
        self.assertEqual(decision, "FINISH")

    def test_decide_broad_summary_query_continues_when_steps_remain(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"decision": "FINISH", "reasoning": "done", "needs_external_enrichment": false}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "Provide a point form summary of The Wisdom of Psychopaths",
            "summary_intent": "broad",
            "past_steps": [{
                "step": {"step_number": 1, "sub_question": "Search local note", "search_strategy": "vector", "keywords": [], "target_folders": [], "reasoning": ""},
                "confidence": 0.8,
                "key_findings": "Found the book note.",
            }],
            "plan": [
                {"step_number": 1, "search_strategy": "vector"},
                {"step_number": 2, "search_strategy": "hybrid"},
            ],
            "current_step_index": 1,
            "iteration_count": 1,
            "max_iterations": 5,
        }

        decision = self.policy.decide(state)
        self.assertEqual(decision, "CONTINUE")

if __name__ == '__main__':
    unittest.main()
