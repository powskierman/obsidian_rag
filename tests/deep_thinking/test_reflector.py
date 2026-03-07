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
        
        self.assertEqual(past_step["key_findings"], "No documents retrieved for this step.")
        self.assertEqual(past_step["confidence"], 0.0)

    def test_reflect_empty_content_falls_back_without_unboundlocalerror(self):
        mock_response = MagicMock()
        mock_response.content = []
        self.mock_client.messages.create.return_value = mock_response

        step = {"step_number": 1, "sub_question": "q"}
        documents = [{"content": "doc1", "source": "s1"}]
        state = {"past_steps": []}

        past_step = self.reflector.reflect(step, documents, state)

        self.assertEqual(past_step["key_findings"], "Retrieved 1 documents. Top sources: s1.")
        self.assertEqual(past_step["confidence"], 0.0)

    def test_compress_context(self):
        # Mock response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='Condensed Summary')]
        self.mock_client.messages.create.return_value = mock_response

        long_text = "This is a very long text that needs to be compressed."
        compressed = self.reflector.compress_context(long_text)
        
        self.assertIn("[COMPRESSED EARLIER STEPS]", compressed)
        self.assertIn("Condensed Summary", compressed)
        self.mock_client.messages.create.assert_called_once()
        
    def test_compress_context_empty(self):
        compressed = self.reflector.compress_context("   ")
        self.assertEqual(compressed, "")

if __name__ == '__main__':
    unittest.main()
