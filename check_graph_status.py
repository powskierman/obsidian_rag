
import pickle
import os
from pathlib import Path

graph_file = Path("graph_data/knowledge_graph_full.pkl")
if not graph_file.exists():
    print("Graph file not found.")
else:
    try:
        with open(graph_file, 'rb') as f:
            data = pickle.load(f)
            stats = data.get('stats', {})
            processed_chunks = data.get('processed_chunks', [])
            graph = data.get('graph')
            
            print(f"Graph file loaded: {graph_file}")
            print(f"Nodes: {graph.number_of_nodes() if graph else 0}")
            print(f"Edges: {graph.number_of_edges() if graph else 0}")
            print(f"Stats: {stats}")
            print(f"Processed chunks count: {len(processed_chunks)}")
            print(f"Timestamp: {data.get('timestamp')}")
    except Exception as e:
        print(f"Error reading graph file: {e}")
