import sys
import types
import unittest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

fake_st = types.SimpleNamespace(
    CrossEncoder=lambda *args, **kwargs: types.SimpleNamespace(
        predict=lambda pairs: [0.9 for _ in pairs]
    )
)
sys.modules.setdefault("sentence_transformers", fake_st)

from deep_thinking.supervisor import RetrievalSupervisor

class TestRetrievalSupervisor(unittest.TestCase):
    def setUp(self):
        self.supervisor = RetrievalSupervisor("http://vector", "http://graph")

    def test_build_filters_single(self):
        filters = self.supervisor._build_filters(["Medical/"])
        self.assertEqual(filters, {"dir_Medical": True})

    def test_build_filters_multiple(self):
        filters = self.supervisor._build_filters(["Medical/", "Tech/"])
        self.assertTrue("$or" in filters)
        self.assertEqual(len(filters["$or"]), 2)

    def test_build_filters_empty(self):
        filters = self.supervisor._build_filters([])
        self.assertEqual(filters, {})

    @patch('requests.post')
    def test_execute_step_vector(self, mock_post):
        # Mock vector response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"text": "content", "metadata": {"file_path": "path"}, "score": 0.9}]}
        mock_post.return_value = mock_response

        step = {
            "sub_question": "q",
            "search_strategy": "vector",
            "keywords": [],
            "target_folders": ["Medical/"],
            "reasoning": ""
        }
        
        results = self.supervisor.execute_step(step, {})
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["type"], "vector")
        self.assertEqual(results[0]["source"], "path")

        expected_n_results = 60 if self.supervisor.enable_reranking else 20
        first_call_args, first_call_kwargs = mock_post.call_args_list[0]
        self.assertEqual(first_call_args[0], 'http://vector/query')
        self.assertEqual(first_call_kwargs["timeout"], 30)

        payload = first_call_kwargs["json"]
        self.assertEqual(payload["query"], "q Medical")
        self.assertEqual(payload["n_results"], expected_n_results)
        self.assertEqual(payload["filters"], {"dir_Medical": True})
        self.assertFalse(payload["reranking"])
        self.assertTrue(payload["deduplicate"])

    @patch('requests.post')
    def test_execute_step_graph(self, mock_post):
        # Mock graph response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "graph answer"}
        mock_post.return_value = mock_response

        step = {
            "sub_question": "q",
            "search_strategy": "graph",
            "keywords": [],
            "target_folders": [],
            "reasoning": ""
        }
        
        results = self.supervisor.execute_step(step, {})
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source_type"], "graph-reasoning")
        self.assertTrue(results[0]["internal_only"])
        self.assertEqual(results[0]["content"], "graph answer")

    @patch('requests.post')
    def test_query_graph_forwards_provider_and_model(self, mock_post):
        supervisor = RetrievalSupervisor(
            "http://vector",
            "http://graph",
            llm_provider="mlx",
            llm_model="mlx-community/Qwen3-4B-8bit",
            enable_reranking=False,
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "graph answer"}
        mock_post.return_value = mock_response

        supervisor._query_graph("esp32-s3 vs esp32-c3", mode="hybrid")

        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        self.assertEqual(payload["llm_provider"], "mlx")
        self.assertEqual(payload["model"], "mlx-community/Qwen3-4B-8bit")

    def test_rank_sources_persists_summary_match_flags(self):
        docs = [
            {
                "source": "Books/Books/A Mind for Numbers.md",
                "filepath": "Books/Books/A Mind for Numbers.md",
                "filename": "A Mind for Numbers.md",
                "title": "A Mind for Numbers",
                "snippet": "Focused and diffuse modes matter.",
                "content": "Focused and diffuse modes matter.",
                "source_category": "vault",
                "source_type": "direct-excerpt",
                "score": 0.9,
            },
            {
                "source": "Books/Books/The Mind Club.md",
                "filepath": "Books/Books/The Mind Club.md",
                "filename": "The Mind Club.md",
                "title": "The Mind Club",
                "snippet": "Mind is a matter of perception.",
                "content": "Mind is a matter of perception.",
                "source_category": "vault",
                "source_type": "direct-excerpt",
                "score": 0.4,
            },
        ]

        ranked = RetrievalSupervisor.rank_sources_for_query(
            "Provide a point form summary of A Mind for Numbers",
            docs,
            max_results=5,
        )

        self.assertTrue(ranked[0]["_summary_focus_exact_match"])
        self.assertTrue(ranked[0]["_summary_focus_title_match"])

    def test_build_query_profile_marks_timeless_conceptual_queries_reasoning_first(self):
        profile = RetrievalSupervisor.build_query_profile(
            "How do asymptotes relate to derivatives?"
        )

        self.assertTrue(profile["is_conceptual_explanation"])
        self.assertTrue(profile["prefers_reasoning_first"])
        self.assertFalse(profile["requires_current_information"])
        self.assertFalse(profile["needs_authoritative_sources"])
        self.assertFalse(profile["needs_external_authority"])

    def test_build_query_profile_includes_structured_relationship_normalization(self):
        profile = RetrievalSupervisor.build_query_profile(
            "How are my lymphoma treatment notes connected to follow-up scan notes?"
        )

        self.assertTrue(profile["is_relationship"])
        self.assertEqual(profile["intent"], "relationship")
        self.assertEqual(profile["anchor_entities"], ["lymphoma treatment", "follow-up scan"])
        self.assertEqual(profile["relations"], ["connected to"])
        self.assertEqual(
            profile["clean_query"],
            "relationship between lymphoma treatment and follow-up scan",
        )
        self.assertEqual(profile["facets"], [["lymphoma", "treatment"], ["follow-up", "scan"]])

    def test_build_query_profile_marks_specs_query_as_authority_seeking(self):
        profile = RetrievalSupervisor.build_query_profile(
            "What are the official specs of ESP32?"
        )

        self.assertFalse(profile["prefers_reasoning_first"])
        self.assertTrue(profile["needs_authoritative_sources"])
        self.assertTrue(profile["needs_external_authority"])

    @patch('requests.post')
    def test_query_graph_drops_synthesis_summary_from_results(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "sources": [{
                "filepath": "Medical/Graph/Entity.md",
                "filename": "Entity.md",
                "snippet": "entity snippet",
                "relevance": 87,
            }],
            "answer": "This is a synthesized graph answer."
        }
        mock_post.return_value = mock_response

        results = self.supervisor._query_graph("query", mode="hybrid")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["source"], "Medical/Graph/Entity.md")
        self.assertFalse(any(doc.get("source") == "Graph Synthesis Summary" for doc in results))

    def test_execute_step_hybrid_filters_graph_summary_before_rerank(self):
        vector_docs = [{
            "content": "vector content",
            "source": "Medical/Vector.md",
            "filepath": "Medical/Vector.md",
            "type": "vector",
            "source_category": "vault",
            "score": 0.8,
        }]
        graph_docs = [
            {
                "content": "graph snippet",
                "source": "Medical/Graph.md",
                "filepath": "Medical/Graph.md",
                "type": "graph",
                "source_category": "vault",
                "score": 0.7,
            },
            {
                "content": "synthetic summary",
                "source": "Graph Synthesis Summary",
                "type": "graph",
                "is_summary": True,
                "score": 1.0,
            },
        ]
        self.supervisor.enable_reranking = True
        self.supervisor.reranker = MagicMock()
        self.supervisor.reranker.rerank.side_effect = lambda query, docs, top_k=20: docs

        with patch.object(self.supervisor, "_query_vector", return_value=vector_docs), patch.object(
            self.supervisor, "_query_graph", return_value=graph_docs
        ):
            results = self.supervisor.execute_step(
                {
                    "step_number": 1,
                    "sub_question": "q",
                    "search_strategy": "hybrid",
                    "keywords": [],
                    "target_folders": [],
                    "reasoning": "",
                },
                {"original_question": "", "warnings": []},
            )

        rerank_docs = self.supervisor.reranker.rerank.call_args.args[1]
        self.assertFalse(any(doc.get("source") == "Graph Synthesis Summary" for doc in rerank_docs))
        self.assertFalse(any(doc.get("source") == "Graph Synthesis Summary" for doc in results))

    def test_effective_metadata_ignores_contradictory_chemotherapy_phase_for_car_t_content(self):
        metadata = RetrievalSupervisor._effective_metadata(
            {
                "filename": "Yescarta.pdf",
                "content": "Yescarta is a CD19-directed CAR-T cell therapy for relapsed or refractory DLBCL.",
                "treatment_phase": "chemotherapy",
                "tags": ["lymphoma"],
            }
        )

        self.assertIn("car_t", metadata["tags"])
        self.assertNotIn("chemotherapy", metadata["tags"])

    def test_rank_sources_for_relationship_query_prefers_direct_drug_disease_evidence(self):
        docs = [
            {
                "source": "Medical/Lymphoma/Diagnosis and Options.md",
                "filepath": "Medical/Lymphoma/Diagnosis and Options.md",
                "filename": "Diagnosis and Options.md",
                "snippet": "Overview of diagnosis and treatment options for lymphoma.",
                "content": "Overview of diagnosis and treatment options for lymphoma.",
                "source_category": "vault",
                "source_type": "entity-context",
                "score": 0.96,
            },
            {
                "source": "Medical/Lymphoma/R-CHOP.md",
                "filepath": "Medical/Lymphoma/R-CHOP.md",
                "filename": "R-CHOP.md",
                "snippet": "R-CHOP is a chemotherapy regimen used in DLBCL.",
                "content": "R-CHOP is a chemotherapy regimen used in DLBCL.",
                "source_category": "vault",
                "source_type": "entity-context",
                "score": 0.95,
                "treatment_phase": "chemotherapy",
            },
            {
                "source": "Medical/Lymphoma/media/Yescarta.pdf",
                "filepath": "Medical/Lymphoma/media/Yescarta.pdf",
                "filename": "Yescarta.pdf",
                "snippet": "Yescarta (axicabtagene ciloleucel) is a CD19-directed CAR-T cell therapy indicated for adult patients with relapsed or refractory large B-cell lymphoma, including DLBCL.",
                "content": "Yescarta (axicabtagene ciloleucel) is a CD19-directed CAR-T cell therapy indicated for adult patients with relapsed or refractory large B-cell lymphoma, including DLBCL.",
                "source_category": "vault",
                "source_type": "direct-excerpt",
                "score": 0.62,
                "treatment_phase": "chemotherapy",
            },
            {
                "source": "Medical/Lymphoma/DLBCL, Follicular Lymphoma.md",
                "filepath": "Medical/Lymphoma/DLBCL, Follicular Lymphoma.md",
                "filename": "DLBCL, Follicular Lymphoma.md",
                "snippet": "DLBCL is a subtype of large B-cell lymphoma.",
                "content": "DLBCL is a subtype of large B-cell lymphoma.",
                "source_category": "vault",
                "source_type": "entity-context",
                "score": 0.7,
                "tags": ["lymphoma"],
            },
        ]

        ranked = RetrievalSupervisor.rank_sources_for_query(
            "What is the connection between Yescarta and DLBCL?",
            docs,
        )

        self.assertLessEqual(len(ranked), 3)
        self.assertEqual(ranked[0]["filename"], "Yescarta.pdf")
        self.assertNotIn("R-CHOP.md", [doc["filename"] for doc in ranked])

    def test_medical_relationship_drops_suspicious_tech_vault_doc(self):
        docs = [
            {
                "source": "Tech/Electronics/Projects/Halcyon/Blynk-local-server-auth-token.md",
                "filepath": "Tech/Electronics/Projects/Halcyon/Blynk-local-server-auth-token.md",
                "filename": "Blynk-local-server-auth-token.md",
                "snippet": "Authentication token setup for the local Blynk server.",
                "content": "Authentication token setup for the local Blynk server.",
                "source_category": "vault",
                "source_type": "direct-excerpt",
                "score": 0.99,
            },
            {
                "source": "https://ncbi.nlm.nih.gov/books/NBK550115",
                "filepath": "https://ncbi.nlm.nih.gov/books/NBK550115",
                "filename": "Axicabtagene Ciloleucel for Large B-cell Lymphoma - NCBI - NIH",
                "snippet": "Axicabtagene ciloleucel is indicated for large B-cell lymphoma including DLBCL.",
                "content": "Axicabtagene ciloleucel is indicated for large B-cell lymphoma including DLBCL.",
                "source_category": "web",
                "source_type": "web-result",
                "score": 0.91,
            },
        ]

        selected = RetrievalSupervisor.select_minimal_evidence_set(
            "How is axicabtagene ciloleucel related to diffuse large B-cell lymphoma?",
            docs,
            max_docs=3,
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["source_category"], "web")

    def test_select_minimal_evidence_set_treats_connected_to_as_relationship_query(self):
        docs = [
            {
                "source": "Medical/Lymphoma/Lymphoma Treatment Summary.md",
                "filepath": "Medical/Lymphoma/Lymphoma Treatment Summary.md",
                "filename": "Lymphoma Treatment Summary.md",
                "snippet": "Treatment summary linked to lymphoma treatment and treatment log.",
                "content": "Treatment summary linked to lymphoma treatment and treatment log.",
                "source_category": "vault",
                "source_type": "direct-excerpt",
                "score": 0.95,
            },
            {
                "source": "Medical/Lymphoma/CT Scan Post-CAR-T.md",
                "filepath": "Medical/Lymphoma/CT Scan Post-CAR-T.md",
                "filename": "CT Scan Post-CAR-T.md",
                "snippet": "Follow-up scan findings after CAR-T therapy.",
                "content": "Follow-up scan findings after CAR-T therapy.",
                "source_category": "vault",
                "source_type": "direct-excerpt",
                "score": 0.72,
            },
            {
                "source": "Medical/Lymphoma/Random Overview.md",
                "filepath": "Medical/Lymphoma/Random Overview.md",
                "filename": "Random Overview.md",
                "snippet": "General overview of lymphoma topics.",
                "content": "General overview of lymphoma topics.",
                "source_category": "vault",
                "source_type": "direct-excerpt",
                "score": 0.99,
            },
        ]

        selected = RetrievalSupervisor.select_minimal_evidence_set(
            "How are my lymphoma treatment notes connected to follow-up scan notes?",
            docs,
            max_docs=2,
        )

        self.assertEqual(
            [doc["filepath"] for doc in selected],
            [
                "Medical/Lymphoma/Lymphoma Treatment Summary.md",
                "Medical/Lymphoma/CT Scan Post-CAR-T.md",
            ],
        )

    def test_select_minimal_evidence_set_preserves_multi_facet_coverage_after_bridge_selection(self):
        query = "How are my treatment notes connected to follow-up scan notes?"
        treatment_doc = {
            "source": "Medical/Lymphoma/Lymphoma Treatment Summary.md",
            "filepath": "Medical/Lymphoma/Lymphoma Treatment Summary.md",
            "filename": "Lymphoma Treatment Summary.md",
            "snippet": "Treatment summary.",
            "content": "Treatment summary and treatment log.",
            "source_category": "vault",
            "source_type": "direct-excerpt",
            "_query_rank_score": 7.0,
            "_anchor_entities_found": ["treatment"],
        }
        bridge_doc = {
            "source": "Medical/Lymphoma/Lymphoma Treatment Log.md",
            "filepath": "Medical/Lymphoma/Lymphoma Treatment Log.md",
            "filename": "Lymphoma Treatment Log.md",
            "snippet": "Treatment log referencing scan follow-up.",
            "content": "Treatment log referencing follow-up scan scheduling.",
            "source_category": "vault",
            "source_type": "direct-excerpt",
            "_query_rank_score": 6.8,
            "_anchor_entities_found": ["treatment"],
        }
        scan_doc = {
            "source": "Medical/Lymphoma/Scans After Yescarta Treatment.md",
            "filepath": "Medical/Lymphoma/Scans After Yescarta Treatment.md",
            "filename": "Scans After Yescarta Treatment.md",
            "snippet": "Follow-up scan results after treatment.",
            "content": "Follow-up scan results after treatment.",
            "source_category": "vault",
            "source_type": "direct-excerpt",
            "_query_rank_score": 6.2,
            "_anchor_entities_found": ["scan"],
        }

        with patch.object(
            RetrievalSupervisor,
            "build_query_profile",
            return_value={"is_relationship": True, "max_sources": 3, "anchor_entities": ["treatment", "scan"]},
        ), patch.object(
            RetrievalSupervisor,
            "filter_vault_docs_by_domain_and_entities",
            side_effect=lambda docs, _profile: docs,
        ), patch.object(
            RetrievalSupervisor,
            "rank_sources_for_query",
            return_value=[treatment_doc, bridge_doc, scan_doc],
        ), patch(
            "deep_thinking.supervisor.has_multi_facet_query",
            return_value=True,
        ), patch(
            "deep_thinking.supervisor.source_set_covers_query_facets",
            side_effect=lambda _query, docs: any(doc["filepath"].endswith("Treatment Summary.md") for doc in docs)
            and any(doc["filepath"].endswith("Scans After Yescarta Treatment.md") for doc in docs),
        ), patch(
            "deep_thinking.supervisor.source_facet_match_indexes",
            side_effect=lambda doc, _query: {0}
            if doc["filepath"].endswith("Treatment Summary.md") or doc["filepath"].endswith("Treatment Log.md")
            else {1},
        ), patch.object(
            RetrievalSupervisor,
            "_bridge_overlap_score",
            side_effect=lambda doc, chosen, _profile: 2 if doc["filepath"].endswith("Treatment Log.md") else 0,
        ):
            selected = RetrievalSupervisor.select_minimal_evidence_set(query, [treatment_doc, bridge_doc, scan_doc], max_docs=3)

        self.assertEqual(
            [doc["filepath"] for doc in selected],
            [
                "Medical/Lymphoma/Lymphoma Treatment Summary.md",
                "Medical/Lymphoma/Scans After Yescarta Treatment.md",
                "Medical/Lymphoma/Lymphoma Treatment Log.md",
            ],
        )

    def test_preserve_multi_facet_query_coverage_supplements_second_side(self):
        query = "How are my lymphoma treatment notes connected to follow-up scan notes?"
        treatment_doc = {
            "source": "Medical/Lymphoma/Lymphoma Treatment Summary.md",
            "filepath": "Medical/Lymphoma/Lymphoma Treatment Summary.md",
            "filename": "Lymphoma Treatment Summary.md",
            "snippet": "Treatment summary covering chemotherapy and CAR-T planning.",
            "content": "Treatment summary covering chemotherapy and CAR-T planning.",
            "source_category": "vault",
            "source_type": "direct-excerpt",
            "_query_rank_score": 7.0,
        }
        scan_doc = {
            "source": "Medical/Lymphoma/4th PET Scan - Treatment Options.md",
            "filepath": "Medical/Lymphoma/4th PET Scan - Treatment Options.md",
            "filename": "4th PET Scan - Treatment Options.md",
            "snippet": "Follow-up scan notes and PET scan findings after treatment.",
            "content": "Follow-up scan notes and PET scan findings after treatment.",
            "source_category": "vault",
            "source_type": "direct-excerpt",
            "_query_rank_score": 6.5,
        }

        def fake_indexes(doc, _query):
            if doc["filepath"].endswith("Lymphoma Treatment Summary.md"):
                return {0}
            if doc["filepath"].endswith("4th PET Scan - Treatment Options.md"):
                return {1}
            return set()

        with patch("deep_thinking.supervisor.has_multi_facet_query", return_value=True), patch(
            "deep_thinking.supervisor.source_set_covers_query_facets",
            side_effect=lambda _query, docs: len(set().union(*(fake_indexes(doc, _query) for doc in docs))) >= 2,
        ), patch(
            "deep_thinking.supervisor.source_facet_match_indexes",
            side_effect=fake_indexes,
        ):
            supplemented = RetrievalSupervisor._preserve_multi_facet_query_coverage(
                query,
                [treatment_doc],
                [treatment_doc, scan_doc],
                max_results=5,
            )

        self.assertEqual(
            [doc["filepath"] for doc in supplemented],
            [
                "Medical/Lymphoma/Lymphoma Treatment Summary.md",
                "Medical/Lymphoma/4th PET Scan - Treatment Options.md",
            ],
        )

    def test_summary_query_excludes_prompt_template_docs_and_prefers_exact_vault_note(self):
        docs = [
            {
                "source": "Books/Books/The Wisdom of Psychopaths.md",
                "filepath": "Books/Books/The Wisdom of Psychopaths.md",
                "filename": "The Wisdom of Psychopaths.md",
                "title": "The Wisdom of Psychopaths",
                "snippet": "Main idea and highlights.",
                "content": "Main idea and highlights.",
                "source_category": "vault",
                "source_type": "direct-excerpt",
                "score": 0.72,
            },
            {
                "source": "copilot/copilot-custom-prompts/Summarize.md",
                "filepath": "copilot/copilot-custom-prompts/Summarize.md",
                "filename": "Summarize.md",
                "title": "Summarize",
                "snippet": "Create a bullet-point summary of {}.",
                "content": "Create a bullet-point summary of {}.",
                "source_category": "vault",
                "source_type": "direct-excerpt",
                "score": 0.99,
            },
            {
                "source": "https://blinkist.com/en/books/the-wisdom-of-psychopaths-en",
                "filepath": "https://blinkist.com/en/books/the-wisdom-of-psychopaths-en",
                "filename": "Blinkist Summary",
                "title": "The Wisdom of Psychopaths Summary",
                "snippet": "External summary.",
                "content": "External summary.",
                "source_category": "web",
                "source_type": "web-result",
                "score": 0.95,
            },
        ]

        selected = RetrievalSupervisor.select_minimal_evidence_set(
            "Provide a point form summary of The Wisdom of Psychopaths",
            docs,
            max_docs=5,
        )

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["filepath"], "Books/Books/The Wisdom of Psychopaths.md")

    def test_resolve_expansion_target_uses_vault_relative_index_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir)
            note_path = vault_root / "Medical" / "CAR-T.md"
            note_path.parent.mkdir(parents=True, exist_ok=True)
            note_path.write_text("full content", encoding="utf-8")

            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault_root)}):
                target = self.supervisor._resolve_expansion_target({"filepath": "Medical/CAR-T.md"})

            self.assertIsNotNone(target)
            self.assertEqual(target["source"], "Medical/CAR-T.md")
            self.assertEqual(Path(target["full_path"]).resolve(), note_path.resolve())

    def test_resolve_expansion_target_normalizes_absolute_path_to_index_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir)
            note_path = vault_root / "Medical" / "CAR-T.md"
            note_path.parent.mkdir(parents=True, exist_ok=True)
            note_path.write_text("full content", encoding="utf-8")

            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault_root)}):
                target = self.supervisor._resolve_expansion_target({"filepath": str(note_path)})

            self.assertIsNotNone(target)
            self.assertEqual(target["source"], "Medical/CAR-T.md")
            self.assertEqual(Path(target["full_path"]).resolve(), note_path.resolve())

    def test_expand_doc_with_cache_reuses_normalized_source_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir)
            note_path = vault_root / "Medical" / "CAR-T.md"
            note_path.parent.mkdir(parents=True, exist_ok=True)
            note_path.write_text("full content", encoding="utf-8")
            state = {}

            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault_root)}), patch.object(
                RetrievalSupervisor,
                "_load_full_content",
                return_value="full content",
            ) as mock_load:
                doc1 = self.supervisor.expand_doc_with_cache(
                    {"filepath": "Medical/CAR-T.md", "content": "snippet"},
                    state,
                    1024,
                )
                doc2 = self.supervisor.expand_doc_with_cache(
                    {"filepath": str(note_path), "content": "snippet"},
                    state,
                    1024,
                )

            self.assertTrue(doc1["is_full_content"])
            self.assertTrue(doc2["is_full_content"])
            self.assertEqual(mock_load.call_count, 1)
            cache_keys = list(state["_expansion_cache_v2"].keys())
            self.assertEqual(len(cache_keys), 1)
            self.assertEqual(cache_keys[0][0], "Medical/CAR-T.md")

    def test_expand_doc_with_cache_repairs_case_mismatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir)
            note_path = vault_root / "Medical" / "CAR-T.md"
            note_path.parent.mkdir(parents=True, exist_ok=True)
            note_path.write_text("full content", encoding="utf-8")
            state = {}

            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault_root)}), patch.object(
                RetrievalSupervisor,
                "_load_full_content",
                return_value="full content",
            ):
                doc = self.supervisor.expand_doc_with_cache(
                    {"filepath": "medical/car-t.md", "content": "snippet"},
                    state,
                    1024,
                )

            self.assertTrue(doc["is_full_content"])
            cache_keys = list(state["_expansion_cache_v2"].keys())
            self.assertEqual(cache_keys[0][0], "Medical/CAR-T.md")

    def test_expand_doc_with_cache_logs_missing_file_with_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vault_root = Path(tmpdir)
            state = {}

            with patch.dict("os.environ", {"OBSIDIAN_VAULT_PATH": str(vault_root)}):
                with self.assertLogs("deep_thinking.supervisor", level="WARNING") as logs:
                    doc = self.supervisor.expand_doc_with_cache(
                        {"filepath": "Medical/Missing.md", "content": "snippet"},
                        state,
                        1024,
                    )

            self.assertEqual(doc["content"], "snippet")
            joined = "\n".join(logs.output)
            self.assertIn("raw_source=Medical/Missing.md", joined)
            self.assertIn("normalized_source=Medical/Missing.md", joined)
            self.assertIn("resolved_path=", joined)

if __name__ == '__main__':
    unittest.main()
