import unittest
from unittest.mock import MagicMock
from deep_thinking.reflector import ReflectionAgent

class TestReflectionAgent(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.reflector = ReflectionAgent(self.mock_client)

    def test_reflect_success(self):
        # Mock response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"key_findings": "found something", "confidence": 0.8, "has_gaps": false}')]
        self.mock_client.messages.create.return_value = mock_response

        step = {"step_number": 1, "sub_question": "q", "search_strategy": "vector"}
        documents = [{"content": "doc1", "source": "s1"}]
        state = {"past_steps": []}
        
        past_step = self.reflector.reflect(step, documents, state)
        
        self.assertEqual(past_step["key_findings"], "found something")
        self.assertEqual(past_step["confidence"], 0.8)
        self.assertEqual(past_step["documents_found"], 1)

    def test_reflect_error(self):
        # Mock invalid JSON
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='invalid')]
        self.mock_client.messages.create.return_value = mock_response

        step = {"step_number": 1, "sub_question": "q"}
        documents = []
        state = {"past_steps": []}
        
        past_step = self.reflector.reflect(step, documents, state)
        
        self.assertEqual(past_step["key_findings"], "Error analyzing results.")
        self.assertEqual(past_step["confidence"], 0.0)

if __name__ == '__main__':
    unittest.main()
