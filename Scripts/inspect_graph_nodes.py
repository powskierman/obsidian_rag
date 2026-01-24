import pickle
import networkx as nx

GRAPH_PATH = "graph_data/knowledge_graph_full.pkl"

def inspect_graph():
    try:
        print(f"Loading graph from {GRAPH_PATH}...")
        with open(GRAPH_PATH, 'rb') as f:
            data = pickle.load(f)
            
        if isinstance(data, dict) and 'graph' in data:
            G = data['graph']
        else:
            G = data
            
        print(f"Loaded Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        
        # Check for specific nodes
        terms = ["lymphoma", "dlbcl", "esp32", "bread"]
        
        print("\n--- Direct Node Inspection ---")
        found_nodes = []
        for term in terms:
            print(f"\nSearching for '{term}':")
            matches = [n for n in G.nodes() if term.lower() in n.lower()]
            print(f"  Found {len(matches)} nodes.")
            if matches:
                 print(f"  Examples: {matches[:5]}")
                 
    except Exception as e:
        print(f"Error: {e}")

inspect_graph()
