#!/usr/bin/env python3
"""
Direct Obsidian Vault Query Script
Bypasses MCP length limits by calling the embedding service directly
"""

import requests
import sys
from typing import List, Dict, Any

EMBEDDING_URL = "http://localhost:8000"

def search_vault(query: str, n_results: int = 10) -> List[Dict[str, Any]]:
    """
    Search your Obsidian vault and return full results
    
    Args:
        query: Search query text
        n_results: Number of results to return (default 10)
    
    Returns:
        List of result dictionaries with content, metadata, and scores
    """
    print(f"🔍 Searching for: '{query}'\n")
    
    try:
        response = requests.post(
            f"{EMBEDDING_URL}/query",
            json={
                "query": query,
                "n_results": n_results,
                "reranking": True,
                "deduplicate": True
            },
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code} - {response.text}")
            return []
        
        results = response.json()
        documents = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        distances = results.get('distances', [[]])[0]
        
        # Build structured results
        search_results = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            relevance = (1 - dist) * 100
            result = {
                'filename': meta.get('filename', 'unknown'),
                'filepath': meta.get('filepath', 'unknown'),
                'content': doc,
                'relevance': relevance,
                'distance': dist
            }
            search_results.append(result)
        
        return search_results
    
    except requests.exceptions.ConnectionError:
        print("❌ Error: Can't connect to embedding service (port 8000)")
        print("   Make sure your Docker services are running:")
        print("   ./Scripts/docker_start.sh")
        return []
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return []

def print_results(results: List[Dict[str, Any]]):
    """Print search results in a readable format"""
    if not results:
        print("No results found.")
        return
    
    print(f"✅ Found {len(results)} results:\n")
    print("=" * 80)
    
    for i, result in enumerate(results, 1):
        filename = result['filename']
        filepath = result['filepath']
        relevance = result['relevance']
        content = result['content']
        
        print(f"\n{i}. {filename}")
        print(f"   Relevance: {relevance:.1f}%")
        print(f"   Path: {filepath}")
        print(f"\n   Content ({len(content)} chars):")
        print("-" * 80)
        # Print full content or truncate at 1000 chars
        if len(content) > 1000:
            print(f"{content[:1000]}...\n[truncated]")
        else:
            print(content)
        print("-" * 80)

def save_results(results: List[Dict[str, Any]], output_file: str = "search_results.txt"):
    """Save full results to a file"""
    with open(output_file, 'w') as f:
        for i, result in enumerate(results, 1):
            f.write(f"{'='*80}\n")
            f.write(f"Result {i}\n")
            f.write(f"{'='*80}\n\n")
            f.write(f"Filename: {result['filename']}\n")
            f.write(f"Path: {result['filepath']}\n")
            f.write(f"Relevance: {result['relevance']:.1f}%\n\n")
            f.write(f"Content:\n{result['content']}\n\n")
    
    print(f"\n💾 Full results saved to: {output_file}")

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python query_vault.py '<search query>' [n_results]")
        print("\nExamples:")
        print("  python query_vault.py 'Home Assistant configuration'")
        print("  python query_vault.py 'ESP32' 20")
        print("  python query_vault.py 'lymphoma treatment' 5")
        sys.exit(1)
    
    query = sys.argv[1]
    n_results = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    # Check if services are running
    try:
        response = requests.get(f"{EMBEDDING_URL}/health", timeout=2)
        if response.status_code != 200:
            print("⚠️  Warning: Embedding service might not be responding correctly")
    except requests.exceptions.ConnectionError:
        print("❌ Embedding service not available!")
        print("   Start it with: ./Scripts/docker_start.sh")
        sys.exit(1)
    
    # Perform search (service cap is ~50, but n_results can be any number)
    results = search_vault(query, n_results)
    
    if not results:
        print("\n⚠️  No results found. Try a different query.")
        return
    
    # Display results
    print_results(results)
    
    # Ask if user wants to save
    print("\n" + "=" * 80)
    print(f"\n💡 Tip: For a specific file, run:")
    print(f"   grep -r '{query}' '/path/to/vault'")
    
    # Save to file by default
    save_results(results, f"search_results_{query.replace(' ', '_')}.txt")

if __name__ == "__main__":
    main()

