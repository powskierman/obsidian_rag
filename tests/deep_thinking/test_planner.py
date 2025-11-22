import unittest
from unittest.mock import MagicMock
from deep_thinking.planner import PlannerAgent

class TestPlannerAgent(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.planner = PlannerAgent(self.mock_client)

    def test_create_plan_success(self):
        # Mock response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='[{"step_number": 1, "sub_question": "test", "search_strategy": "vector", "keywords": ["test"], "target_folders": [], "reasoning": "test"}]')]
        self.mock_client.messages.create.return_value = mock_response

        plan = self.planner.create_plan("test question", {})
        
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["sub_question"], "test")
        self.assertEqual(plan[0]["search_strategy"], "vector")

    def test_create_plan_parsing_error(self):
        # Mock invalid JSON response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='invalid json')]
        self.mock_client.messages.create.return_value = mock_response

        plan = self.planner.create_plan("test question", {})
        
        # Should return fallback plan
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["search_strategy"], "hybrid")
        self.assertEqual(plan[0]["reasoning"], "Fallback plan due to parsing error")

    def test_extend_plan_success(self):
        # Mock response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='[{"sub_question": "new step", "search_strategy": "graph", "keywords": [], "target_folders": [], "reasoning": "gap"}]')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "orig",
            "plan": [{"step_number": 1}],
            "past_steps": [{"step": {"step_number": 1, "sub_question": "q"}, "key_findings": "f"}]
        }
        
        new_steps = self.planner.extend_plan(state)
        
        self.assertEqual(len(new_steps), 1)
        self.assertEqual(new_steps[0]["step_number"], 2)
        self.assertEqual(new_steps[0]["sub_question"], "new step")

if __name__ == '__main__':
    unittest.main()
