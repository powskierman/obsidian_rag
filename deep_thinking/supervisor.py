import requests
from typing import List, Dict, Any
from .state import Step, RAGState
try:
    from .reranker import Reranker
    RERANKER_AVAILABLE = True
except ImportError:
    RERANKER_AVAILABLE = False
    print("Warning: Reranker not available. Install sentence-transformers to enable reranking.")

import os
try:
    from tavily import TavilyClient
    WEB_SEARCH_AVAILABLE = True
except ImportError:
    WEB_SEARCH_AVAILABLE = False
    print("Warning: tavily-python not available.")

class RetrievalSupervisor:
    def __init__(self, vector_service_url: str, graph_service_url: str, enable_reranking: bool = True):
        self.vector_service_url = vector_service_url
        self.graph_service_url = graph_service_url
        self.enable_reranking = enable_reranking and RERANKER_AVAILABLE
        
        # Initialize reranker if available
        if self.enable_reranking:
            self.reranker = Reranker()
            print("✅ Reranker initialized")
        else:
            self.reranker = None
            if enable_reranking:
                print("⚠️  Reranking disabled (sentence-transformers not installed)")
        
    def execute_step(self, step: Step, state: RAGState) -> List[Dict[str, Any]]:
        """
        Execute the search strategy specified in the step.
        """
        # For vault searches (vector/hybrid), use keywords if available.
        # Keywords have better signal than sub_questions which may include generic words.
        strategy = step["search_strategy"]
        if strategy in ["vector", "hybrid"] and step.get("keywords"):
            # Join keywords for better retrieval
            query = " ".join(step["keywords"])
        else:
            query = step["sub_question"]
        
        # Apply Obsidian folder filtering
        filters = self._build_filters(step["target_folders"])
        
        results = []
        
        if strategy == "vector":
            # Retrieve more results for reranking
            n_results = 10 if self.enable_reranking else 5
            results = self._query_vector(query, filters, n_results=n_results)
            
            # Fallback: If filtered search returns nothing, try without filters
            if not results and filters:
                print(f"⚠️  No results with filters {filters}. Retrying without filters...")
                results = self._query_vector(query, filters=None, n_results=n_results)
            
        elif strategy == "graph":
            # Use 'local' mode for specific entity questions
            results = self._query_graph(query, mode="local")
            
        elif strategy == "hybrid":
            # Graph search disabled: LightRAG requires multiple sequential LLM calls
            # Deep Thinking works great with vector-only search
            n_results = 10 if self.enable_reranking else 5
            vec_results = self._query_vector(query, filters, n_results=n_results)
            
            # Fallback for hybrid (vector part)
            if not vec_results and filters:
                print(f"⚠️  No results with filters {filters}. Retrying without filters...")
                vec_results = self._query_vector(query, filters=None, n_results=n_results)
                
            results = vec_results
            
        elif strategy == "web":
            results = self._query_web(query)
        
        # Apply reranking if enabled
        if self.enable_reranking and results and len(results) > 0:
            results = self.reranker.rerank(query, results, top_k=5)
            
        return results
    
    def _build_filters(self, target_folders: List[str]) -> Dict[str, Any]:
        """Convert Obsidian folder paths to ChromaDB metadata filters."""
        if not target_folders:
            return {}
        
        # If only one folder, simple filter
        if len(target_folders) == 1:
            return {"source": {"$contains": target_folders[0]}}
            
        # If multiple folders, use $or
        return {
            "$or": [{"source": {"$contains": folder}} for folder in target_folders]
        }
    
    def _query_vector(self, query: str, filters: Dict[str, Any] = None, n_results: int = 10) -> List[Dict[str, Any]]:
        try:
            response = requests.post(
                f'{self.vector_service_url}/query',
                json={
                    "query": query,
                    "n_results": n_results,
                    "filters": filters,
                    "reranking": False,  # We do our own reranking
                    "deduplicate": True
                },
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                # Normalize format - embedding service returns documents/metadatas/distances arrays
                normalized = []
                documents = data.get("documents", [[]])[0]
                metadatas = data.get("metadatas", [[]])[0]
                distances = data.get("distances", [[]])[0]
                
                for doc, meta, dist in zip(documents, metadatas, distances):
                    normalized.append({
                        "content": doc,
                        "source": meta.get("filepath", "Unknown"),
                        "type": "vector",
                        "score": float(1 - dist) if dist < 1 else 0.0  # Convert distance to similarity score
                    })
                return normalized
            else:
                print(f"Vector search error: {response.status_code}")
                return []
        except Exception as e:
            print(f"Vector search exception: {e}")
            return []

    def _query_graph(self, query: str, mode: str = "hybrid") -> List[Dict[str, Any]]:
        try:
            response = requests.post(
                f'{self.graph_service_url}/query',
                json={
                    "query": query,
                    "mode": mode,
                    "top_k": 30,
                    "chunk_top_k": 10
                },
                timeout=300  # Increased from 180 to 300 seconds
            )
            if response.status_code == 200:
                data = response.json()
                # LightRAG returns a string response usually, but we might want chunks if available.
                # If the API returns just a string, we wrap it.
                # Assuming standard LightRAG response format.
                # If it returns a string directly:
                if isinstance(data, str):
                     return [{
                        "content": data,
                        "source": "LightRAG Knowledge Graph",
                        "type": "graph",
                        "score": 1.0
                    }]
                # If it returns a dict with response:
                elif isinstance(data, dict) and "response" in data:
                     return [{
                        "content": data["response"],
                        "source": "LightRAG Knowledge Graph",
                        "type": "graph",
                        "score": 1.0
                    }]
                return []
            else:
                print(f"Graph search error: {response.status_code}")
                return []
        except requests.exceptions.Timeout:
            print(f"Graph search timeout after 300s for query: {query[:50]}...")
            # Return empty results instead of crashing
            return []
        except Exception as e:
            print(f"Graph search exception: {e}")
            return []

    def _query_web(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        if not WEB_SEARCH_AVAILABLE:
            print("⚠️ Web search disabled (tavily-python not installed)")
            return []
            
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            print("⚠️ Web search disabled (TAVILY_API_KEY not set)")
            return []

        try:
            print(f"DEBUG: Web Query: {query}")
            tavily_client = TavilyClient(api_key=api_key)
            # Use 'search' method with image support
            response = tavily_client.search(
                query, 
                search_depth="advanced", 
                max_results=n_results,
                include_images=True  # Enable image retrieval
            )
            
            formatted_results = []
            images = response.get('images', [])
            
            if 'results' in response:
                for i, res in enumerate(response['results']):
                    doc = {
                        "content": f"Title: {res['title']}\nSnippet: {res['content']}",
                        "source": res['url'],
                        "type": "web",
                        "score": res.get('score', 1.0)
                    }
                    # Add first 2 images to first result if available
                    if i == 0 and images:
                        doc['images'] = images[:2]
                    formatted_results.append(doc)
            
            # If we got images but no results, log it
            if images and not formatted_results:
                print(f"DEBUG: Found {len(images)} images but no text results")
                
            return formatted_results
        except Exception as e:
            print(f"Web search error: {e}")

            return []
