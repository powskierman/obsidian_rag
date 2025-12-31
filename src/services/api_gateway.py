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

# Import Deep Thinking modules
# Note: In Docker, we copy deep_thinking/ to root so import is direct
# But locally it might be deep_thinking.orchestrator
try:
    from deep_thinking.orchestrator import DeepThinkingRAG
except ImportError:
    # Fallback for local dev if in src/services
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from deep_thinking.orchestrator import DeepThinkingRAG

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
                "graph": {
                    "status": graph_status, 
                    "url": GRAPH_SERVICE_URL,
                    "nodes": graph_data.get("nodes", 0),
                    "edges": graph_data.get("edges", 0)
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
            "nodes": services.get("graph", {}).get("nodes", 0),
            "edges": services.get("graph", {}).get("edges", 0)
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
    
    if not ANTHROPIC_API_KEY:
        await websocket.send_json({"type": "error", "content": "ANTHROPIC_API_KEY not set"})
        await websocket.close()
        return

    try:
        data = await websocket.receive_json()
        query = data.get("query")
        if not query:
            await websocket.send_json({"type": "error", "content": "No query provided"})
            return

        # Initialize Agent
        # Note: We must use the INTERNAL Docker URLs here
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        rag = DeepThinkingRAG(
            anthropic_client=client,
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
