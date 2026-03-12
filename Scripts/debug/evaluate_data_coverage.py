#!/usr/bin/env python3
import requests
import json
import time
import statistics
from typing import Dict, Any, List

# Configuration
GATEWAY_URL = "http://localhost:4000/api/v1/query"
OUTPUT_FILE = "Documentation/operations/quality/DATA_COVERAGE_REPORT.md"

# Test Topics
TOPICS = [
    "lymphoma",       # Medical
    "esp32",          # Tech / IoT
    "calculus",       # Math / Academic
    "bread",          # Random / Cooking (control group?)
    "3d printing"     # DIY / Tech
]

# Supported REST modes
MODES = ["vector", "cascading"]

def query_gateway(topic: str, mode: str) -> Dict[str, Any]:
    """Query the gateway and return standardized stats."""
    payload = {
        "query": f"Tell me about {topic}",
        "mode": mode,
        "n_results": 10,
        "llm_provider": "ollama", # Cheap/Free
        "temperature": 0.0
    }
    
    try:
        response = requests.post(GATEWAY_URL, json=payload, timeout=60)
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "count": 0}
            
        data = response.json()
        sources = []
        
        # Parse Sources based on mode schema (using learnings from previous audit)
        if mode == "vector":
            # Vector returns {results: {documents: [[]], metadatas: [[]], ...}}
            if "results" in data:
                inner = data["results"]
                if "metadatas" in inner and inner["metadatas"]:
                     # Flatten the first batch
                     sources = inner["metadatas"][0]
        else:
            # Cascading returns {sources: [...]}
            sources = data.get("sources", [])
            
        # Analyze sources
        count = len(sources)
        filenames = []
        
        # Extract unique filenames to see breadth
        seen_files = set()
        for s in sources:
            # Vector metadata uses 'filename', Graph sources use 'filename'
            fname = s.get("filename", "unknown")
            if fname not in seen_files:
                filenames.append(fname)
                seen_files.add(fname)
                
        return {
            "count": count,
            "unique_files": len(filenames),
            "top_files": filenames[:3], # Show top 3 files found
            "error": None
        }
        
    except Exception as e:
        return {"error": str(e), "count": 0}

def generate_report(results: Dict[str, Dict[str, Any]]):
    with open(OUTPUT_FILE, "w") as f:
        f.write("# Data Coverage & Relevance Report\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("Objective: Determine pertinence and comprehensiveness of mining across different databases.\n\n")
        
        f.write("| Topic | Database (Mode) | Hits (Chunks/Nodes) | Unique Files | Top Sources |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        
        for topic in TOPICS:
            for mode in MODES:
                key = f"{topic}_{mode}"
                res = results.get(key, {})
                
                # Format helpful output
                hits = res.get("count", 0)
                unique = res.get("unique_files", 0)
                files = ", ".join(res.get("top_files", []))
                
                if res.get("error"):
                    files = f"⚠️ {res['error']}"
                
                if hits == 0:
                    files = "*(No results)*"
                
                # Map mode to DB name for clarity
                db_name = {
                    "vector": "Vector (Chroma)",
                    "cascading": "Cascading"
                }.get(mode, mode)
                
                f.write(f"| **{topic}** | {db_name} | {hits} | {unique} | {files} |\n")
            
            f.write("| | | | | |\n") # Spacer row
            
    print(f"\nReport saved to query {OUTPUT_FILE}")

def main():
    print("Starting Data Coverage Evaluation...")
    results = {}
    
    for topic in TOPICS:
        print(f"\nAnalyzing topic: {topic}")
        for mode in MODES:
            print(f"  - Querying {mode}...", end="", flush=True)
            res = query_gateway(topic, mode)
            results[f"{topic}_{mode}"] = res
            print(f" Found {res.get('count', 0)} hits.")
            
    generate_report(results)

if __name__ == "__main__":
    main()
