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
        
    def execute_step(self, step: Step, state: RAGState, trace_callback=None) -> List[Dict[str, Any]]:
        """
        Execute the search strategy specified in the step.
        """
        def trace(message: str, details: Dict[str, Any] | None = None) -> None:
            line = f"{message}"
            if details:
                line = f"{line} {details}"
            print(line)
            if trace_callback:
                trace_callback(message, details)

        def summarize(results: List[Dict[str, Any]], limit: int = 3) -> Dict[str, Any]:
            sample = []
            for item in results[:limit]:
                sample.append({
                    "source": item.get("source"),
                    "type": item.get("type"),
                    "score": round(float(item.get("score", 0.0)), 4)
                })
            return {"count": len(results), "sample": sample}

        # For vault searches (vector/hybrid), use keywords if available.
        # Keywords have better signal than sub_questions which may include generic words.
        strategy = step["search_strategy"]
        if strategy in ["vector", "hybrid"]:
            query = step["sub_question"]
            if step.get("keywords"):
                query = f"{query} {' '.join(step['keywords'])}"
            original_question = state.get("original_question", "")
            if original_question and original_question.lower() not in query.lower():
                query = f"{query} {original_question}"
        else:
            query = step["sub_question"]
        
        # Apply Obsidian folder filtering
        filters = self._build_filters(step["target_folders"])
        
        results = []
        min_results = 3
        debug_prefix = f"[DeepThinking] Step {step.get('step_number', '?')}"
        
        if strategy == "vector":
            # Retrieve more results for reranking
            n_results = 60 if self.enable_reranking else 20
            trace(
                f"{debug_prefix} vector query",
                {"query": query, "filters": filters or None, "n_results": n_results}
            )
            results = self._query_vector(query, filters, n_results=n_results, trace_callback=trace)
            trace(f"{debug_prefix} vector output", summarize(results))
            
            # Fallback: If filtered search returns too few, try without filters
            if filters and len(results) < min_results:
                trace(
                    f"{debug_prefix} vector retry without filters",
                    {"reason": "too_few_results", "count": len(results)}
                )
                results = self._query_vector(query, filters=None, n_results=n_results, trace_callback=trace)
                trace(f"{debug_prefix} vector retry output", summarize(results))
            
        elif strategy == "graph":
            # Use 'local' mode for specific entity questions
            results = self._query_graph(query, mode="local", trace_callback=trace)
            trace(f"{debug_prefix} graph output", summarize(results))
            
        elif strategy == "hybrid":
            # True Hybrid: Combine Graph and Vector results
            n_results = 60 if self.enable_reranking else 25
            trace(
                f"{debug_prefix} hybrid query",
                {"query": query, "filters": filters or None, "n_results": n_results}
            )
            vec_results = self._query_vector(query, filters, n_results=n_results, trace_callback=trace)
            graph_results = self._query_graph(query, mode="hybrid", trace_callback=trace)
            
            # Combine results
            results = vec_results + graph_results
            trace(
                f"{debug_prefix} hybrid output",
                {
                    "vector": summarize(vec_results),
                    "graph": summarize(graph_results),
                    "total": len(results)
                }
            )
            
            # Fallback: If filtered vector search returns too few, retry without filters
            if filters and len(vec_results) < min_results:
                trace(
                    f"{debug_prefix} hybrid retry without filters",
                    {"reason": "too_few_vector_results", "vector_count": len(vec_results)}
                )
                vec_results = self._query_vector(query, filters=None, n_results=n_results, trace_callback=trace)
                results = vec_results + graph_results
                trace(
                    f"{debug_prefix} hybrid retry output",
                    {"vector": summarize(vec_results), "total": len(results)}
                )
            
        elif strategy == "web":
            results = self._query_web(query, trace_callback=trace)
            trace(f"{debug_prefix} web output", summarize(results))
        
        # Apply reranking if enabled
        if self.enable_reranking and results and len(results) > 0:
            results = self.reranker.rerank(query, results, top_k=20)
            trace(f"{debug_prefix} reranked output", summarize(results))
            
        return results
    
    def _build_filters(self, target_folders: List[str]) -> Dict[str, Any]:
        """Convert Obsidian folder paths to ChromaDB metadata filters."""
        if not target_folders:
            return {}

        def folder_filter(folder_path: str) -> Dict[str, Any]:
            parts = [part for part in folder_path.replace("\\", "/").split("/") if part]
            if not parts:
                return {}
            if len(parts) == 1:
                return {f"dir_{parts[0]}": True}
            return {"$and": [{f"dir_{part}": True} for part in parts]}

        filters = [folder_filter(folder) for folder in target_folders]
        filters = [flt for flt in filters if flt]
        if not filters:
            return {}
        if len(filters) == 1:
            return filters[0]
        return {"$or": filters}
    
    def _query_vector(
        self,
        query: str,
        filters: Dict[str, Any] = None,
        n_results: int = 10,
        trace_callback=None
    ) -> List[Dict[str, Any]]:
        def trace(message: str, details: Dict[str, Any] | None = None) -> None:
            line = f"{message}"
            if details:
                line = f"{line} {details}"
            print(line)
            if trace_callback:
                trace_callback(message, details)

        try:
            trace("[DeepThinking] vector request", {"query": query, "filters": filters, "n_results": n_results})
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
                trace("[DeepThinking] vector response", {"status": response.status_code, "count": len(normalized)})
                return normalized
            else:
                error_body = response.text[:500] if response.text else ""
                trace(
                    "[DeepThinking] vector error",
                    {"status": response.status_code, "body": error_body}
                )
                return []
        except Exception as e:
            trace("[DeepThinking] vector exception", {"error": str(e)})
            return []

    def _query_graph(
        self,
        query: str,
        mode: str = "hybrid",
        trace_callback=None
    ) -> List[Dict[str, Any]]:
        def trace(message: str, details: Dict[str, Any] | None = None) -> None:
            line = f"{message}"
            if details:
                line = f"{line} {details}"
            print(line)
            if trace_callback:
                trace_callback(message, details)

        try:
            trace("[DeepThinking] graph request", {"query": query, "mode": mode})
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
                     results = [{
                        "content": data,
                        "source": "LightRAG Knowledge Graph",
                        "type": "graph",
                        "score": 1.0
                    }]
                     trace("[DeepThinking] graph response", {"status": response.status_code, "count": len(results)})
                     return results
                # If it returns a dict with response or answer (graph-service uses answer):
                elif isinstance(data, dict):
                    content = data.get("answer") or data.get("response")
                    if content:
                        results = [{
                            "content": content,
                            "source": "Knowledge Graph",
                            "type": "graph",
                            "score": 1.0
                        }]
                        trace("[DeepThinking] graph response", {"status": response.status_code, "count": len(results)})
                        return results
                return []
            else:
                error_body = response.text[:500] if response.text else ""
                trace(
                    "[DeepThinking] graph error",
                    {"status": response.status_code, "body": error_body}
                )
                return []
        except requests.exceptions.Timeout:
            trace(
                "[DeepThinking] graph timeout",
                {"query": f"{query[:50]}..."}
            )
            # Return empty results instead of crashing
            return []
        except Exception as e:
            trace("[DeepThinking] graph exception", {"error": str(e)})
            return []

    def _query_web(self, query: str, n_results: int = 5, trace_callback=None) -> List[Dict[str, Any]]:
        def trace(message: str, details: Dict[str, Any] | None = None) -> None:
            line = f"{message}"
            if details:
                line = f"{line} {details}"
            print(line)
            if trace_callback:
                trace_callback(message, details)

        if not WEB_SEARCH_AVAILABLE:
            trace("[DeepThinking] web disabled", {"reason": "tavily-python not installed"})
            return []
            
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            trace("[DeepThinking] web disabled", {"reason": "TAVILY_API_KEY not set"})
            return []

        try:
            trace("[DeepThinking] web request", {"query": query, "n_results": n_results})
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
                trace("[DeepThinking] web no text results", {"images": len(images)})

            trace("[DeepThinking] web response", {"count": len(formatted_results)})
            return formatted_results
        except Exception as e:
            trace("[DeepThinking] web error", {"error": str(e)})

            return []
