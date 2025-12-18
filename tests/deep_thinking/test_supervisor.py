import unittest
from unittest.mock import MagicMock, patch
from deep_thinking.supervisor import RetrievalSupervisor

class TestRetrievalSupervisor(unittest.TestCase):
    def setUp(self):
        self.supervisor = RetrievalSupervisor("http://vector", "http://graph")

    def test_build_filters_single(self):
        filters = self.supervisor._build_filters(["Medical/"])
        self.assertEqual(filters, {"source": {"$contains": "Medical/"}})

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
        # Verify filters were passed
        mock_post.assert_called_with(
            'http://vector/query',
            json={
                "query": "q",
                "n_results": 10,
                "where": {"source": {"$contains": "Medical/"}},
                "reranking": True,
                "deduplicate": True
            },
            timeout=30
        )

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
