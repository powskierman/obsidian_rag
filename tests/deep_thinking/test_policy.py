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

if __name__ == '__main__':
    unittest.main()
