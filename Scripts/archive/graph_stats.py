#!/usr/bin/env python3
"""
Show statistics about the knowledge graph without visualization
Quick way to see what's in your graph
"""

import sys
from pathlib import Path
import networkx as nx

graph_path = "./lightrag_db/graph_chunk_entity_relation.graphml"

if not Path(graph_path).exists():
    print("❌ Graph file not found!")
    print(f"   Looking for: {graph_path}")
    print("")
    print("💡 Run this after indexing has started.")
    sys.exit(1)

print("📊 Loading knowledge graph...")
G = nx.read_graphml(graph_path)

print("")
print("╔════════════════════════════════════════════════════════════╗")
print("║              Knowledge Graph Statistics                    ║")
print("╚════════════════════════════════════════════════════════════╝")
print("")

# Basic stats
print(f"📍 Total Entities (Nodes): {G.number_of_nodes()}")
print(f"🔗 Total Relationships (Edges): {G.number_of_edges()}")
print("")

if G.number_of_nodes() == 0:
    print("⚠️  Graph is empty - indexing may have just started")
    sys.exit(0)

# Density
density = nx.density(G)
print(f"📊 Graph Density: {density:.4f}")
print(f"   (0 = sparse, 1 = fully connected)")
print("")

# Connected components
if not nx.is_directed(G):
    components = list(nx.connected_components(G))
    print(f"🌐 Connected Components: {len(components)}")
    if len(components) <= 5:
        for i, comp in enumerate(components, 1):
            print(f"   Component {i}: {len(comp)} entities")
    print("")

# Most connected entities
print("🌟 Top 20 Most Connected Entities:")
degrees = dict(G.degree())
top_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:20]

for i, (node, degree) in enumerate(top_nodes, 1):
    # Get description if available
    attrs = G.nodes[node]
    desc = attrs.get('description', node)
    print(f"   {i:2d}. {node[:50]:50s} ({degree:3d} connections)")

print("")

# Average degree
avg_degree = sum(degrees.values()) / len(degrees)
print(f"📈 Average Connections per Entity: {avg_degree:.2f}")
print("")

# Edge types (if available)
edge_types = {}
for edge in G.edges():
    attrs = G.edges[edge]
    keywords = attrs.get('keywords', 'unknown')
    edge_types[keywords] = edge_types.get(keywords, 0) + 1

if edge_types:
    print("🔗 Relationship Types (top 10):")
    sorted_types = sorted(edge_types.items(), key=lambda x: x[1], reverse=True)[:10]
    for rel_type, count in sorted_types:
        print(f"   • {rel_type[:40]:40s}: {count:4d}")
    print("")

print("💡 To visualize the graph interactively:")
print("   python3 visualize_graph.py")
print("")

