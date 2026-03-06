import unittest
from unittest.mock import MagicMock, patch
from deep_thinking.orchestrator import DeepThinkingRAG

class TestDeepThinkingRAG(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.orchestrator = DeepThinkingRAG(self.mock_client, "http://vector", "http://graph")
        
        # Mock internal components
        self.orchestrator.planner = MagicMock()
        self.orchestrator.supervisor = MagicMock()
        self.orchestrator.reflector = MagicMock()
        self.orchestrator.policy = MagicMock()
        self.orchestrator.synthesizer = MagicMock()

    def test_query_flow(self):
        # Setup mocks
        self.orchestrator.planner.create_plan.return_value = [{
            "step_number": 1, 
            "sub_question": "q1",
            "search_strategy": "vector",
            "keywords": [],
            "target_folders": [],
            "reasoning": ""
        }]
        self.orchestrator.supervisor.execute_step.return_value = [{
            "content": "doc1",
            "source": "Tech/ESP32.md",
            "filepath": "Tech/ESP32.md",
            "filename": "ESP32.md",
            "snippet": "doc1",
            "type": "vector",
            "score": 0.9,
            "source_category": "vault",
        }]
        self.orchestrator.reflector.reflect.return_value = {"key_findings": "f1", "confidence": 0.9}
        self.orchestrator.policy.decide.return_value = "FINISH"
        self.orchestrator.synthesizer.generate.return_value = ("Final Answer", ["citation1"])

        result = self.orchestrator.query("test question")
        
        self.assertEqual(result["answer"], "Final Answer")
        self.assertEqual(len(result["research_steps"]), 1)
        self.assertEqual(result["total_documents"], 1)
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["source_category"], "vault")
        self.assertEqual(result["sources"][0]["filepath"], "Tech/ESP32.md")
        
        # Verify calls
        self.orchestrator.planner.create_plan.assert_called_once()
        self.orchestrator.supervisor.execute_step.assert_called_once()
        self.orchestrator.reflector.reflect.assert_called_once()
        self.orchestrator.policy.decide.assert_called_once()
        self.orchestrator.synthesizer.generate.assert_called_once()

    def test_query_flow_accepts_wrapped_plan_object(self):
        self.orchestrator.planner.create_plan.return_value = {
            "steps": [{
                "step_number": 1,
                "sub_question": "q1",
                "search_strategy": "vector",
                "keywords": [],
                "target_folders": [],
                "reasoning": ""
            }]
        }
        self.orchestrator.supervisor.execute_step.return_value = [{
            "content": "doc1",
            "source": "Tech/ESP32.md",
            "filepath": "Tech/ESP32.md",
            "filename": "ESP32.md",
            "snippet": "doc1",
            "type": "vector",
            "score": 0.9,
            "source_category": "vault",
        }]
        self.orchestrator.reflector.reflect.return_value = {"key_findings": "f1", "confidence": 0.9}
        self.orchestrator.policy.decide.return_value = "FINISH"
        self.orchestrator.synthesizer.generate.return_value = ("Final Answer", ["citation1"])

        result = self.orchestrator.query("test question")

        self.assertEqual(result["answer"], "Final Answer")
        self.assertEqual(len(result["research_steps"]), 1)
        self.assertEqual(len(result["sources"]), 1)

    def test_query_max_iterations(self):
        # Setup mocks to loop
        self.orchestrator.planner.create_plan.return_value = [{
            "step_number": 1, 
            "sub_question": "q1",
            "search_strategy": "vector",
            "keywords": [],
            "target_folders": [],
            "reasoning": ""
        }]
        self.orchestrator.supervisor.execute_step.return_value = []
        self.orchestrator.reflector.reflect.return_value = {"key_findings": "f", "confidence": 0.5}
        self.orchestrator.policy.decide.return_value = "REVISE_PLAN"
        self.orchestrator.planner.extend_plan.return_value = [{
            "step_number": 2, 
            "sub_question": "q2",
            "search_strategy": "vector",
            "keywords": [],
            "target_folders": [],
            "reasoning": ""
        }]
        self.orchestrator.synthesizer.generate.return_value = ("Ans", [])

        # Limit iterations
        result = self.orchestrator.query("test", max_iterations=2)
        
        # Should stop after 2 iterations
        self.assertEqual(len(result["research_steps"]), 2)
        self.assertEqual(result["sources"], [])

    @patch('deep_thinking.orchestrator.DeepThinkingRAG._provider_limits')
    def test_hierarchical_memory_compression(self, mock_limits):
        # Set a very low accumulated_context_chars limit to trigger compression easily
        mock_limits.return_value = (3, 6000, 24000, 100) # limit is 100, 70% is 70
        
        self.orchestrator.planner.create_plan.return_value = [{
            "step_number": 1, 
            "sub_question": "q1",
            "search_strategy": "vector",
            "keywords": [],
            "target_folders": [],
            "reasoning": ""
        }]
        self.orchestrator.supervisor.execute_step.return_value = []
        # Make the key findings long enough to exceed 70 chars
        self.orchestrator.reflector.reflect.return_value = {"key_findings": "A" * 80, "confidence": 0.9}
        self.orchestrator.reflector.compress_context.return_value = "[COMPRESSED] Summary of A"
        self.orchestrator.policy.decide.return_value = "FINISH"
        self.orchestrator.synthesizer.generate.return_value = ("Final Answer", [])

        result = self.orchestrator.query("test question")
        
        self.orchestrator.reflector.compress_context.assert_called_once()
        # The accumulated context should contain the compressed prefix
        self.orchestrator.synthesizer.generate.assert_called_once()

if __name__ == '__main__':
    unittest.main()
