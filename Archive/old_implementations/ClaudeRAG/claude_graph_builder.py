"""
Claude-Powered Knowledge Graph Builder for Obsidian Vault

This service uses Claude API to extract entities and relationships from your
Obsidian vault chunks, building a queryable knowledge graph.
"""

import json
import os
from typing import List, Dict, Any, Optional
from anthropic import Anthropic
import networkx as nx
from pathlib import Path
import pickle
from datetime import datetime


class ClaudeGraphBuilder:
    """Build knowledge graph using Claude's reasoning capabilities"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.graph = nx.MultiDiGraph()
        self.entity_cache = {}
        self.extraction_stats = {
            'chunks_processed': 0,
            'entities_extracted': 0,
            'relationships_extracted': 0,
            'errors': 0
        }
    
    def extract_graph_from_chunk(self, chunk_text: str, metadata: Dict) -> Dict[str, Any]:
        """
        Use Claude to extract entities and relationships from a single chunk
        
        Returns:
            {
                'entities': [
                    {'name': 'CAR-T Therapy', 'type': 'treatment', 'properties': {...}},
                    ...
                ],
                'relationships': [
                    {'source': 'CAR-T Therapy', 'target': 'Lymphoma', 'type': 'treats', 'properties': {...}},
                    ...
                ]
            }
        """
        
        prompt = f"""Analyze this text from a personal knowledge base and extract:

1. **Entities**: Important concepts, people, places, treatments, technologies, projects, etc.
2. **Relationships**: How these entities relate to each other

Text to analyze:
<text>
{chunk_text}
</text>

Metadata:
- Source: {metadata.get('filename', 'Unknown')}
- Date: {metadata.get('date', 'Unknown')}

Extract entities and relationships in JSON format:

{{
  "entities": [
    {{
      "name": "Entity Name",
      "type": "person|treatment|concept|technology|event|project|location|medication|condition",
      "properties": {{
        "description": "Brief description",
        "domain": "medical|technical|personal|general",
        "importance": "high|medium|low"
      }}
    }}
  ],
  "relationships": [
    {{
      "source": "Entity1 Name",
      "target": "Entity2 Name", 
      "type": "treats|causes|uses|creates|relates_to|part_of|used_in|leads_to",
      "properties": {{
        "description": "How they relate",
        "strength": "strong|medium|weak",
        "temporal": "before|after|during|null"
      }}
    }}
  ]
}}

Guidelines:
- Extract 3-10 most important entities per chunk
- Focus on entities that connect to other knowledge
- For medical content: extract treatments, conditions, medications, procedures
- For technical content: extract technologies, projects, tools, methods
- Relationships should be specific and meaningful
- Use consistent entity names (e.g., always "CAR-T Therapy", not variations)

Respond with ONLY the JSON object, no other text."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=2048,
                temperature=0.3,  # Lower temperature for consistent extraction
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Parse JSON response
            response_text = response.content[0].text.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            graph_data = json.loads(response_text)
            
            # Add source metadata to all entities and relationships
            for entity in graph_data.get('entities', []):
                if 'sources' not in entity['properties']:
                    entity['properties']['sources'] = []
                entity['properties']['sources'].append({
                    'filename': metadata.get('filename', 'Unknown'),
                    'chunk_id': metadata.get('chunk_id', 'Unknown')
                })
            
            for rel in graph_data.get('relationships', []):
                if 'sources' not in rel['properties']:
                    rel['properties']['sources'] = []
                rel['properties']['sources'].append({
                    'filename': metadata.get('filename', 'Unknown'),
                    'chunk_id': metadata.get('chunk_id', 'Unknown')
                })
            
            self.extraction_stats['chunks_processed'] += 1
            self.extraction_stats['entities_extracted'] += len(graph_data.get('entities', []))
            self.extraction_stats['relationships_extracted'] += len(graph_data.get('relationships', []))
            
            return graph_data
            
        except Exception as e:
            self.extraction_stats['errors'] += 1
            print(f"Error extracting from chunk: {e}")
            return {'entities': [], 'relationships': []}
    
    def add_to_graph(self, graph_data: Dict[str, Any]):
        """Add extracted entities and relationships to the NetworkX graph"""
        
        # Add entities as nodes
        for entity in graph_data.get('entities', []):
            entity_name = entity['name']
            
            # If entity exists, merge properties
            if self.graph.has_node(entity_name):
                existing = self.graph.nodes[entity_name]
                # Merge sources
                existing_sources = existing.get('sources', [])
                new_sources = entity['properties'].get('sources', [])
                existing['sources'] = existing_sources + new_sources
                # Update other properties if needed
                for key, value in entity['properties'].items():
                    if key != 'sources' and key not in existing:
                        existing[key] = value
            else:
                # Add new entity
                self.graph.add_node(
                    entity_name,
                    entity_type=entity['type'],
                    **entity['properties']
                )
                self.entity_cache[entity_name.lower()] = entity_name
        
        # Add relationships as edges
        for rel in graph_data.get('relationships', []):
            source = rel['source']
            target = rel['target']
            rel_type = rel['type']
            
            # Normalize entity names using cache
            source_norm = self.entity_cache.get(source.lower(), source)
            target_norm = self.entity_cache.get(target.lower(), target)
            
            # Only add edge if both entities exist
            if self.graph.has_node(source_norm) and self.graph.has_node(target_norm):
                self.graph.add_edge(
                    source_norm,
                    target_norm,
                    relationship_type=rel_type,
                    **rel['properties']
                )
    
    def build_graph_from_chunks(self, chunks: List[Dict], batch_size: int = 10):
        """
        Build graph from multiple chunks
        
        Args:
            chunks: List of {'text': str, 'metadata': dict}
            batch_size: Process this many chunks before saving progress
        """
        total = len(chunks)
        
        for i, chunk in enumerate(chunks):
            print(f"Processing chunk {i+1}/{total}...")
            
            graph_data = self.extract_graph_from_chunk(
                chunk['text'],
                chunk['metadata']
            )
            
            self.add_to_graph(graph_data)
            
            # Save progress every batch_size chunks
            if (i + 1) % batch_size == 0:
                self.save_graph(f"graph_checkpoint_{i+1}.pkl")
                print(f"Checkpoint saved at {i+1} chunks")
        
        print("\nGraph building complete!")
        print(f"Stats: {self.extraction_stats}")
        print(f"Graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
    
    def save_graph(self, filepath: str = "knowledge_graph.pkl"):
        """Save graph to disk"""
        with open(filepath, 'wb') as f:
            pickle.dump({
                'graph': self.graph,
                'stats': self.extraction_stats,
                'timestamp': datetime.now().isoformat()
            }, f)
        print(f"Graph saved to {filepath}")
    
    def load_graph(self, filepath: str = "knowledge_graph.pkl"):
        """Load graph from disk"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            self.graph = data['graph']
            self.extraction_stats = data['stats']
            print(f"Graph loaded: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
    
    def export_graph_json(self, filepath: str = "knowledge_graph.json"):
        """Export graph to JSON for visualization"""
        graph_data = {
            'nodes': [],
            'edges': [],
            'stats': self.extraction_stats
        }
        
        # Export nodes
        for node, data in self.graph.nodes(data=True):
            node_data = {'id': node, 'label': node}
            node_data.update(data)
            # Limit sources to keep file size reasonable
            if 'sources' in node_data:
                node_data['source_count'] = len(node_data['sources'])
                node_data['sources'] = node_data['sources'][:5]  # Keep first 5
            graph_data['nodes'].append(node_data)
        
        # Export edges
        for source, target, data in self.graph.edges(data=True):
            edge_data = {
                'source': source,
                'target': target,
            }
            edge_data.update(data)
            if 'sources' in edge_data:
                edge_data['source_count'] = len(edge_data['sources'])
                edge_data['sources'] = edge_data['sources'][:3]
            graph_data['edges'].append(edge_data)
        
        with open(filepath, 'w') as f:
            json.dump(graph_data, f, indent=2)
        
        print(f"Graph exported to {filepath}")


class ClaudeGraphQuerier:
    """Query the knowledge graph using Claude's reasoning"""
    
    def __init__(self, graph_builder: ClaudeGraphBuilder, api_key: Optional[str] = None):
        self.graph = graph_builder.graph
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
    
    def find_paths(self, source: str, target: str, max_depth: int = 3) -> List[List[str]]:
        """Find paths between two entities"""
        try:
            # Try exact match first
            if source in self.graph and target in self.graph:
                paths = list(nx.all_simple_paths(self.graph, source, target, cutoff=max_depth))
                return paths[:10]  # Return top 10 paths
        except:
            pass
        
        # Try fuzzy match
        source_matches = [n for n in self.graph.nodes() if source.lower() in n.lower()]
        target_matches = [n for n in self.graph.nodes() if target.lower() in n.lower()]
        
        all_paths = []
        for s in source_matches[:3]:
            for t in target_matches[:3]:
                try:
                    paths = list(nx.all_simple_paths(self.graph, s, t, cutoff=max_depth))
                    all_paths.extend(paths[:5])
                except:
                    continue
        
        return all_paths[:10]
    
    def get_entity_neighborhood(self, entity: str, depth: int = 1) -> Dict[str, Any]:
        """Get entities connected to this entity"""
        if entity not in self.graph:
            # Try fuzzy match
            matches = [n for n in self.graph.nodes() if entity.lower() in n.lower()]
            if not matches:
                return {'entity': entity, 'found': False}
            entity = matches[0]
        
        # Get neighbors
        neighbors = {
            'entity': entity,
            'properties': dict(self.graph.nodes[entity]),
            'outgoing': [],
            'incoming': []
        }
        
        # Outgoing edges
        for _, target, data in self.graph.out_edges(entity, data=True):
            neighbors['outgoing'].append({
                'target': target,
                'relationship': data.get('relationship_type', 'related_to'),
                'properties': data
            })
        
        # Incoming edges
        for source, _, data in self.graph.in_edges(entity, data=True):
            neighbors['incoming'].append({
                'source': source,
                'relationship': data.get('relationship_type', 'related_to'),
                'properties': data
            })
        
        return neighbors
    
    def query_with_claude(self, user_query: str, max_entities: int = 20) -> str:
        """
        Use Claude to reason over the knowledge graph
        
        This retrieves relevant graph context and asks Claude to synthesize an answer
        """
        
        # Extract key entities from query
        entities_in_query = []
        for node in self.graph.nodes():
            if node.lower() in user_query.lower():
                entities_in_query.append(node)
        
        # Get graph context
        graph_context = []
        for entity in entities_in_query[:max_entities]:
            neighborhood = self.get_entity_neighborhood(entity, depth=1)
            graph_context.append(neighborhood)
        
        # If no entities found, get most central nodes
        if not graph_context:
            centrality = nx.degree_centrality(self.graph)
            top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:10]
            for node, _ in top_nodes:
                graph_context.append(self.get_entity_neighborhood(node, depth=1))
        
        # Format context for Claude
        context_text = self._format_graph_context(graph_context)
        
        # Query Claude
        prompt = f"""You are analyzing a personal knowledge graph. Answer the user's question based on the graph structure and relationships.

Knowledge Graph Context:
<graph>
{context_text}
</graph>

User Question: {user_query}

Provide a comprehensive answer that:
1. Identifies relevant entities and relationships
2. Explains connections and paths between concepts
3. Synthesizes information from multiple parts of the graph
4. Cites specific entities when relevant

If the graph doesn't contain enough information, say so clearly."""

        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=3000,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        return response.content[0].text
    
    def _format_graph_context(self, graph_context: List[Dict]) -> str:
        """Format graph data for Claude"""
        formatted = []
        
        for item in graph_context:
            if not item.get('found', True):
                continue
            
            entity = item['entity']
            props = item.get('properties', {})
            
            # Entity info
            entity_text = f"Entity: {entity}\n"
            entity_text += f"Type: {props.get('entity_type', 'Unknown')}\n"
            if 'description' in props:
                entity_text += f"Description: {props['description']}\n"
            
            # Relationships
            if item.get('outgoing'):
                entity_text += "Relationships:\n"
                for rel in item['outgoing'][:10]:  # Limit to 10
                    entity_text += f"  - {entity} --[{rel['relationship']}]--> {rel['target']}\n"
            
            if item.get('incoming'):
                for rel in item['incoming'][:10]:
                    entity_text += f"  - {rel['source']} --[{rel['relationship']}]--> {entity}\n"
            
            formatted.append(entity_text)
        
        return "\n---\n".join(formatted)
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the graph"""
        return {
            'total_nodes': self.graph.number_of_nodes(),
            'total_edges': self.graph.number_of_edges(),
            'density': nx.density(self.graph),
            'is_connected': nx.is_weakly_connected(self.graph),
            'top_entities': self._get_top_entities(10)
        }
    
    def _get_top_entities(self, n: int = 10) -> List[Dict[str, Any]]:
        """Get most connected entities"""
        centrality = nx.degree_centrality(self.graph)
        top = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:n]
        return [
            {
                'entity': entity,
                'centrality': score,
                'connections': self.graph.degree(entity)
            }
            for entity, score in top
        ]


if __name__ == "__main__":
    # Example usage
    print("Claude Graph Builder - Example Usage")
    print("=" * 50)
    
    # Initialize builder
    builder = ClaudeGraphBuilder()
    
    # Example chunks (you'll load these from ChromaDB)
    example_chunks = [
        {
            'text': 'CAR-T therapy is a treatment for lymphoma that uses modified T cells to target cancer cells.',
            'metadata': {'filename': 'medical/lymphoma-treatment.md', 'chunk_id': '1'}
        },
        {
            'text': 'The Fusion 360 project for Gridfinity uses parametric design to create modular storage.',
            'metadata': {'filename': 'tech/3d-printing/gridfinity.md', 'chunk_id': '2'}
        }
    ]
    
    # Build graph (this would process all your 7,113 chunks)
    print("\n1. Building graph from chunks...")
    # builder.build_graph_from_chunks(example_chunks)
    
    # Save graph
    # builder.save_graph("my_knowledge_graph.pkl")
    
    # Load existing graph
    # builder.load_graph("my_knowledge_graph.pkl")
    
    # Query the graph
    print("\n2. Querying the graph...")
    # querier = ClaudeGraphQuerier(builder)
    # answer = querier.query_with_claude("How does CAR-T therapy work for lymphoma?")
    # print(answer)
    
    print("\nReady to process your vault!")
