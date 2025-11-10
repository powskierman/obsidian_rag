#!/usr/bin/env python3
"""
Visualize the LightRAG knowledge graph
Creates an interactive HTML visualization
"""

import sys
import os
from pathlib import Path

# Check if graph exists
graph_path = "./lightrag_db/graph_chunk_entity_relation.graphml"
if not Path(graph_path).exists():
    print("❌ Graph file not found!")
    print(f"   Looking for: {graph_path}")
    print("")
    print("💡 Make sure indexing has started/completed first.")
    sys.exit(1)

print("📊 Loading knowledge graph...")

import networkx as nx
from pyvis.network import Network

# Load the graph
G = nx.read_graphml(graph_path)

print(f"✅ Loaded graph:")
print(f"   📍 Nodes (entities): {G.number_of_nodes()}")
print(f"   🔗 Edges (relationships): {G.number_of_edges()}")
print("")

# Get statistics
print("📈 Graph Statistics:")
if G.number_of_nodes() > 0:
    # Find most connected nodes
    degrees = dict(G.degree())
    top_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:10]
    
    print(f"   🌟 Top 10 most connected entities:")
    for node, degree in top_nodes:
        print(f"      • {node}: {degree} connections")
    print("")

# Create interactive visualization
print("🎨 Creating interactive visualization...")

net = Network(
    height="900px",
    width="100%",
    bgcolor="#222222",
    font_color="white",
    notebook=False
)

# Configure physics
net.barnes_hut(
    gravity=-80000,
    central_gravity=0.3,
    spring_length=200,
    spring_strength=0.001,
    damping=0.09
)

# Add nodes and edges
for node in G.nodes():
    # Node size based on degree
    degree = G.degree(node)
    size = 10 + (degree * 2)
    
    # Get node attributes
    attrs = G.nodes[node]
    label = attrs.get('description', node)[:50]  # Truncate long labels
    
    net.add_node(
        node,
        label=label,
        title=f"<b>{node}</b><br>Connections: {degree}",
        size=size,
        color="#97c2fc"
    )

for edge in G.edges():
    source, target = edge
    # Get edge attributes
    attrs = G.edges[edge]
    keywords = attrs.get('keywords', 'related to')
    
    net.add_edge(
        source,
        target,
        title=keywords,
        color="#848484"
    )

# Save to HTML
output_file = "knowledge_graph.html"
net.save_graph(output_file)

print(f"✅ Visualization created!")
print(f"   📄 File: {output_file}")
print("")
print("🌐 Opening in browser...")
print(f"   If it doesn't open, manually open: file://{os.path.abspath(output_file)}")
print("")
print("💡 Tips:")
print("   • Zoom: Mouse wheel or pinch")
print("   • Pan: Click and drag")
print("   • Hover: See entity details")
print("   • Click: Select and highlight connections")
print("")

# Try to open in browser
import webbrowser
webbrowser.open(f"file://{os.path.abspath(output_file)}")

print("✨ Done!")

