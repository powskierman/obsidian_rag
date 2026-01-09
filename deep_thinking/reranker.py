"""
Cross-Encoder Reranker for Deep Thinking RAG
Improves retrieval precision by reranking documents based on query-document relevance.
"""

from typing import List, Dict, Any
from sentence_transformers import CrossEncoder


class Reranker:
    """
    Reranks retrieved documents using a cross-encoder model.
    
    Cross-encoders process query-document pairs jointly, capturing
    nuanced semantic relationships better than bi-encoders.
    """
    
    
    # Cache models to avoid reloading on every request/instance
    _model_cache = {}

    def __init__(self, model_name: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'):
        """
        Initialize the reranker with a cross-encoder model.
        
        Args:
            model_name: HuggingFace model name. Default is a fast, accurate model
                       trained on MS MARCO passage ranking dataset.
        """
        if model_name not in self._model_cache:
            print(f"Loading Reranker model: {model_name}...")
            self._model_cache[model_name] = CrossEncoder(model_name)
        
        self.model = self._model_cache[model_name]
        self.model_name = model_name
        
    def rerank(
        self, 
        query: str, 
        documents: List[Dict[str, Any]], 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents by relevance to query.
        
        Args:
            query: The search query
            documents: List of document dicts with 'content' field
            top_k: Number of top documents to return
            
        Returns:
            List of reranked documents with added 'rerank_score' field,
            sorted by relevance (highest first)
        """
        if not documents:
            return []
        
        # Prepare query-document pairs for cross-encoder
        pairs = [(query, doc.get("content", "")) for doc in documents]
        
        # Score all pairs (returns numpy array)
        scores = self.model.predict(pairs)
        
        # Add scores to documents and sort
        scored_docs = [
            {**doc, "rerank_score": float(score)}
            for doc, score in zip(documents, scores)
        ]
        
        # Sort by rerank score (descending) and return top_k
        scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
        
        return scored_docs[:top_k]
    
    def rerank_with_threshold(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        threshold: float = 0.5,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents and filter by minimum relevance threshold.
        
        Args:
            query: The search query
            documents: List of document dicts
            threshold: Minimum rerank score (0-1) to include document
            top_k: Maximum number of documents to return
            
        Returns:
            List of reranked documents above threshold, up to top_k
        """
        reranked = self.rerank(query, documents, top_k=len(documents))
        
        # Filter by threshold and limit to top_k
        filtered = [doc for doc in reranked if doc["rerank_score"] >= threshold]
        
        return filtered[:top_k]
