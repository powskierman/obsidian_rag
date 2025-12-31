
import requests
import json
import sys

# Color output
def print_green(text): print(f"\033[92m{text}\033[0m")
def print_red(text): print(f"\033[91m{text}\033[0m")
def print_yellow(text): print(f"\033[93m{text}\033[0m")

EMBEDDING_URL = "http://localhost:8000/query"

def query_vector_db(query, n_results=40):
    print_yellow(f"\n🔍 Querying: '{query}' (n={n_results})")
    try:
        response = requests.post(EMBEDDING_URL, json={
            "query": query,
            "n_results": n_results,
            "reranking": False,
            "deduplicate": True
        })
        
        if response.status_code != 200:
            print_red(f"Error: {response.status_code} - {response.text}")
            return

        data = response.json()
        documents = data.get("documents", [[]])[0]
        metadatas = data.get("metadatas", [[]])[0]
        distances = data.get("distances", [[]])[0]
        
        found_pet = False
        print(f"Found {len(documents)} results:")
        
        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
            filename = meta.get('filename', 'Unknown')
            path = meta.get('filepath', 'Unknown')
            score = 1 - dist
            
            # Simple highlight if it looks relevant
            is_relevant = "pet" in filename.lower() or "scan" in filename.lower()
            
            prefix = f"[{i+1}] {score:.4f} "
            if is_relevant:
                 print_green(f"{prefix} {filename} ({path})")
                 found_pet = True
            else:
                 print(f"{prefix} {filename}")
                 
            # Print snippet
            print(f"    Snippet: {doc[:150].replace('\n', ' ')}...")
            
        if not found_pet:
            print_red("❌ No obvious PET scan results found in top results.")

    except Exception as e:
        print_red(f"Exception: {e}")

if __name__ == "__main__":
    query_vector_db("PET scan timeline")
    query_vector_db("2nd PET scan results")
