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

    def test_decide_conceptual_query_does_not_force_external_enrichment(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"decision": "FINISH", "reasoning": "done", "needs_external_enrichment": true}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "How do asymptotes relate to derivatives?",
            "past_steps": [{
                "step": {"step_number": 1, "sub_question": "Search math notes", "search_strategy": "vector", "keywords": ["asymptote", "derivative"], "target_folders": ["Math/"], "reasoning": ""},
                "confidence": 0.8,
                "key_findings": "Found notes about asymptotes, derivatives, and limits.",
            }],
            "plan": [{"step_number": 1, "search_strategy": "vector"}],
            "current_step_index": 1,
            "iteration_count": 1,
            "max_iterations": 5,
        }

        decision = self.policy.decide(state)
        self.assertEqual(decision, "FINISH")

    def test_decide_vault_scoped_query_continues_when_vault_step_remains(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"decision": "FINISH", "reasoning": "done", "needs_external_enrichment": false}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "How are my notes connected to follow-up scan notes?",
            "past_steps": [{
                "step": {"step_number": 1, "sub_question": "Check outside references", "search_strategy": "web", "keywords": [], "target_folders": [], "reasoning": ""},
                "confidence": 0.6,
                "key_findings": "Found general follow-up guidance.",
            }],
            "retrieved_documents": [
                {
                    "filepath": "https://example.com/follow-up",
                    "source_category": "web",
                    "snippet": "General follow-up guidance.",
                }
            ],
            "plan": [
                {"step_number": 1, "search_strategy": "web"},
                {"step_number": 2, "search_strategy": "vector"},
            ],
            "current_step_index": 1,
            "iteration_count": 1,
            "max_iterations": 5,
        }

        decision = self.policy.decide(state)
        self.assertEqual(decision, "CONTINUE")

    def test_decide_vault_scoped_query_revises_when_only_web_evidence_exists(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"decision": "FINISH", "reasoning": "done", "needs_external_enrichment": false}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "How are treatment notes connected to scan notes?",
            "past_steps": [{
                "step": {"step_number": 1, "sub_question": "Check outside references", "search_strategy": "web", "keywords": [], "target_folders": [], "reasoning": ""},
                "confidence": 0.6,
                "key_findings": "Found general follow-up guidance.",
            }],
            "retrieved_documents": [
                {
                    "filepath": "https://example.com/follow-up",
                    "source_category": "web",
                    "snippet": "General follow-up guidance.",
                }
            ],
            "plan": [
                {"step_number": 1, "search_strategy": "web"},
            ],
            "current_step_index": 1,
            "iteration_count": 1,
            "max_iterations": 5,
        }

        decision = self.policy.decide(state)
        self.assertEqual(decision, "REVISE_PLAN")

    def test_decide_vault_scoped_query_revises_when_vault_evidence_is_only_thin_metadata(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"decision": "FINISH", "reasoning": "done", "needs_external_enrichment": false}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "How are my treatment notes connected to scan notes?",
            "past_steps": [{
                "step": {"step_number": 1, "sub_question": "Check graph links", "search_strategy": "graph-local", "keywords": [], "target_folders": [], "reasoning": ""},
                "confidence": 0.6,
                "key_findings": "Found graph links.",
            }],
            "retrieved_documents": [
                {
                    "filepath": "Medical/Treatment Notes.md",
                    "source_category": "vault",
                    "source_type": "entity-context",
                    "snippet": "On explicit graph path. depth=9, seed_hits=8.",
                }
            ],
            "plan": [
                {"step_number": 1, "search_strategy": "graph-local"},
            ],
            "current_step_index": 1,
            "iteration_count": 1,
            "max_iterations": 5,
        }

        decision = self.policy.decide(state)
        self.assertEqual(decision, "REVISE_PLAN")

    def test_decide_vault_scoped_comparison_finishes_when_only_one_side_has_vault_evidence(self):
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"decision": "REVISE_PLAN", "reasoning": "need more data", "needs_external_enrichment": false}')]
        self.mock_client.messages.create.return_value = mock_response

        state = {
            "original_question": "From my vault, what is the difference between the bambu p1s and the Creality CR-10",
            "past_steps": [
                {
                    "step": {"step_number": 1, "sub_question": "Find P1S and CR-10 notes", "search_strategy": "vector", "keywords": [], "target_folders": [], "reasoning": ""},
                    "confidence": 0.4,
                    "key_findings": "The vault has detailed P1S specs but no CR-10 evidence.",
                }
            ],
            "retrieved_documents": [
                {
                    "filepath": "Tech/3D-Printing/media/bambu-lab-P1S-tech-specs.pdf",
                    "source_category": "vault",
                    "source_type": "direct-excerpt",
                    "snippet": "Build volume 256 x 256 x 256 mm. Hotend 300 C. Max toolhead speed 500 mm/s.",
                },
                {
                    "filepath": "Tech/3D-Printing/Bambu Labs MoC.md",
                    "source_category": "vault",
                    "source_type": "direct-excerpt",
                    "snippet": "Overview of Bambu printer notes and resources for the P1S.",
                },
            ],
            "plan": [
                {"step_number": 1, "search_strategy": "vector"},
            ],
            "current_step_index": 1,
            "iteration_count": 1,
            "max_iterations": 5,
        }

        decision = self.policy.decide(state)
        self.assertEqual(decision, "FINISH")

if __name__ == '__main__':
    unittest.main()
