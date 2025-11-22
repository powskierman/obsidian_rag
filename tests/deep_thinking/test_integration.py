import unittest
from unittest.mock import MagicMock, patch
from deep_thinking.orchestrator import DeepThinkingRAG

class TestDeepThinkingIntegration(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.orchestrator = DeepThinkingRAG(self.mock_client, "http://vector", "http://graph")

    def test_complex_query_flow(self):
        """
        Simulates a 2-step research process:
        1. Plan: 2 steps
        2. Step 1: Vector search -> Found docs -> Reflection
        3. Step 2: Graph search -> Found docs -> Reflection
        4. Policy: Finish
        5. Synthesis: Final answer
        """
        # --- MOCK RESPONSES ---
        
        # 1. Planner: Create Plan
        plan_response = [
            {
                "step_number": 1,
                "sub_question": "What is the mechanism of action for CAR-T?",
                "search_strategy": "vector",
                "keywords": ["CAR-T", "mechanism"],
                "target_folders": ["Medical/"],
                "reasoning": "Understand the basics."
            },
            {
                "step_number": 2,
                "sub_question": "What are the side effects recorded in my notes?",
                "search_strategy": "vector",
                "keywords": ["side effects", "symptoms"],
                "target_folders": ["Medical/"],
                "reasoning": "Check personal records."
            }
        ]
        
        # 2. Supervisor: Execute Step 1 (Vector)
        step1_docs = [{"content": "CAR-T uses T-cells...", "source": "Medical/Notes/CAR-T.md", "type": "vector"}]
        
        # 3. Reflector: Reflect Step 1
        step1_reflection = {
            "key_findings": "CAR-T modifies T-cells to attack cancer.",
            "confidence": 0.9,
            "has_gaps": False
        }
        
        # 4. Supervisor: Execute Step 2 (Vector)
        step2_docs = [{"content": "Experienced fatigue and fever...", "source": "Medical/Daily/2023-05.md", "type": "vector"}]
        
        # 5. Reflector: Reflect Step 2
        step2_reflection = {
            "key_findings": "Patient reported fatigue and fever.",
            "confidence": 0.8,
            "has_gaps": False
        }
        
        # 6. Policy: Decide (after step 2)
        policy_decision = {"decision": "FINISH", "reasoning": "Have enough info."}
        
        # 7. Synthesizer: Generate
        final_answer = {
            "answer": "CAR-T works by modifying T-cells. You experienced fatigue.",
            "citations": ["[[Medical/Notes/CAR-T.md]]", "[[Medical/Daily/2023-05.md]]"]
        }

        # --- CONFIGURE MOCKS ---
        
        # Planner
        self.mock_client.messages.create.side_effect = [
            MagicMock(content=[MagicMock(text=str(plan_response).replace("'", '"'))]), # Plan
            MagicMock(content=[MagicMock(text=str(step1_reflection).replace("'", '"').replace("False", "false"))]), # Reflect 1
            MagicMock(content=[MagicMock(text=str(step2_reflection).replace("'", '"').replace("False", "false"))]), # Reflect 2
            MagicMock(content=[MagicMock(text=str(policy_decision).replace("'", '"'))]), # Policy
            MagicMock(content=[MagicMock(text=str(final_answer).replace("'", '"'))]) # Synthesis
        ]
        
        # Supervisor (We need to mock the internal methods or the requests calls)
        # Since we are testing integration of the orchestrator, mocking the supervisor's execute_step is easier
        # but mocking requests gives us more coverage of supervisor.
        # Let's mock requests.post to return different things based on the query or order.
        
        with patch('requests.post') as mock_post:
            mock_post.side_effect = [
                MagicMock(status_code=200, json=lambda: {"results": [{"text": "CAR-T uses T-cells...", "metadata": {"file_path": "Medical/Notes/CAR-T.md"}, "score": 0.9}]}), # Step 1
                MagicMock(status_code=200, json=lambda: {"results": [{"text": "Experienced fatigue...", "metadata": {"file_path": "Medical/Daily/2023-05.md"}, "score": 0.8}]})  # Step 2
            ]
            
            # Run Query
            result = self.orchestrator.query("How does CAR-T work and what were my side effects?")
            
            # Assertions
            self.assertEqual(result["answer"], "CAR-T works by modifying T-cells. You experienced fatigue.")
            self.assertEqual(len(result["research_steps"]), 2)
            self.assertEqual(len(result["citations"]), 2)
            self.assertEqual(result["research_steps"][0]["key_findings"], "CAR-T modifies T-cells to attack cancer.")

if __name__ == '__main__':
    unittest.main()
