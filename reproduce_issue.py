
import urllib.request
import json
import sys

# Color output
def print_green(text): print(f"\033[92m{text}\033[0m")
def print_red(text): print(f"\033[91m{text}\033[0m")
def print_yellow(text): print(f"\033[93m{text}\033[0m")

EMBEDDING_URL = "http://localhost:8000/query"

def query_vector_db(query, n_results=100):
    print_yellow(f"\n🔍 Querying: '{query}' (n={n_results})")
    try:
        data = {
            "query": query,
            "n_results": n_results,
            "reranking": False,
            "deduplicate": True
        }
        req = urllib.request.Request(
            EMBEDDING_URL,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                print_red(f"Error: {response.status}")
                return

            data = json.loads(response.read().decode('utf-8'))
            documents = data.get("documents", [[]])[0]
            metadatas = data.get("metadatas", [[]])[0]
            distances = data.get("distances", [[]])[0]
            
            print(f"Found {len(documents)} results:")
            
            for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances)):
                filename = meta.get('filename', 'Unknown')
                path = meta.get('filepath', 'Unknown')
                # New formula (Python uses 1.0 for float division, just in case)
                score = max(0.0, (1.0 - (dist / 2.0)) * 100.0)
                
                print(f"[{i+1}] {score:.2f}% {filename} ({path})")
                
    except Exception as e:
        print_red(f"Exception: {e}")

if __name__ == "__main__":
    query_vector_db("bread")
