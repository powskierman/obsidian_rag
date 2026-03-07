import unittest
from unittest.mock import MagicMock, patch
from deep_thinking.orchestrator import DeepThinkingRAG
from deep_thinking.planner import PlannerAgent

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

    @patch.dict("os.environ", {}, clear=True)
    def test_orchestrator_v2_is_enabled_by_default(self):
        self.assertTrue(DeepThinkingRAG._use_orchestrator_v2())

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

    def test_query_flow_filters_graph_summary_before_reflection_and_sources(self):
        self.orchestrator.planner.create_plan.return_value = [{
            "step_number": 1,
            "sub_question": "q1",
            "search_strategy": "vector",
            "keywords": [],
            "target_folders": [],
            "reasoning": ""
        }]
        self.orchestrator.supervisor.execute_step.return_value = [
            {
                "content": "real graph evidence",
                "source": "Medical/GraphEvidence.md",
                "filepath": "Medical/GraphEvidence.md",
                "filename": "GraphEvidence.md",
                "snippet": "real graph evidence",
                "type": "graph",
                "source_category": "vault",
                "score": 0.9,
            },
            {
                "content": "synthetic summary",
                "source": "Graph Synthesis Summary",
                "type": "graph",
                "is_summary": True,
                "score": 1.0,
            },
        ]
        self.orchestrator.reflector.reflect.return_value = {"key_findings": "f1", "confidence": 0.9}
        self.orchestrator.policy.decide.return_value = "FINISH"

        def synthesize(state):
            self.assertEqual(len(state["retrieved_documents"]), 1)
            self.assertEqual(state["retrieved_documents"][0]["source"], "Medical/GraphEvidence.md")
            self.assertEqual(len(state["raw_context_buffer"]), 1)
            self.assertEqual(state["raw_context_buffer"][0]["source"], "Medical/GraphEvidence.md")
            return ("Final Answer", ["[[Medical/GraphEvidence.md]]"])

        self.orchestrator.synthesizer.generate.side_effect = synthesize

        result = self.orchestrator.query("question without forced vault markers")

        reflected_docs = self.orchestrator.reflector.reflect.call_args.args[1]
        self.assertEqual(len(reflected_docs), 1)
        self.assertEqual(reflected_docs[0]["source"], "Medical/GraphEvidence.md")
        self.assertFalse(any(source["filepath"] == "Graph Synthesis Summary" for source in result["sources"]))
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["filepath"], "Medical/GraphEvidence.md")

    def test_build_structured_sources_dedupes_canonical_web_urls(self):
        documents = [
            {
                "source": "https://www.example.com/guide?utm_source=newsletter",
                "filepath": "https://www.example.com/guide?utm_source=newsletter",
                "filename": "Guide A",
                "title": "Guide A",
                "snippet": "First snippet",
                "type": "web",
                "source_category": "web",
                "score": 0.9,
            },
            {
                "source": "https://example.com/guide?srsltid=123",
                "filepath": "https://example.com/guide?srsltid=123",
                "filename": "Guide B",
                "title": "Guide B",
                "snippet": "Second snippet",
                "type": "web",
                "source_category": "web",
                "score": 0.8,
            },
        ]

        sources = self.orchestrator._build_structured_sources(
            documents,
            ["https://example.com/guide"],
        )

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["filepath"], "https://example.com/guide")
        self.assertEqual(sources[0]["source_category"], "web")

    def test_build_structured_sources_excludes_internal_reasoning_docs(self):
        documents = [
            {
                "source": "Graph Reasoning Result",
                "filepath": "Graph Reasoning Result",
                "filename": "Graph Reasoning (local)",
                "snippet": "Internal graph reasoning",
                "content": "Internal graph reasoning",
                "type": "graph",
                "source_type": "graph-reasoning",
                "internal_only": True,
                "score": 0.6,
            },
            {
                "source": "Medical/GraphEvidence.md",
                "filepath": "Medical/GraphEvidence.md",
                "filename": "GraphEvidence.md",
                "snippet": "real graph evidence",
                "content": "real graph evidence",
                "type": "graph",
                "source_category": "vault",
                "source_type": "entity-context",
                "score": 0.9,
            },
        ]

        sources = self.orchestrator._build_structured_sources(
            documents,
            ["[[Medical/GraphEvidence.md]]"],
        )

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["filepath"], "Medical/GraphEvidence.md")

    def test_query_uses_only_synthesizer_used_documents_for_final_sources(self):
        self.orchestrator.planner.create_plan.return_value = [{
            "step_number": 1,
            "sub_question": "q1",
            "search_strategy": "vector",
            "keywords": [],
            "target_folders": [],
            "reasoning": ""
        }]
        self.orchestrator.supervisor.execute_step.return_value = [
            {
                "content": "yescarta evidence",
                "source": "Medical/Lymphoma/media/Yescarta.pdf",
                "filepath": "Medical/Lymphoma/media/Yescarta.pdf",
                "filename": "Yescarta.pdf",
                "snippet": "Yescarta is indicated for DLBCL.",
                "type": "vector",
                "score": 0.8,
                "source_category": "vault",
                "source_type": "direct-excerpt",
            },
            {
                "content": "generic overview",
                "source": "Medical/Lymphoma/Diagnosis and Options.md",
                "filepath": "Medical/Lymphoma/Diagnosis and Options.md",
                "filename": "Diagnosis and Options.md",
                "snippet": "Overview of lymphoma diagnosis and options.",
                "type": "graph",
                "score": 0.9,
                "source_category": "vault",
                "source_type": "entity-context",
            },
        ]
        self.orchestrator.reflector.reflect.return_value = {"key_findings": "f1", "confidence": 0.9}
        self.orchestrator.policy.decide.return_value = "FINISH"
        self.orchestrator.synthesizer.generate.return_value = {
            "answer": "Final Answer",
            "citations": ["[[Medical/Lymphoma/media/Yescarta.pdf]]"],
            "confidence_score": 0.91,
            "confidence_justification": "Direct indication evidence.",
            "used_documents": [
                {
                    "content": "yescarta evidence",
                    "source": "Medical/Lymphoma/media/Yescarta.pdf",
                    "filepath": "Medical/Lymphoma/media/Yescarta.pdf",
                    "filename": "Yescarta.pdf",
                    "snippet": "Yescarta is indicated for DLBCL.",
                    "type": "vector",
                    "score": 0.8,
                    "source_category": "vault",
                    "source_type": "direct-excerpt",
                }
            ],
        }

        result = self.orchestrator.query("What is the connection between Yescarta and DLBCL?")

        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["filename"], "Yescarta.pdf")
        self.assertEqual(result["sources"][0]["filepath"], "Medical/Lymphoma/media/Yescarta.pdf")

    def test_query_does_not_fetch_new_web_sources_after_synthesis(self):
        self.orchestrator.planner.create_plan.return_value = [{
            "step_number": 1,
            "sub_question": "Compare ESP32 vs ESP8266",
            "search_strategy": "vector",
            "keywords": [],
            "target_folders": [],
            "reasoning": ""
        }]
        self.orchestrator.supervisor.execute_step.side_effect = [
            [{
                "content": "vault note",
                "source": "Tech/ESP32.md",
                "filepath": "Tech/ESP32.md",
                "filename": "ESP32.md",
                "snippet": "vault note",
                "type": "vector",
                "score": 0.8,
                "source_category": "vault",
                "source_type": "direct-excerpt",
            }],
            [{
                "content": "web spec sheet",
                "source": "https://example.com/esp32-spec",
                "filepath": "https://example.com/esp32-spec",
                "filename": "ESP32 Spec",
                "snippet": "web spec sheet",
                "type": "web",
                "score": 0.9,
                "source_category": "web",
                "source_type": "web-result",
            }],
        ]
        self.orchestrator.reflector.reflect.return_value = {"key_findings": "f1", "confidence": 0.9}
        self.orchestrator.policy.decide.return_value = "FINISH"
        self.orchestrator.synthesizer.generate.return_value = {
            "answer": "Final Answer",
            "citations": ["[[Tech/ESP32.md]]"],
            "confidence_score": 0.9,
            "confidence_justification": "ok",
            "used_documents": [{
                "content": "vault note",
                "source": "Tech/ESP32.md",
                "filepath": "Tech/ESP32.md",
                "filename": "ESP32.md",
                "snippet": "vault note",
                "type": "vector",
                "score": 0.8,
                "source_category": "vault",
                "source_type": "direct-excerpt",
            }],
        }

        result = self.orchestrator.query("Compare ESP32 vs ESP8266 specs")

        self.assertEqual(self.orchestrator.supervisor.execute_step.call_count, 2)
        self.assertTrue(any("web evidence" in warning.lower() or "citable web sources" in warning.lower() for warning in result["warnings"]))

    def test_structured_sources_match_used_documents_exactly(self):
        used_documents = [
            {
                "source": "Medical/Lymphoma/media/Yescarta.pdf",
                "filepath": "Medical/Lymphoma/media/Yescarta.pdf",
                "filename": "Yescarta.pdf",
                "snippet": "Yescarta is indicated for DLBCL.",
                "source_category": "vault",
                "source_type": "direct-excerpt",
                "score": 0.9,
            },
            {
                "source": "https://ncbi.nlm.nih.gov/books/NBK550115",
                "filepath": "https://ncbi.nlm.nih.gov/books/NBK550115",
                "filename": "Axicabtagene Ciloleucel for Large B-cell Lymphoma - NCBI - NIH",
                "snippet": "Axicabtagene ciloleucel is indicated for DLBCL.",
                "source_category": "web",
                "source_type": "web-result",
                "score": 0.92,
            },
        ]

        sources = self.orchestrator._build_structured_sources(
            used_documents,
            ["[[Medical/Lymphoma/media/Yescarta.pdf]]", "https://ncbi.nlm.nih.gov/books/NBK550115"],
            max_sources=5,
        )
        sources = self.orchestrator._align_structured_sources_to_used_documents(
            sources,
            used_documents,
            max_sources=5,
        )

        self.assertEqual(
            self.orchestrator._document_identity_set(sources),
            self.orchestrator._document_identity_set(used_documents),
        )

    def test_extend_plan_with_enforcement_drops_unanchored_steps(self):
        planner = PlannerAgent(MagicMock())
        state = {
            "plan": [{"step_number": 1}],
            "retrieved_documents": [{
                "filepath": "Medical/CAR-T.md",
                "source": "Medical/CAR-T.md",
                "keywords": ["CAR-T"],
                "source_category": "vault",
            }],
            "past_steps": [{
                "step": {"step_number": 1, "sub_question": "q", "keywords": ["CAR-T"]},
                "key_findings": "f",
            }],
            "original_question": "orig",
        }
        proposed_steps = [
            {
                "sub_question": "Summarize Medical/CAR-T.md",
                "search_strategy": "vector",
                "keywords": ["CAR-T"],
                "target_folders": [],
                "reasoning": "gap",
            },
            {
                "sub_question": "What do generic external guidelines say?",
                "search_strategy": "web",
                "keywords": ["guidelines"],
                "target_folders": [],
                "reasoning": "gap",
            },
        ]
        planner.extend_plan = MagicMock(return_value=proposed_steps)
        self.orchestrator.planner = planner

        collected = []
        result = self.orchestrator._extend_plan_with_enforcement(
            state,
            lambda message, details=None: collected.append((message, details)),
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["references"], ["Medical/CAR-T.md", "CAR-T"])
        self.assertTrue(any(message == "   Dropped unanchored extension steps" for message, _ in collected))

if __name__ == '__main__':
    unittest.main()
