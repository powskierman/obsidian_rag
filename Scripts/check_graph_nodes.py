import argparse
import os
import pickle
from pathlib import Path

import networkx as nx

DEFAULT_GRAPH_PATH = Path(__file__).resolve().parents[1] / "data" / "graph_data" / "knowledge_graph_full.pkl"


def parse_args():
    parser = argparse.ArgumentParser(description="Inspect NetworkX graph nodes and centrality.")
    parser.add_argument(
        "--graph",
        default=os.getenv("GRAPH_PATH", str(DEFAULT_GRAPH_PATH)),
        help="Path to knowledge_graph_full.pkl (defaults to GRAPH_PATH or repo data/graph_data)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    graph_path = Path(args.graph)
    if not graph_path.exists():
        raise SystemExit(f"Graph file not found: {graph_path}")

    with open(graph_path, "rb") as f:
        data = pickle.load(f)
        graph = data["graph"]

    nodes = list(graph.nodes())
    print(f"Total nodes: {len(nodes)}")

    nextion_nodes = [n for n in nodes if "nextion" in n.lower()]
    esp32_nodes = [n for n in nodes if "esp32" in n.lower()]

    print(f"Nextion nodes: {nextion_nodes}")
    print(f"ESP32 nodes: {esp32_nodes}")

    # Check top central nodes to see if they match the user's irrelevant results
    centrality = nx.degree_centrality(graph)
    top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:20]
    print("\nTop Central Nodes:")
    for node, score in top_nodes:
        print(f"- {node}: {score:.4f}")


if __name__ == "__main__":
    main()
