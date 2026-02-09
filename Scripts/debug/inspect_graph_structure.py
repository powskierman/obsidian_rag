#!/usr/bin/env python3
"""
Inspect NetworkX Graph Structure

Quick script to examine how data is actually stored in the graph.
"""

import pickle
import networkx as nx
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
graph_path = REPO_ROOT / "data/graph_data/knowledge_graph_full.pkl"

print(f"Loading graph from: {graph_path}")
with open(graph_path, 'rb') as f:
    graph = pickle.load(f)

print(f"\nGraph type: {type(graph)}")
print(f"Nodes: {graph.number_of_nodes()}")
print(f"Edges: {graph.number_of_edges()}")

# Sample some nodes
print("\n" + "="*80)
print("SAMPLE NODES (first 10):")
print("="*80)
for i, (node, data) in enumerate(list(graph.nodes(data=True))[:10]):
    print(f"\nNode {i+1}: {node}")
    print(f"  Type: {type(node)}")
    print(f"  Data keys: {list(data.keys())}")
    print(f"  Data: {data}")

# Sample some edges
print("\n" + "="*80)
print("SAMPLE EDGES (first 10):")
print("="*80)
for i, (u, v, data) in enumerate(list(graph.edges(data=True))[:10]):
    print(f"\nEdge {i+1}: {u} -> {v}")
    print(f"  Data keys: {list(data.keys())}")
    print(f"  Data: {data}")

# Check for nodes with specific attributes
print("\n" + "="*80)
print("SEARCHING FOR NODES WITH ATTRIBUTES:")
print("="*80)

# Look for nodes with various possible attribute names
attribute_names = ['type', 'node_type', 'label', 'source', 'source_file', 'filepath', 'path', 'file', 'description', 'content']
for attr in attribute_names:
    nodes_with_attr = [n for n, d in graph.nodes(data=True) if attr in d]
    print(f"  Nodes with '{attr}': {len(nodes_with_attr)}")
    if nodes_with_attr:
        sample = nodes_with_attr[0]
        print(f"    Sample: {sample} -> {graph.nodes[sample][attr]}")

# Look for edges with attributes
print("\n" + "="*80)
print("SEARCHING FOR EDGES WITH ATTRIBUTES:")
print("="*80)
edge_attribute_names = ['type', 'edge_type', 'relation', 'relationship', 'label', 'weight']
for attr in edge_attribute_names:
    edges_with_attr = [(u, v) for u, v, d in graph.edges(data=True) if attr in d]
    print(f"  Edges with '{attr}': {len(edges_with_attr)}")
    if edges_with_attr:
        u, v = edges_with_attr[0]
        print(f"    Sample: {u} -> {v}: {graph.edges[u, v][attr]}")

# Check node name patterns
print("\n" + "="*80)
print("NODE NAME PATTERNS:")
print("="*80)
node_names = list(graph.nodes())
print(f"  Total nodes: {len(node_names)}")
print(f"  Sample node names:")
for node in node_names[:20]:
    print(f"    • {node}")
