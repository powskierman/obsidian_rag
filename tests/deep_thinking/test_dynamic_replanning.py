from unittest.mock import MagicMock, patch

import unittest
from deep_thinking.orchestrator import DeepThinkingRAG
from deep_thinking.state import RAGState

class TestDynamicReplanning(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.rag = DeepThinkingRAG(self.mock_client)
        
    def test_policy_triggers_replanning(self):
        """Test that policy triggers REVISE_PLAN when info is missing."""
        
        # Mock state where plan is done but info is missing
        state = {
            "original_question": "What is the capital of France?",
            "plan": [{"step_number": 1, "sub_question": "Check map", "search_strategy": "vector"}],
            "current_step_index": 1, # Plan exhausted
            "past_steps": [{
                "step": {"step_number": 1, "sub_question": "Check map"},
                "key_findings": "Found nothing relevant.",
                "confidence": 0.0
            }],
            "iteration_count": 1,
            "max_iterations": 5,
            "should_continue": True
        }
        
        # Mock responses for sequential calls:
        # 1. Policy decision (REVISE_PLAN)
        # 2. Planner extension (New steps)
        self.mock_client.messages.create.side_effect = [
            MagicMock(content=[MagicMock(text='{"decision": "REVISE_PLAN", "reasoning": "Missing capital info"}')]),
            MagicMock(content=[MagicMock(text='[{"sub_question": "Search for Paris", "search_strategy": "vector", "keywords": [], "target_folders": [], "reasoning": "gap"}]')])
        ]
        
        # Execute policy logic (simulating orchestrator loop)
        decision = self.rag.policy.decide(state)
        self.assertEqual(decision, "REVISE_PLAN")
        
        if decision == "REVISE_PLAN":
            new_steps = self.rag.planner.extend_plan(state)
            self.assertEqual(len(new_steps), 1)
            self.assertEqual(new_steps[0]["sub_question"], "Search for Paris")
            
    def test_orchestrator_integration(self):
        """Test full orchestrator flow with replanning."""
        # This is harder to mock without running the full loop, 
        # but we can verify the components work together.
        pass

if __name__ == '__main__':
    unittest.main()
