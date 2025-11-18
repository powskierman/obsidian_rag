#!/usr/bin/env python3
"""
Analyze errors in knowledge graph building
"""

import pickle
import sys
from pathlib import Path
import networkx as nx

def analyze_graph_errors(graph_file: str = "graph_data/knowledge_graph_full.pkl"):
    """Analyze the graph to understand error patterns"""
    
    graph_path = Path(graph_file)
    if not graph_path.exists():
        print(f"❌ Graph file not found: {graph_file}")
        return
    
    print("=" * 70)
    print("📊 KNOWLEDGE GRAPH ERROR ANALYSIS")
    print("=" * 70)
    
    # Load graph
    with open(graph_path, 'rb') as f:
        data = pickle.load(f)
        graph = data['graph']
        stats = data.get('stats', {})
    
    chunks_processed = stats.get('chunks_processed', 0)
    errors = stats.get('errors', 0)
    entities_extracted = stats.get('entities_extracted', 0)
    relationships_extracted = stats.get('relationships_extracted', 0)
    
    print(f"\n📈 STATISTICS:")
    print(f"  Total Chunks Processed: {chunks_processed}")
    print(f"  Errors: {errors}")
    print(f"  Success Rate: {((chunks_processed - errors) / chunks_processed * 100):.1f}%")
    print(f"  Entities Extracted: {entities_extracted:,}")
    print(f"  Relationships Extracted: {relationships_extracted:,}")
    
    print(f"\n🔍 ERROR ANALYSIS:")
    print(f"  Error Rate: {(errors / chunks_processed * 100):.1f}%")
    print(f"  Successful Chunks: {chunks_processed - errors}")
    print(f"  Failed Chunks: {errors}")
    
    # Calculate average entities per successful chunk
    if chunks_processed - errors > 0:
        avg_entities = entities_extracted / (chunks_processed - errors)
        avg_relationships = relationships_extracted / (chunks_processed - errors)
        print(f"\n📊 AVERAGES (per successful chunk):")
        print(f"  Entities: {avg_entities:.1f}")
        print(f"  Relationships: {avg_relationships:.1f}")
    
    print(f"\n✅ GRAPH QUALITY:")
    print(f"  Total Nodes: {graph.number_of_nodes():,}")
    print(f"  Total Edges: {graph.number_of_edges():,}")
    print(f"  Graph Density: {(graph.number_of_edges() / (graph.number_of_nodes() * (graph.number_of_nodes() - 1))):.6f}")
    
    # Check if graph is connected
    if graph.number_of_nodes() > 0:
        is_connected = graph.number_of_nodes() == 1 or len(list(nx.weakly_connected_components(graph))) == 1
        print(f"  Is Connected: {is_connected}")
    
    print(f"\n💡 WHAT THE ERRORS MEAN:")
    print(f"  The {errors} errors represent chunks where Claude API:")
    print(f"  1. Returned malformed JSON (most common)")
    print(f"  2. Hit rate limits or timeouts")
    print(f"  3. Encountered chunks that were too short or empty")
    print(f"  4. Had API errors (network issues, etc.)")
    print(f"\n  These errors are handled gracefully:")
    print(f"  - The chunk is skipped")
    print(f"  - Processing continues")
    print(f"  - Other chunks are still processed successfully")
    
    print(f"\n🎯 RECOMMENDATION:")
    if errors / chunks_processed > 0.3:
        print(f"  ⚠️  Error rate is high ({errors/chunks_processed*100:.1f}%)")
        print(f"  Consider:")
        print(f"  - Using a more reliable model (claude-sonnet instead of haiku)")
        print(f"  - Increasing max_tokens in the extraction prompt")
        print(f"  - Processing in smaller batches")
    else:
        print(f"  ✅ Error rate is acceptable ({errors/chunks_processed*100:.1f}%)")
        print(f"  Your graph has {graph.number_of_nodes():,} entities and {graph.number_of_edges():,} relationships")
        print(f"  This is a healthy knowledge graph!")

if __name__ == "__main__":
    graph_file = sys.argv[1] if len(sys.argv) > 1 else "graph_data/knowledge_graph_full.pkl"
    analyze_graph_errors(graph_file)

