#!/usr/bin/env python3
import requests
import json
import asyncio
import websockets
import os
import time
from typing import Dict, Any

# Configurations
GATEWAY_URL = "http://localhost:4000"
WS_GATEWAY_URL = "ws://localhost:4000"
OUTPUT_FILE = "Documentation/SEARCH_MODE_AUDIT.md"

# Modes to test defined in user request + api.ts
MODES = [
    "vector",
    "notes", 
    "entities",
    "notes+vector",
    "entities+vector",
    "dual-graph", 
    "hybrid",
    "cascading"
]

TEST_QUERY = "What is the treatment for DLBCL?"  # A known medical query from existing tests

def test_rest_mode(mode: str) -> Dict[str, Any]:
    """Test a REST API mode via the Gateway."""
    url = f"{GATEWAY_URL}/api/v1/query"
    payload = {
        "query": TEST_QUERY,
        "mode": mode,
        "n_results": 3,
        "llm_provider": "ollama", # Use Ollama to avoid burning paid tokens
        "temperature": 0.0
    }
    
    start_time = time.time()
    try:
        response = requests.post(url, json=payload, timeout=60)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            # Try to extract answer length and source count based on varied response structures
            answer = ""
            sources = []
            
            # Handle Gateway V1 Nested Wrapper (e.g. data['results']['documents'])
            if 'results' in data:
                inner = data['results']
                if 'documents' in inner and inner['documents']:
                    # Vector mode raw return
                    sources = inner['documents'][0]
                    answer = "Found snippets" # Dummy answer for vector mode
                elif 'answer' in inner:
                     answer = inner['answer']
                elif 'result' in inner:
                     answer = inner['result']
                
                # If sources are in inner
                if 'sources' in inner:
                    sources = inner['sources']
            
            # Hybrid/Unified flattened structure
            if not answer:
                if 'answer' in data:
                    answer = data['answer']
                elif 'result' in data:
                    answer = data['result']
            
            if not sources and 'sources' in data:
                sources = data['sources']
            
            # Nested structures (e.g. notes.data.answer)
            if not answer and 'notes' in data and data['notes']['data']:
                 answer = data['notes']['data'].get('answer', '')
            
            return {
                "status": "PASS",
                "duration": f"{duration:.2f}s",
                "answer_len": len(answer),
                "source_count": len(sources),
                "details": "OK"
            }
        else:
            return {
                "status": "FAIL", 
                "duration": f"{duration:.2f}s",
                "details": f"HTTP {response.status_code}: {response.text[:100]}"
            }
    except Exception as e:
        return {
            "status": "ERROR",
            "duration": f"{time.time() - start_time:.2f}s",
            "details": str(e)
        }

async def test_deep_thinking() -> Dict[str, Any]:
    """Test the Deep Thinking WebSocket endpoint."""
    uri = f"{WS_GATEWAY_URL}/api/v1/deep-research"
    payload = {
        "query": TEST_QUERY,
        "mode": "deep-thinking",
        "parameters": {
            "max_depth": 1
        }
    }
    
    start_time = time.time()
    try:
        async with websockets.connect(uri) as websocket:
            await websocket.send(json.dumps(payload))
            
            msgs_received = 0
            final_answer_received = False
            
            # Listen for up to 30 seconds
            try:
                while True:
                    msg = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    msgs_received += 1
                    data = json.loads(msg)
                    
                    if data.get("type") == "answer" or data.get("status") == "complete":
                        final_answer_received = True
                        break
                    if data.get("type") == "error":
                        return {
                            "status": "FAIL",
                            "duration": f"{time.time() - start_time:.2f}s", 
                            "details": f"WS Error: {data.get('message')}"
                        }
            except asyncio.TimeoutError:
                pass # Timeout is okay if we got some chunks, but better if we finish
                
            return {
                "status": "PASS" if msgs_received > 0 else "FAIL",
                "duration": f"{time.time() - start_time:.2f}s",
                "answer_len": "Streamed", 
                "source_count": "N/A",
                "details": f"Received {msgs_received} chunks. Final Answer: {final_answer_received}"
            }
            
    except Exception as e:
        return {
            "status": "ERROR",
            "duration": f"{time.time() - start_time:.2f}s",
            "details": str(e)
        }

def run_audit():
    print(f"Starting Search Mode Audit against {GATEWAY_URL}...")
    print(f"Test Query: {TEST_QUERY}\n")
    
    results = {}
    
    # 1. Test REST Modes
    for mode in MODES:
        print(f"Testing mode: {mode}...", end="", flush=True)
        res = test_rest_mode(mode)
        results[mode] = res
        print(f" {res['status']}")
        
    # 2. Test Deep Thinking (Async)
    print(f"Testing mode: deep-thinking...", end="", flush=True)
    dt_res = asyncio.run(test_deep_thinking())
    results["deep-thinking"] = dt_res
    print(f" {dt_res['status']}")
    
    # 3. Generate Report
    generate_report(results)

def generate_report(results: Dict[str, Any]):
    with open(OUTPUT_FILE, "w") as f:
        f.write("# Search Mode Audit Report\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Query used:** `{TEST_QUERY}`\n\n")
        
        f.write("| Mode | Status | Duration | Answer Len | Sources | Details |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        
        for mode, res in results.items():
            f.write(f"| **{mode}** | {res['status']} | {res.get('duration','-')} | {res.get('answer_len','-')} | {res.get('source_count','-')} | {res.get('details','')} |\n")
            
    print(f"\nReport saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    run_audit()
