import sys
import types
import unittest
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
        self.assertEqual(results[0]["type"], "graph")

if __name__ == '__main__':
    unittest.main()
