import requests
from typing import List, Dict, Any
from .state import Step, RAGState

class RetrievalSupervisor:
    def __init__(self, vector_service_url: str, graph_service_url: str):
        self.vector_service_url = vector_service_url
        self.graph_service_url = graph_service_url
        
    def execute_step(self, step: Step, state: RAGState) -> List[Dict[str, Any]]:
        """
        Execute the search strategy specified in the step.
        """
        query = step["sub_question"]
        strategy = step["search_strategy"]
        
        # Apply Obsidian folder filtering
        filters = self._build_filters(step["target_folders"])
        
        results = []
        
        if strategy == "vector":
            results = self._query_vector(query, filters)
            
        elif strategy == "graph":
            # Use 'local' mode for specific entity questions
            # Graph search typically doesn't support metadata filtering easily in LightRAG yet, 
            # so we might skip it or apply post-filtering if possible. 
            # For now, we pass it but the underlying service might ignore it.
            results = self._query_graph(query, mode="local")
            
        elif strategy == "hybrid":
            # Graph search disabled: LightRAG requires multiple sequential LLM calls
            # Even with Claude, this takes 30+ seconds per query (too slow for Deep Thinking)
            # Deep Thinking works great with vector-only search
            vec_results = self._query_vector(query, filters)
            results = vec_results
            
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
    
    def _query_vector(self, query: str, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        try:
            response = requests.post(
                f'{self.vector_service_url}/query',
                json={
                    "query": query,
                    "n_results": 10,
                    "filters": filters,
                    "reranking": True,
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
