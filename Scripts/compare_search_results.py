#!/usr/bin/env python3
"""
Compare search results from unified server vs Docker toolkit
Tests the embedding service directly (unified server backend)
"""

import requests
import json
import sys
from typing import Dict, List

def test_unified_search(query: str, n_results: int = 5) -> Dict:
    """Test unified server's semantic search"""
    try:
        response = requests.post(
            "http://localhost:8000/query",
            json={
                "query": query,
                "n_results": n_results,
                "reranking": True,
                "deduplicate": True
            },
            timeout=10
        )
        
        if response.status_code == 200:
            return {
                "success": True,
                "results": response.json(),
                "method": "Semantic Search (Unified Server)"
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {response.status_code}",
                "method": "Semantic Search (Unified Server)"
            }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": "Embedding service not running at http://localhost:8000",
            "method": "Semantic Search (Unified Server)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "method": "Semantic Search (Unified Server)"
        }

def format_results(data: Dict) -> str:
    """Format search results for display"""
    if not data.get("success"):
        return f"❌ {data['method']}: {data.get('error', 'Unknown error')}"
    
    results = data.get("results", {})
    documents = results.get('documents', [[]])[0]
    metadatas = results.get('metadatas', [[]])[0]
    distances = results.get('distances', [[]])[0]
    
    if not documents:
        return f"✅ {data['method']}: No results found"
    
    output = [f"✅ {data['method']}: Found {len(documents)} results\n"]
    
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
        relevance = (1 - dist) * 100 if dist < 1 else abs(dist) * 100
        relevance = min(100, max(0, relevance))
        filename = meta.get('filename', 'unknown')
        filepath = meta.get('filepath', 'unknown')
        
        output.append(f"\n{i}. {filename} ({relevance:.0f}% relevant)")
        output.append(f"   📁 {filepath}")
        output.append(f"   📄 {doc[:200]}..." if len(doc) > 200 else f"   📄 {doc}")
    
    return "\n".join(output)

def main():
    if len(sys.argv) < 2:
        print("Usage: python compare_search_results.py <query> [n_results]")
        print("Example: python compare_search_results.py 'lymphoma treatments' 5")
        sys.exit(1)
    
    query = sys.argv[1]
    n_results = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    print("=" * 70)
    print(f"SEARCH COMPARISON: '{query}'")
    print("=" * 70)
    print()
    
    # Test unified server
    print("Testing Unified Server (Semantic Search)...")
    unified_results = test_unified_search(query, n_results)
    print(format_results(unified_results))
    
    print()
    print("=" * 70)
    print("NOTE: Docker Toolkit uses Obsidian's native text search")
    print("To compare with Docker toolkit, use Claude Desktop with both servers enabled")
    print("and ask Claude to use both tools explicitly.")
    print("=" * 70)

if __name__ == "__main__":
    main()
