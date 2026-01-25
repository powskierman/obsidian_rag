#!/usr/bin/env python3
"""
Verify NetworkX Graph Database Completeness

This script analyzes the NetworkX knowledge graph to verify:
- Total nodes and edges
- Coverage of vault files as nodes
- Entity extraction completeness
- Relationship density and quality
- Graph structure integrity
- Comparison with vault files
"""

import os
import sys
import json
import pickle
import networkx as nx
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

# Add src to path for imports
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from indexing.index_vault import should_process

SUPPORTED_EXTENSIONS = {".md", ".pdf"}


def load_graph(graph_path: Path):
    """Load the NetworkX graph from pickle file."""
    print(f"📊 Loading graph from: {graph_path}")
    
    try:
        with open(graph_path, 'rb') as f:
            graph = pickle.load(f)
        
        graph_type = "DiGraph" if isinstance(graph, nx.DiGraph) else "Graph"
        print(f"   ✅ Loaded {graph_type} with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges")
        return graph
        
    except Exception as e:
        print(f"   ❌ Error loading graph: {e}")
        sys.exit(1)


def get_vault_files(vault_path: Path) -> dict:
    """
    Scan vault and return dict of files that should be indexed.
    Returns: {relative_path: {filepath, size, modified, extension}}
    """
    vault_files = {}
    
    for root, dirs, files in os.walk(vault_path):
        for name in files:
            filepath = Path(root) / name
            
            if not should_process(filepath):
                continue
            
            try:
                rel_path = str(filepath.relative_to(vault_path))
                file_stats = filepath.stat()
                
                vault_files[rel_path] = {
                    "filepath": str(filepath),
                    "size": file_stats.st_size,
                    "modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                    "extension": filepath.suffix.lower()
                }
            except Exception as e:
                print(f"  ⚠️  Error processing {filepath}: {e}")
    
    return vault_files


def analyze_graph_structure(graph: nx.Graph) -> dict:
    """Analyze the structure and properties of the graph."""
    print("\n🔍 Analyzing graph structure...")
    
    # Basic stats
    num_nodes = graph.number_of_nodes()
    num_edges = graph.number_of_edges()
    
    # Node types
    node_types = Counter()
    nodes_with_source = 0
    document_nodes = []
    entity_nodes = []
    
    for node, data in graph.nodes(data=True):
        # Use entity_type instead of type
        node_type = data.get('entity_type', data.get('type', 'unknown'))
        node_types[node_type] += 1
        
        # Check for sources (list of source files)
        if 'sources' in data and data['sources']:
            nodes_with_source += 1
        elif 'source_file' in data or 'source' in data:
            nodes_with_source += 1
        
        # In this graph, all nodes are entities/concepts, not documents
        # Documents are referenced in the 'sources' attribute
        if node_type == 'document':
            document_nodes.append(node)
        else:
            # All other nodes are entities
            entity_nodes.append(node)
    
    # Edge types (use relationship_type instead of type)
    edge_types = Counter()
    for u, v, data in graph.edges(data=True):
        edge_type = data.get('relationship_type', data.get('type', 'unknown'))
        edge_types[edge_type] += 1
    
    # Connectivity (handle both directed and undirected graphs)
    if isinstance(graph, nx.DiGraph):
        is_connected = nx.is_weakly_connected(graph)
        num_components = nx.number_weakly_connected_components(graph)
    else:
        is_connected = nx.is_connected(graph)
        num_components = nx.number_connected_components(graph)
    
    # Degree statistics
    degrees = [d for n, d in graph.degree()]
    avg_degree = sum(degrees) / len(degrees) if degrees else 0
    max_degree = max(degrees) if degrees else 0
    min_degree = min(degrees) if degrees else 0
    
    # Isolated nodes
    isolated_nodes = list(nx.isolates(graph))
    
    # Density
    density = nx.density(graph)
    
    structure = {
        "basic_stats": {
            "total_nodes": num_nodes,
            "total_edges": num_edges,
            "density": round(density, 6),
            "is_connected": is_connected,
            "num_components": num_components
        },
        "node_analysis": {
            "types": dict(node_types),
            "nodes_with_source": nodes_with_source,
            "document_nodes": len(document_nodes),
            "entity_nodes": len(entity_nodes),
            "isolated_nodes": len(isolated_nodes)
        },
        "edge_analysis": {
            "types": dict(edge_types),
            "total_edges": num_edges
        },
        "degree_stats": {
            "average": round(avg_degree, 2),
            "max": max_degree,
            "min": min_degree
        },
        "sample_isolated_nodes": isolated_nodes[:10] if isolated_nodes else []
    }
    
    return structure, document_nodes, entity_nodes


def compare_with_vault(graph: nx.Graph, vault_files: dict, document_nodes: list) -> dict:
    """Compare graph sources with vault files."""
    print("\n🔍 Comparing graph with vault files...")
    
    # Extract all unique source files from all nodes
    graph_documents = set()
    
    # Iterate through all nodes and collect source files
    for node, node_data in graph.nodes(data=True):
        # Check for sources list
        if 'sources' in node_data and isinstance(node_data['sources'], list):
            for source in node_data['sources']:
                if isinstance(source, dict) and 'filename' in source:
                    file_path = source['filename']
                    # Normalize path
                    file_path = str(Path(file_path).as_posix())
                    graph_documents.add(file_path)
    
    # Compare
    vault_set = set(vault_files.keys())
    
    # Files in vault but not in graph
    missing_from_graph = []
    for vault_file in vault_set:
        # Check if this file is represented in the graph
        found = False
        for graph_doc in graph_documents:
            if vault_file in graph_doc or graph_doc in vault_file:
                found = True
                break
        
        if not found:
            missing_from_graph.append({
                "filepath": vault_file,
                "size": vault_files[vault_file]["size"],
                "extension": vault_files[vault_file]["extension"]
            })
    
    # Files in graph but not in vault (orphaned)
    orphaned_in_graph = []
    for graph_doc in graph_documents:
        found = False
        for vault_file in vault_set:
            if vault_file in graph_doc or graph_doc in vault_file:
                found = True
                break
        
        if not found:
            orphaned_in_graph.append(graph_doc)
    
    coverage_percentage = 0
    if len(vault_set) > 0:
        matched = len(vault_set) - len(missing_from_graph)
        coverage_percentage = round((matched / len(vault_set)) * 100, 2)
    
    comparison = {
        "total_vault_files": len(vault_set),
        "total_graph_documents": len(graph_documents),
        "missing_from_graph": len(missing_from_graph),
        "orphaned_in_graph": len(orphaned_in_graph),
        "coverage_percentage": coverage_percentage,
        "missing_files": missing_from_graph[:20],  # First 20
        "orphaned_files": orphaned_in_graph[:20]   # First 20
    }
    
    return comparison


def analyze_entity_extraction(graph: nx.Graph, entity_nodes: list) -> dict:
    """Analyze entity extraction quality."""
    print("\n🔍 Analyzing entity extraction...")
    
    # Entity types
    entity_type_counts = Counter()
    entities_with_relationships = 0
    
    entity_details = []
    for entity in entity_nodes:
        node_data = graph.nodes[entity]
        entity_type = node_data.get('entity_type', node_data.get('type', 'entity'))
        entity_type_counts[entity_type] += 1
        
        # Count relationships
        num_relationships = graph.degree(entity)
        if num_relationships > 0:
            entities_with_relationships += 1
        
        entity_details.append({
            "name": str(entity),
            "type": entity_type,
            "relationships": num_relationships,
            "attributes": {k: v for k, v in node_data.items() if k not in ['type', 'name']}
        })
    
    # Sort by most connected
    entity_details.sort(key=lambda x: x['relationships'], reverse=True)
    
    analysis = {
        "total_entities": len(entity_nodes),
        "entity_types": dict(entity_type_counts),
        "entities_with_relationships": entities_with_relationships,
        "entities_without_relationships": len(entity_nodes) - entities_with_relationships,
        "top_connected_entities": entity_details[:20]  # Top 20 most connected
    }
    
    return analysis


def verify_graph_integrity(graph: nx.Graph) -> dict:
    """Verify graph data integrity."""
    print("\n🔍 Verifying graph integrity...")
    
    issues = []
    
    # Check for nodes without entity_type or type
    nodes_without_type = []
    for node, data in graph.nodes(data=True):
        if 'entity_type' not in data and 'type' not in data:
            nodes_without_type.append(str(node))
    
    if nodes_without_type:
        issues.append({
            "type": "missing_node_type",
            "count": len(nodes_without_type),
            "samples": nodes_without_type[:10]
        })
    
    # Check for edges without relationship_type or type
    edges_without_type = []
    for u, v, data in graph.edges(data=True):
        if 'relationship_type' not in data and 'type' not in data:
            edges_without_type.append(f"{u} -> {v}")
    
    if edges_without_type:
        issues.append({
            "type": "missing_edge_type",
            "count": len(edges_without_type),
            "samples": edges_without_type[:10]
        })
    
    # Check for self-loops
    self_loops = list(nx.selfloop_edges(graph))
    if self_loops:
        issues.append({
            "type": "self_loops",
            "count": len(self_loops),
            "samples": [f"{u} -> {v}" for u, v in self_loops[:10]]
        })
    
    integrity = {
        "is_valid": len(issues) == 0,
        "issues": issues,
        "total_issues": sum(issue['count'] for issue in issues)
    }
    
    return integrity


def generate_report(graph_path: Path, vault_path: Path) -> dict:
    """Generate comprehensive verification report."""
    print("=" * 80)
    print("NETWORKX GRAPH DATABASE COMPLETENESS VERIFICATION")
    print("=" * 80)
    print()
    
    # Load graph
    graph = load_graph(graph_path)
    
    # Get vault files
    print("\n📂 Scanning Obsidian vault...")
    vault_files = get_vault_files(vault_path)
    print(f"   Found {len(vault_files)} files that should be indexed")
    
    # Analyze graph structure
    structure, document_nodes, entity_nodes = analyze_graph_structure(graph)
    
    # Compare with vault
    comparison = compare_with_vault(graph, vault_files, document_nodes)
    
    # Analyze entity extraction
    entity_analysis = analyze_entity_extraction(graph, entity_nodes)
    
    # Verify integrity
    integrity = verify_graph_integrity(graph)
    
    # Build report
    report = {
        "timestamp": datetime.now().isoformat(),
        "graph_path": str(graph_path),
        "vault_path": str(vault_path),
        "graph_structure": structure,
        "vault_comparison": comparison,
        "entity_analysis": entity_analysis,
        "integrity": integrity
    }
    
    return report


def print_report(report: dict):
    """Print human-readable report."""
    print()
    print("=" * 80)
    print("VERIFICATION REPORT")
    print("=" * 80)
    print()
    
    # Graph structure
    print("📊 GRAPH STRUCTURE")
    basic = report["graph_structure"]["basic_stats"]
    print(f"   Total nodes:              {basic['total_nodes']:,}")
    print(f"   Total edges:              {basic['total_edges']:,}")
    print(f"   Graph density:            {basic['density']:.6f}")
    print(f"   Is connected:             {basic['is_connected']}")
    print(f"   Connected components:     {basic['num_components']}")
    print()
    
    # Node analysis
    print("🔷 NODE ANALYSIS")
    nodes = report["graph_structure"]["node_analysis"]
    print(f"   Document nodes:           {nodes['document_nodes']:,}")
    print(f"   Entity nodes:             {nodes['entity_nodes']:,}")
    print(f"   Nodes with source:        {nodes['nodes_with_source']:,}")
    print(f"   Isolated nodes:           {nodes['isolated_nodes']:,}")
    print()
    print("   Node types:")
    for node_type, count in sorted(nodes['types'].items(), key=lambda x: x[1], reverse=True):
        print(f"      {node_type:20s}: {count:,}")
    print()
    
    # Edge analysis
    print("🔗 EDGE ANALYSIS")
    edges = report["graph_structure"]["edge_analysis"]
    print(f"   Total edges:              {edges['total_edges']:,}")
    print()
    print("   Edge types:")
    for edge_type, count in sorted(edges['types'].items(), key=lambda x: x[1], reverse=True):
        print(f"      {edge_type:20s}: {count:,}")
    print()
    
    # Degree statistics
    print("📈 DEGREE STATISTICS")
    degree = report["graph_structure"]["degree_stats"]
    print(f"   Average degree:           {degree['average']:.2f}")
    print(f"   Max degree:               {degree['max']}")
    print(f"   Min degree:               {degree['min']}")
    print()
    
    # Vault comparison
    print("📂 VAULT COMPARISON")
    comp = report["vault_comparison"]
    print(f"   Total vault files:        {comp['total_vault_files']:,}")
    print(f"   Graph document nodes:     {comp['total_graph_documents']:,}")
    print(f"   Missing from graph:       {comp['missing_from_graph']:,}")
    print(f"   Orphaned in graph:        {comp['orphaned_in_graph']:,}")
    print(f"   Coverage:                 {comp['coverage_percentage']:.2f}%")
    print()
    
    if comp['missing_files']:
        print(f"   ❌ Sample missing files ({len(comp['missing_files'])} shown):")
        for item in comp['missing_files'][:10]:
            print(f"      • {item['filepath']}")
        print()
    
    # Entity analysis
    print("🏷️  ENTITY ANALYSIS")
    entities = report["entity_analysis"]
    print(f"   Total entities:           {entities['total_entities']:,}")
    print(f"   With relationships:       {entities['entities_with_relationships']:,}")
    print(f"   Without relationships:    {entities['entities_without_relationships']:,}")
    print()
    print("   Entity types:")
    for entity_type, count in sorted(entities['entity_types'].items(), key=lambda x: x[1], reverse=True):
        print(f"      {entity_type:20s}: {count:,}")
    print()
    
    if entities['top_connected_entities']:
        print("   🔝 Top connected entities:")
        for entity in entities['top_connected_entities'][:10]:
            print(f"      • {entity['name']} ({entity['type']}) - {entity['relationships']} connections")
        print()
    
    # Integrity
    print("✅ INTEGRITY CHECK")
    integrity = report["integrity"]
    if integrity['is_valid']:
        print("   ✅ Graph integrity is valid - no issues found!")
    else:
        print(f"   ⚠️  Found {integrity['total_issues']} integrity issues:")
        for issue in integrity['issues']:
            print(f"      • {issue['type']}: {issue['count']} occurrences")
    print()
    
    print("=" * 80)


def save_report(report: dict, output_path: Path):
    """Save report as JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"📄 Full report saved to: {output_path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Verify NetworkX graph database completeness"
    )
    parser.add_argument(
        "--graph",
        default="data/graph_data/knowledge_graph_full.pkl",
        help="Path to graph pickle file (relative to repo root)"
    )
    parser.add_argument(
        "--vault",
        help="Path to Obsidian vault (default: from OBSIDIAN_VAULT_PATH env)"
    )
    parser.add_argument(
        "--output",
        default="networkx_db_verification_report.json",
        help="Output JSON report path"
    )
    
    args = parser.parse_args()
    
    # Get graph path
    graph_path = REPO_ROOT / args.graph
    if not graph_path.exists():
        print(f"❌ Graph file does not exist: {graph_path}")
        print("\nAvailable graph files:")
        for pkl_file in (REPO_ROOT / "data/graph_data").glob("*.pkl"):
            print(f"   • {pkl_file.relative_to(REPO_ROOT)}")
        sys.exit(1)
    
    # Get vault path
    vault_path = args.vault or os.getenv("OBSIDIAN_VAULT_PATH")
    if not vault_path:
        print("❌ No vault path specified. Use --vault or set OBSIDIAN_VAULT_PATH")
        sys.exit(1)
    
    vault_path = Path(vault_path)
    if not vault_path.exists():
        print(f"❌ Vault path does not exist: {vault_path}")
        sys.exit(1)
    
    # Generate report
    report = generate_report(graph_path, vault_path)
    
    # Print report
    print_report(report)
    
    # Save report
    output_path = Path(args.output)
    save_report(report, output_path)
    
    # Exit code based on coverage and integrity
    coverage = report["vault_comparison"]["coverage_percentage"]
    is_valid = report["integrity"]["is_valid"]
    
    if not is_valid:
        print()
        print("⚠️  WARNING: Graph has integrity issues!")
        sys.exit(1)
    elif coverage < 95:
        print()
        print(f"⚠️  WARNING: Coverage is below 95% ({coverage:.2f}%)")
        print("   Consider re-running graph extraction")
        sys.exit(1)
    elif coverage < 100:
        print()
        print(f"ℹ️  Coverage is good but not perfect ({coverage:.2f}%)")
        sys.exit(0)
    else:
        print()
        print("✅ Perfect coverage and integrity!")
        sys.exit(0)


if __name__ == "__main__":
    main()
