"""
Unit tests for Cross-Encoder Reranker
"""

import unittest
import sys
import types

fake_st = types.SimpleNamespace(
    CrossEncoder=lambda *args, **kwargs: types.SimpleNamespace(
        predict=lambda pairs: [0.9 for _ in pairs]
    )
)
sys.modules.setdefault("sentence_transformers", fake_st)
from deep_thinking.reranker import Reranker


class TestReranker(unittest.TestCase):
    """Test cases for the Reranker class"""
    
    @classmethod
    def setUpClass(cls):
        """Initialize reranker once for all tests"""
        cls.reranker = Reranker()
    
    def test_rerank_basic(self):
        """Test basic reranking functionality"""
        query = "What are the side effects of CAR-T therapy?"
        
        documents = [
            {"content": "CAR-T therapy can cause cytokine release syndrome and neurotoxicity."},
            {"content": "The weather today is sunny and warm."},
            {"content": "Side effects of CAR-T include fever, fatigue, and confusion."},
            {"content": "Python is a programming language."},
        ]
        
        reranked = self.reranker.rerank(query, documents, top_k=2)
        
        # Should return 2 documents
        self.assertEqual(len(reranked), 2)
        
        # All should have rerank_score
        for doc in reranked:
            self.assertIn("rerank_score", doc)
            self.assertIsInstance(doc["rerank_score"], float)
        
        # Scores should be in descending order
        self.assertGreaterEqual(reranked[0]["rerank_score"], reranked[1]["rerank_score"])
        
        # Most relevant documents should be about CAR-T side effects
        self.assertIn("CAR-T", reranked[0]["content"])
    
    def test_rerank_empty_documents(self):
        """Test reranking with empty document list"""
        query = "test query"
        documents = []
        
        reranked = self.reranker.rerank(query, documents)
        
        self.assertEqual(len(reranked), 0)
    
    def test_rerank_preserves_metadata(self):
        """Test that reranking preserves document metadata"""
        query = "lymphoma treatment"
        
        documents = [
            {
                "content": "R-CHOP is a chemotherapy regimen for lymphoma.",
                "source": "treatment_notes.md",
                "score": 0.85
            },
            {
                "content": "The sky is blue.",
                "source": "random.md",
                "score": 0.1
            }
        ]
        
        reranked = self.reranker.rerank(query, documents, top_k=2)
        
        # Original metadata should be preserved
        self.assertIn("source", reranked[0])
        self.assertIn("score", reranked[0])
        
        # New rerank_score should be added
        self.assertIn("rerank_score", reranked[0])
    
    def test_rerank_with_threshold(self):
        """Test reranking with relevance threshold"""
        query = "PET scan results"
        
        documents = [
            {"content": "PET scan showed increased FDG uptake in lymph nodes."},
            {"content": "The patient had a PET-CT scan yesterday."},
            {"content": "Unrelated content about gardening."},
        ]
        
        # Use threshold to filter out irrelevant docs
        reranked = self.reranker.rerank_with_threshold(
            query, documents, threshold=0.3, top_k=5
        )
        
        # Should filter out gardening content
        self.assertLessEqual(len(reranked), 2)
        
        # All returned docs should be above threshold
        for doc in reranked:
            self.assertGreaterEqual(doc["rerank_score"], 0.3)
    
    def test_top_k_limit(self):
        """Test that top_k properly limits results"""
        query = "test"
        documents = [{"content": f"Document {i}"} for i in range(10)]
        
        reranked = self.reranker.rerank(query, documents, top_k=3)
        
        self.assertEqual(len(reranked), 3)


if __name__ == '__main__':
    unittest.main()
