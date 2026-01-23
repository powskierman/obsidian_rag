import urllib.request
import json
import time
import sys

BASE_URL = "http://localhost:4000/api/v1/query"

TEST_CASES = [
    {
        "mode": "vector",
        "query": "What were the findings of the 1st PET-CT scan?",
        "desc": "Vector: Content Retrieval (Target: 1st PET-CT scan.md)"
    },
    {
        "mode": "notes",
        "query": "What is Double-hit Lymphoma?",
        "desc": "Notes: Graph Definition (Target: Node Description & Connections)"
    },
    {
        "mode": "entities",
        "query": "List key concepts related to Lymphoma Treatment.",
        "desc": "Entities: High-Level Concepts (Target: LightRAG Entities)"
    },
    {
        "mode": "hybrid",
        "query": "Summarize the progression of my Lymphoma based on scan reports.",
        "desc": "Hybrid: Synthesis (Combines Scan Docs + Treatment Timeline)"
    },
    {
        "mode": "entities+vector",
        "query": "Explain the Obsidian RAG architecture and query modes.",
        "desc": "Entities+Vector: Tech Docs (Combines Documentation + Architecture Nodes)"
    }
]

def run_test():
    print(f"{'MODE':<20} | {'STATUS':<10} | {'TIME (s)':<10} | {'RESPONSE SNIPPET'}")
    print("-" * 100)

    for test in TEST_CASES:
        payload = json.dumps({
            "query": test["query"],
            "mode": test["mode"],
            "llm_provider": "gemini" 
        }).encode('utf-8')
        
        req = urllib.request.Request(
            BASE_URL, 
            data=payload, 
            headers={'Content-Type': 'application/json'}
        )
        
        start_time = time.time()
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                elapsed = time.time() - start_time
                data = json.loads(response.read().decode('utf-8'))
                
                # Extract answer logic
                answer = ""
                # Flatten the check for keys
                if "result" in data:
                    res = data["result"]
                    if isinstance(res, dict):
                        answer = str(res.get("result") or res.get("answer") or "")
                    else:
                        answer = str(res)
                elif "answer" in data:
                    answer = str(data["answer"])
                
                # Handle complicated Unified Gateway returns
                # Sometimes it returns { "vector": { "data": ... } }
                if not answer:
                    for key in ["vector", "notes", "entities"]:
                        if key in data and data[key] and "data" in data[key]:
                             inner = data[key]["data"]
                             if isinstance(inner, dict):
                                 answer = inner.get("result") or inner.get("answer") or ""
                                 if answer: break
                
                # Fallback
                if not answer:
                    answer = str(data)[:100]

                snippet = (answer[:60] + "...") if len(answer) > 60 else answer
                snippet = snippet.replace("\n", " ")
                
                print(f"{test['mode']:<20} | PASS       | {elapsed:.2f}       | {snippet}")

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"{test['mode']:<20} | ERROR      | {elapsed:.2f}       | {str(e)[:40]}")

if __name__ == "__main__":
    run_test()
