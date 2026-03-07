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
        self.assertEqual(
            self.mock_client.messages.create.call_args.kwargs["response_format"],
            {"type": "json_object"},
        )

    def test_create_plan_accepts_wrapped_steps_object(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"steps":[{"step_number": 1, "sub_question": "test", "search_strategy": "vector", "keywords": ["test"], "target_folders": [], "reasoning": "test"}]}')]
        self.mock_client.messages.create.return_value = mock_response

        plan = self.planner.create_plan("test question", {})

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["sub_question"], "test")
        self.assertEqual(plan[0]["search_strategy"], "vector")

    def test_create_plan_trivially_normalizes_single_step_object(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"sub_question": "test", "search_strategy": "vector", "keywords": ["test"], "target_folders": [], "reasoning": "test"}')]
        self.mock_client.messages.create.return_value = mock_response

        plan = self.planner.create_plan("test question", {})

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["sub_question"], "test")

    def test_create_plan_accepts_array_wrapped_in_plain_text(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='Plan follows:\n[{"step_number": 1, "sub_question": "test", "search_strategy": "vector", "keywords": ["test"], "target_folders": [], "reasoning": "test"}]')]
        self.mock_client.messages.create.return_value = mock_response

        plan = self.planner.create_plan("test question", {})

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["sub_question"], "test")

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

    def test_create_plan_uses_summary_fast_path_without_model_call(self):
        plan = self.planner.create_plan(
            "Provide a point form summary of The Wisdom of Psychopaths",
            {}
        )

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["search_strategy"], "vector")
        self.assertIn("summary", plan[0]["reasoning"].lower())
        self.mock_client.messages.create.assert_not_called()

    def test_create_plan_invalid_payload_falls_back(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"foo": "bar"}')]
        self.mock_client.messages.create.return_value = mock_response

        plan = self.planner.create_plan("test question", {})

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["search_strategy"], "hybrid")

    def _build_extension_state(self, retrieved_documents=None):
        return {
            "original_question": "orig",
            "plan": [{"step_number": 1}],
            "past_steps": [{
                "step": {
                    "step_number": 1,
                    "sub_question": "q",
                    "keywords": ["CAR-T"],
                },
                "key_findings": "f",
            }],
            "retrieved_documents": retrieved_documents or [],
        }

    def test_extend_plan_success(self):
        # Mock response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='[{"sub_question": "new step", "search_strategy": "graph", "keywords": [], "target_folders": [], "reasoning": "gap"}]')]
        self.mock_client.messages.create.return_value = mock_response

        state = self._build_extension_state()
        
        new_steps = self.planner.extend_plan(state)
        
        self.assertEqual(len(new_steps), 1)
        self.assertEqual(new_steps[0]["step_number"], 2)
        self.assertEqual(new_steps[0]["sub_question"], "new step")
        self.assertEqual(new_steps[0]["references"], [])

    def test_extend_plan_accepts_wrapped_steps_object(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"steps":[{"sub_question": "new step", "search_strategy": "graph", "keywords": [], "target_folders": [], "reasoning": "gap"}]}')]
        self.mock_client.messages.create.return_value = mock_response

        state = self._build_extension_state()

        new_steps = self.planner.extend_plan(state)

        self.assertEqual(len(new_steps), 1)
        self.assertEqual(new_steps[0]["step_number"], 2)
        self.assertEqual(new_steps[0]["sub_question"], "new step")

    def test_extend_plan_prompt_lists_vault_files_and_entities(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"steps": []}')]
        self.mock_client.messages.create.return_value = mock_response

        state = self._build_extension_state([
            {
                "filepath": "Medical/CAR-T.md",
                "source": "Medical/CAR-T.md",
                "filename": "CAR-T.md",
                "keywords": ["CAR-T", "DLBCL"],
                "source_category": "vault",
            }
        ])

        self.planner.extend_plan(state)
        prompt = self.mock_client.messages.create.call_args.kwargs["messages"][0]["content"]

        self.assertIn("Retrieved vault files:", prompt)
        self.assertIn("Medical/CAR-T.md", prompt)
        self.assertIn("Key entities extracted from those files:", prompt)
        self.assertIn("CAR-T", prompt)
        self.assertIn('All new steps must reference at least one of these files or entities', prompt)

    def test_extend_plan_keeps_steps_vault_anchored_when_docs_exist(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"steps":[{"sub_question":"What does Medical/CAR-T.md say about DLBCL?","search_strategy":"vector","keywords":["CAR-T"],"target_folders":[],"reasoning":"gap","references":["CAR-T.md"]}]}')]
        self.mock_client.messages.create.return_value = mock_response

        state = self._build_extension_state([
            {
                "filepath": "Medical/CAR-T.md",
                "source": "Medical/CAR-T.md",
                "filename": "CAR-T.md",
                "keywords": ["CAR-T", "DLBCL"],
                "source_category": "vault",
            }
        ])

        new_steps = self.planner.extend_plan(state)

        self.assertEqual(len(new_steps), 1)
        self.assertIn("Medical/CAR-T.md", new_steps[0]["references"])
        self.assertIn("CAR-T", new_steps[0]["references"])

    def test_extend_plan_rejects_unanchored_steps_when_vault_docs_exist(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"steps":[{"sub_question":"What are the latest external guidelines?","search_strategy":"web","keywords":["guidelines"],"target_folders":[],"reasoning":"gap","references":[]}]}')]
        self.mock_client.messages.create.return_value = mock_response

        state = self._build_extension_state([
            {
                "filepath": "Medical/CAR-T.md",
                "source": "Medical/CAR-T.md",
                "filename": "CAR-T.md",
                "keywords": ["CAR-T"],
                "source_category": "vault",
            }
        ])

        new_steps = self.planner.extend_plan(state)

        self.assertEqual(new_steps, [])

    def test_extend_plan_allows_web_drift_when_no_vault_docs_exist(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"steps":[{"sub_question":"What are the latest external guidelines?","search_strategy":"web","keywords":["guidelines"],"target_folders":[],"reasoning":"gap"}]}')]
        self.mock_client.messages.create.return_value = mock_response

        state = self._build_extension_state([])

        new_steps = self.planner.extend_plan(state)

        self.assertEqual(len(new_steps), 1)
        self.assertEqual(new_steps[0]["search_strategy"], "web")
        self.assertEqual(new_steps[0]["references"], [])

    def test_extend_plan_skips_summary_query_replanning(self):
        state = self._build_extension_state([
            {
                "filepath": "Books/Books/The Wisdom of Psychopaths.md",
                "source": "Books/Books/The Wisdom of Psychopaths.md",
                "filename": "The Wisdom of Psychopaths.md",
                "source_category": "vault",
            }
        ])
        state["original_question"] = "Provide a point form summary of The Wisdom of Psychopaths"

        new_steps = self.planner.extend_plan(state)

        self.assertEqual(new_steps, [])
        self.mock_client.messages.create.assert_not_called()

if __name__ == '__main__':
    unittest.main()
