import os
import httpx
import json
import asyncio
import anthropic
import uvicorn
from fastapi import FastAPI, WebSocket, Request, HTTPException, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor

# Import CascadingRetriever - handle both package and direct execution
try:
    from cascading_retriever import CascadingRetriever
except ImportError:
    from src.services.cascading_retriever import CascadingRetriever


def _load_deep_thinking_rag():
    """Lazy-load DeepThinkingRAG to avoid heavy ML imports during test collection."""
    try:
        from deep_thinking.orchestrator import DeepThinkingRAG
        return DeepThinkingRAG
    except ImportError:
        import sys
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        sys.path.append(base_path)
        sys.path.append(base_path)
        from deep_thinking.orchestrator import DeepThinkingRAG
        return DeepThinkingRAG

app = FastAPI(title="Obsidian RAG Unified API", version="1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
GRAPH_SERVICE_URL = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8002")
LIGHTRAG_SERVICE_URL = os.getenv("LIGHTRAG_SERVICE_URL", "http://localhost:8001")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# thread pool for running synchronous Deep Thinking agents
executor = ThreadPoolExecutor(max_workers=5)

class SearchRequest(BaseModel):
    query: str
    mode: str = "hybrid"  # vector, graph, hybrid
    n_results: int = 10
    llm_provider: str = "kimi"
    model: Optional[str] = None
    temperature: float = 0.0
    system_prompt: Optional[str] = None
    web_search: bool = False
    llm_knowledge: bool = False
    reranking: bool = True
    deduplicate: bool = True

@app.get("/api/v1/health")
async def health_check():
    """Aggregated health check with stats"""
    emb_data = {}
    graph_data = {}
    lightrag_data = {}

    try:
        async with httpx.AsyncClient() as client:
            emb_resp = await client.get(f"{EMBEDDING_SERVICE_URL}/health", timeout=2.0)
            if emb_resp.status_code == 200:
                emb_data = emb_resp.json()
                emb_status = "healthy"
            else:
                emb_status = "unhealthy"
    except:
        emb_status = "unreachable"

    try:
        async with httpx.AsyncClient() as client:
            graph_resp = await client.get(f"{GRAPH_SERVICE_URL}/health", timeout=2.0)
            if graph_resp.status_code == 200:
                graph_data = graph_resp.json()
                graph_status = "healthy"
            else:
                graph_status = "unhealthy"
    except:
        graph_status = "unreachable"

    try:
        async with httpx.AsyncClient() as client:
            lightrag_resp = await client.get(f"{LIGHTRAG_SERVICE_URL}/health", timeout=2.0)
            if lightrag_resp.status_code == 200:
                lightrag_data = lightrag_resp.json()
                lightrag_status = "healthy"
            else:
                lightrag_status = "unhealthy"
    except:
        lightrag_status = "unreachable"

    # Get LightRAG stats
    try:
        async with httpx.AsyncClient() as client:
            stats_resp = await client.get(f"{LIGHTRAG_SERVICE_URL}/stats", timeout=2.0)
            if stats_resp.status_code == 200:
                lightrag_stats = stats_resp.json()
                lightrag_data.update(lightrag_stats)
    except:
        pass

    return {
        "success": True,
        "data": {
            "gateway": "healthy",
            "services": {
                "embedding": {
                    "status": emb_status,
                    "url": EMBEDDING_SERVICE_URL,
                    "count": emb_data.get("documents", 0) or emb_data.get("count", 0) # Handle various response formats
                },
                "networkx": {
                    "status": graph_status,
                    "url": GRAPH_SERVICE_URL,
                    "nodes": graph_data.get("nodes", 0),
                    "edges": graph_data.get("edges", 0)
                },
                "lightrag": {
                    "status": lightrag_status,
                    "url": LIGHTRAG_SERVICE_URL,
                    "nodes": lightrag_data.get("graph_nodes", 0),
                    "edges": lightrag_data.get("graph_edges", 0),
                    "indexed_notes": lightrag_data.get("indexed_notes", 0)
                }
            },
        }
    }
@app.get("/api/v1/stats")
async def get_stats():
    """Get aggregated stats for UI"""
    health_data = await health_check()
    services = health_data.get("data", {}).get("services", {})

    return {
        "documents": services.get("embedding", {}).get("count", 0),
        "graph": {
            "nodes": services.get("networkx", {}).get("nodes", 0),
            "edges": services.get("networkx", {}).get("edges", 0)
        }
    }
@app.post("/api/v1/search")
async def unified_search(request: SearchRequest):
    """Unified search endpoint acting as a proxy/router"""
    mode = request.mode.lower()
    
    # 1. Vector Only -> Embedding Service
    if mode == "vector":
        async with httpx.AsyncClient() as client:
            try:
                # Embedding service expects keys: query, n_results
                payload = {
                    "query": request.query,
                    "n_results": request.n_results
                }
                response = await client.post(f"{EMBEDDING_SERVICE_URL}/query", json=payload, timeout=30.0)
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                raise HTTPException(status_code=503, detail=f"Embedding service unreachable: {str(e)}")

    # 2. Graph / Hybrid -> Graph Service
    else:
        async with httpx.AsyncClient() as client:
            try:
                # Graph service expects robust payload
                payload = request.model_dump()
                response = await client.post(f"{GRAPH_SERVICE_URL}/query", json=payload, timeout=120.0)
                response.raise_for_status()
                return response.json()
            except httpx.RequestError as e:
                raise HTTPException(status_code=503, detail=f"Graph service unreachable: {str(e)}")

class UnifiedQueryRequest(BaseModel):
    query: str
    mode: str = "hybrid"  # networkx, lightrag, hybrid
    max_results: int = 10
    llm_provider: str = "ollama"
    model: Optional[str] = None
    temperature: float = 0.7
    relevance_threshold: float = 0  # 0-100%, 0 = show all results
    distance_threshold: Optional[float] = None  # Legacy support (deprecated)
    system_prompt: Optional[str] = None

@app.post("/api/v1/query")
async def unified_query(request: UnifiedQueryRequest):
    """
    Enhanced unified query endpoint with multiple knowledge source modes

    Single-source modes:
    - vector: Pure vector similarity (ChromaDB, 7k chunks)
    - notes (or networkx): Note-centric graph with wiki-links (16k nodes)
    - entities (or lightrag): Entity-centric semantic graph (2k notes)

    Dual-source modes:
    - notes+vector: NetworkX graph + ChromaDB vectors
    - entities+vector: LightRAG graph + ChromaDB vectors
    - dual-graph: Both graphs (NetworkX + LightRAG)

    Ultimate mode:
    - hybrid: All three sources (Vector + Notes + Entities) - RECOMMENDED
    """
    mode = request.mode.lower()

    # Normalize mode aliases
    mode_aliases = {
        "networkx": "notes",
        "lightrag": "entities"
    }
    mode = mode_aliases.get(mode, mode)
    print(f"DEBUG: Unified query incoming mode: {mode}")
    effective_relevance_threshold = request.relevance_threshold
    if effective_relevance_threshold == 0 and request.distance_threshold is not None:
        import math
        effective_relevance_threshold = 100 / (1 + math.exp(request.distance_threshold / 2))
        effective_relevance_threshold = max(0.0, min(100.0, effective_relevance_threshold))
    print(f"🎯 API Gateway received relevance_threshold: {effective_relevance_threshold}%")

    # ===== CASCADING RETRIEVAL MODE =====
    if mode == "cascading":
        try:
            api_key = None
            if request.llm_provider == "anthropic":
                api_key = ANTHROPIC_API_KEY

            retriever = CascadingRetriever(
                embed_url=EMBEDDING_SERVICE_URL,
                graph_url=GRAPH_SERVICE_URL,
                lightrag_url=LIGHTRAG_SERVICE_URL,
                llm_provider=request.llm_provider,
                api_key=api_key
            )

            result = await retriever.retrieve(request.query, max_results=request.max_results)

            return {
                "query": request.query,
                "mode": "cascading",
                "results": result,
                "metadata": {
                    "description": "5-Stage Cascading Retrieval (Anchor -> Entity -> Expand -> Vector -> Synthesis)",
                    "stages": ["Note Discovery", "Entity Extraction", "Semantic Expansion", "Vector Search"]
                }
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Cascading retrieval error: {str(e)}")

    async with httpx.AsyncClient() as client:

        # ===== SINGLE-SOURCE MODES =====

        # Pure vector search
        if mode == "vector":
            try:
                payload = {"query": request.query, "n_results": request.max_results, "relevance_threshold": effective_relevance_threshold}
                response = await client.post(f"{EMBEDDING_SERVICE_URL}/query", json=payload, timeout=30.0)
                response.raise_for_status()
                result = response.json()

                return {
                    "query": request.query,
                    "mode": "vector",
                    "results": result,
                    "metadata": {
                        "source": "ChromaDB Vectors",
                        "description": "Pure vector similarity search across 7,102 document chunks"
                    }
                }
            except Exception as e:
                raise HTTPException(status_code=503, detail=f"Vector service error: {str(e)}")

        # NetworkX notes graph
        elif mode == "notes":
            try:
                payload = {
                    "query": request.query,
                    "mode": "graph",
                    "n_results": request.max_results,
                    "use_vector": True,
                    "llm_provider": request.llm_provider,
                    "model": request.model,
                    "temperature": request.temperature,
                    "system_prompt": request.system_prompt
                }
                response = await client.post(f"{GRAPH_SERVICE_URL}/query", json=payload, timeout=120.0)
                response.raise_for_status()
                result = response.json()

                return {
                    "query": request.query,
                    "mode": "notes",
                    "results": result,
                    "metadata": {
                        "source": "NetworkX Graph",
                        "description": "Note-centric graph with wiki-link relationships (16,212 nodes, 16,268 edges)"
                    }
                }
            except Exception as e:
                raise HTTPException(status_code=503, detail=f"Notes graph error: {str(e)}")

        # LightRAG entities graph
        elif mode == "entities":
            try:
                payload = {
                    "query": request.query,
                    "mode": "hybrid",
                    "llm_provider": request.llm_provider,
                    "model": request.model,
                    "temperature": request.temperature,
                    "system_prompt": request.system_prompt
                }
                response = await client.post(f"{LIGHTRAG_SERVICE_URL}/query", json=payload, timeout=60.0)
                response.raise_for_status()
                result = response.json()

                return {
                    "query": request.query,
                    "mode": "entities",
                    "results": result,
                    "metadata": {
                        "source": "LightRAG Graph",
                        "description": "Entity-centric semantic graph (2,000 indexed notes)"
                    }
                }
            except Exception as e:
                raise HTTPException(status_code=503, detail=f"Entities graph error: {str(e)}")

        # ===== DUAL-SOURCE MODES =====

        # Notes + Vector
        elif mode == "notes+vector":
            try:
                tasks = [
                    client.post(f"{GRAPH_SERVICE_URL}/query", json={
                        "query": request.query,
                        "mode": "hybrid",
                        "n_results": request.max_results,
                        "use_vector": True,
                        "llm_provider": request.llm_provider,
                        "model": request.model,
                        "temperature": request.temperature,
                        "system_prompt": request.system_prompt
                    }, timeout=120.0),
                    client.post(f"{EMBEDDING_SERVICE_URL}/query", json={
                        "query": request.query, "n_results": request.max_results, "relevance_threshold": effective_relevance_threshold
                    }, timeout=30.0)
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

                notes_result = None if isinstance(responses[0], Exception) else responses[0].json()
                vector_result = None if isinstance(responses[1], Exception) else responses[1].json()

                return {
                    "query": request.query,
                    "mode": "notes+vector",
                    "notes": {"available": notes_result is not None, "data": notes_result},
                    "vector": {"available": vector_result is not None, "data": vector_result},
                    "metadata": {"description": "Combined NetworkX graph + ChromaDB vectors"}
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Notes+Vector error: {str(e)}")

        # Entities + Vector
        elif mode == "entities+vector":
            try:
                tasks = [
                    client.post(f"{LIGHTRAG_SERVICE_URL}/query", json={
                        "query": request.query,
                        "mode": "hybrid",
                        "llm_provider": request.llm_provider,
                        "model": request.model,
                        "temperature": request.temperature,
                        "system_prompt": request.system_prompt
                    }, timeout=60.0),
                    client.post(f"{EMBEDDING_SERVICE_URL}/query", json={
                        "query": request.query, "n_results": request.max_results, "relevance_threshold": effective_relevance_threshold
                    }, timeout=30.0)
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

                entities_result = None if isinstance(responses[0], Exception) else responses[0].json()
                vector_result = None if isinstance(responses[1], Exception) else responses[1].json()

                return {
                    "query": request.query,
                    "mode": "entities+vector",
                    "entities": {"available": entities_result is not None, "data": entities_result},
                    "vector": {"available": vector_result is not None, "data": vector_result},
                    "metadata": {"description": "Combined LightRAG graph + ChromaDB vectors"}
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Entities+Vector error: {str(e)}")

        # Dual-Graph (both graphs, no vectors)
        elif mode == "dual-graph":
            try:
                tasks = [
                    client.post(f"{GRAPH_SERVICE_URL}/query", json={
                        "query": request.query,
                        "mode": "hybrid",
                        "n_results": request.max_results,
                        "use_vector": True,
                        "llm_provider": request.llm_provider,
                        "model": request.model,
                        "temperature": request.temperature,
                        "system_prompt": request.system_prompt
                    }, timeout=120.0),
                    client.post(f"{LIGHTRAG_SERVICE_URL}/query", json={
                        "query": request.query,
                        "mode": "hybrid",
                        "llm_provider": request.llm_provider,
                        "model": request.model,
                        "temperature": request.temperature,
                        "system_prompt": request.system_prompt
                    }, timeout=60.0)
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

                notes_result = None if isinstance(responses[0], Exception) else responses[0].json()
                entities_result = None if isinstance(responses[1], Exception) else responses[1].json()

                return {
                    "query": request.query,
                    "mode": "dual-graph",
                    "notes": {"available": notes_result is not None, "data": notes_result},
                    "entities": {"available": entities_result is not None, "data": entities_result},
                    "metadata": {"description": "Combined NetworkX + LightRAG graphs"}
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Dual-graph error: {str(e)}")

        # ===== ULTIMATE HYBRID MODE =====

        # Hybrid: All three sources
        # Hybrid: All three sources
        elif mode == "hybrid":
            try:
                tasks = [
                    client.post(f"{GRAPH_SERVICE_URL}/query", json={
                        "query": request.query,
                        "mode": "hybrid",
                        "n_results": request.max_results,
                        "use_vector": True,
                        "llm_provider": request.llm_provider,
                        "model": request.model,
                        "temperature": request.temperature,
                        "system_prompt": request.system_prompt
                    }, timeout=90.0),
                    client.post(f"{LIGHTRAG_SERVICE_URL}/query", json={
                        "query": request.query,
                        "mode": "hybrid",
                        "llm_provider": request.llm_provider,
                        "model": request.model,
                        "temperature": request.temperature,
                        "system_prompt": request.system_prompt
                    }, timeout=90.0),
                    client.post(f"{EMBEDDING_SERVICE_URL}/query", json={
                        "query": request.query, "n_results": request.max_results, "relevance_threshold": effective_relevance_threshold
                    }, timeout=30.0)
                ]
                responses = await asyncio.gather(*tasks, return_exceptions=True)

                notes_result = None if isinstance(responses[0], Exception) else responses[0].json()
                entities_result = None if isinstance(responses[1], Exception) else responses[1].json()
                vector_result = None if isinstance(responses[2], Exception) else responses[2].json()

                return {
                    "query": request.query,
                    "mode": "hybrid",
                    "notes": {"available": notes_result is not None, "data": notes_result},
                    "entities": {"available": entities_result is not None, "data": entities_result},
                    "vector": {"available": vector_result is not None, "data": vector_result},
                    "metadata": {
                        "description": "Ultimate hybrid: All 3 sources (Vector + Notes + Entities)",
                        "sources": {
                            "vector": "ChromaDB (7,102 chunks)",
                            "notes": "NetworkX Graph (16,212 nodes)",
                            "entities": "LightRAG Graph (2,000 notes)"
                        }
                    }
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Hybrid query error: {str(e)}")

@app.websocket("/api/v1/deep-research")
async def deep_research_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for Deep Thinking Agent.
    Client sends JSON: {"query": "..."}
    Server streams messages: 
      {"type": "log", "content": "..."}
      {"type": "status", "content": "🤔 Planning..."} 
      {"type": "answer", "data": {...}}
    """
    await websocket.accept()
    
    try:
        data = await websocket.receive_json()
        query = data.get("query")
        provider = data.get("provider", "claude").lower()
        
        if not query:
            await websocket.send_json({"type": "error", "content": "No query provided"})
            return

        # Determine API Key based on provider
        api_key = None
        if provider == "claude":
            api_key = ANTHROPIC_API_KEY
            if not api_key:
                await websocket.send_json({"type": "error", "content": "ANTHROPIC_API_KEY not configured"})
                await websocket.close()
                return
        elif provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                await websocket.send_json({"type": "error", "content": "GEMINI_API_KEY not configured"})
                await websocket.close()
                return

        # Initialize Agent with Universal Client
        # Note: We must use the INTERNAL Docker URLs here
        DeepThinkingRAG = _load_deep_thinking_rag()
        rag = DeepThinkingRAG(
            provider=provider,
            api_key=api_key,
            vector_service_url=EMBEDDING_SERVICE_URL,
            graph_service_url=GRAPH_SERVICE_URL,
            enable_reranking=True
        )

        # Define synchronous callback to run in thread
        def status_callback(msg, details=None):
            # We can't await here, so we run a coroutine in the main event loop
            # But making it thread-safe is tricky.
            # Simplified: formatting the message and putting it in a queue, or just printing?
            # Ideally we want to send to websocket.
            
            # Since this runs in a thread, we need to schedule the send on the loop
            loop = asyncio.new_event_loop() 
            # Wait, creating a new loop is risky. 
            # Better approach: The callback is run in the thread. 
            # We can use asyncio.run_coroutine_threadsafe if we have reference to the loop.
            pass

        # Actually, let's redefine this to run nicely with FastAPI's event loop
        loop = asyncio.get_running_loop()

        def sync_callback(msg, details=None):
            payload = {
                "type": "log", 
                "message": msg, 
                "details": details
            }
            # Schedule sending the message on the main loop
            asyncio.run_coroutine_threadsafe(websocket.send_json(payload), loop)

        # Run the heavy blocking function in a thread pool
        def run_agent():
            return rag.query(query, status_callback=sync_callback)

        await websocket.send_json({"type": "status", "content": "Agent started"})
        
        # Execute in thread
        result = await asyncio.get_running_loop().run_in_executor(executor, run_agent)
        
        # Send final result
        await websocket.send_json({
            "type": "result",
            "data": result
        })
        
        await websocket.close()

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"Error: {e}")
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
            await websocket.close(code=1011)
        except:
            pass

if __name__ == "__main__":
    uvicorn.run("api_gateway:app", host="0.0.0.0", port=3000, reload=True)
