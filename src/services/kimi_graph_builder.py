"""
Kimi-Powered Knowledge Graph Builder for Obsidian Vault

This service uses Kimi K2 via OpenRouter to extract entities and relationships from your
Obsidian vault chunks, building a queryable knowledge graph.
"""

import json
import os
import re
import time
import hashlib
import logging
import pickle
from typing import List, Dict, Any, Optional, Union, Set
from openai import OpenAI
import networkx as nx
from pathlib import Path
from datetime import datetime

# Configure logging
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

# Graph data directory
GRAPH_DATA_DIR = Path("graph_data")
try:
    GRAPH_DATA_DIR.mkdir(exist_ok=True)
except OSError:
    pass


class GraphBuilder:
    """Build knowledge graph using Kimi's extraction capabilities via OpenRouter"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = None, max_retries: int = 3):
        # Use OPENROUTER_API_KEY + KIMI_MODEL env vars
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        self.model = model or os.environ.get("KIMI_MODEL", "moonshotai/kimi-k2-0905")
        self.max_retries = max_retries

        self.graph = nx.MultiDiGraph()
        self.entity_cache = {}
        self.extraction_stats = {
            'chunks_processed': 0,
            'entities_extracted': 0,
            'relationships_extracted': 0,
            'errors': 0,
            'retries': 0,
            'successful_retries': 0,
        }
        self.failed_chunks = []
        self.processed_chunks: Set[str] = set()

    def add_entity(self, name: str, entity_type: str = "unknown", **properties):
        """Add a single entity to the graph"""
        props = properties.pop('properties', {})
        all_props = {**props, **properties}

        if self.graph.has_node(name):
            existing = self.graph.nodes[name]
            for key, value in all_props.items():
                existing[key] = value
        else:
            self.graph.add_node(name, entity_type=entity_type, **all_props)
            self.entity_cache[name.lower()] = name

    def add_relationship(self, source: str, target: str, relationship_type: str = "relates_to", **properties):
        """Add a single relationship to the graph"""
        if not self.graph.has_node(source):
            self.add_entity(source)
        if not self.graph.has_node(target):
            self.add_entity(target)

        self.graph.add_edge(source, target, relationship_type=relationship_type, **properties)

    def clean_entity_name(self, name: str) -> str:
        """Clean entity name"""
        cleaned = name.strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned

    def merge_graph(self, other_graph: nx.MultiDiGraph):
        """Merge another graph into this one"""
        for node, data in other_graph.nodes(data=True):
            if self.graph.has_node(node):
                existing = self.graph.nodes[node]
                for key, value in data.items():
                    if key not in existing:
                        existing[key] = value
            else:
                self.graph.add_node(node, **data)
                self.entity_cache[node.lower()] = node

        for source, target, data in other_graph.edges(data=True):
            self.graph.add_edge(source, target, **data)

    def _get_chunk_hash(self, chunk_text: str, metadata: Dict) -> str:
        """Generate a unique hash for a chunk"""
        chunk_id = f"{metadata.get('filename', '')}:{metadata.get('chunk_id', '')}:{chunk_text[:100]}"
        return hashlib.md5(chunk_id.encode()).hexdigest()

    def extract_graph_from_chunk(self, chunk_text: str, metadata: Dict, retry_count: int = 0) -> Dict[str, Any]:
        """Use Kimi to extract entities and relationships from a single chunk"""
        if len(chunk_text.strip()) < 50:
            return {'entities': [], 'relationships': []}
        
        prompt = f"""Analyze this text from a personal knowledge base and extract:

1. **Entities**: Important concepts, people, places, treatments, technologies, projects, etc.
2. **Relationships**: How these entities relate to each other.
3. **Timeline**: Specific dates or sequences of events.
4. **Importance**: Rate the clinical or central relevance of entities (1-10).

Text to analyze:
<text>
{chunk_text[:8000]}
</text>

Metadata:
- Source: {metadata.get('filename', 'Unknown')}
- Date: {metadata.get('date', 'Unknown')}

Extract entities and relationships in JSON format. IMPORTANT: Return ONLY valid JSON, no markdown, no explanations:

{{
  "entities": [
    {{
      "name": "Entity Name",
      "type": "person|treatment|concept|technology|event|project|location|medication|condition",
      "properties": {{
        "description": "Brief description",
        "domain": "medical|technical|personal|general",
        "importance": 10,
        "category": "treatment|symptom|metric|other"
      }}
    }}
  ],
  "relationships": [
    {{
      "source": "Entity1 Name",
      "target": "Entity2 Name", 
      "type": "treats|causes|uses|creates|relates_to|part_of|used_in|leads_to|happened_on|followed_by",
      "properties": {{
        "description": "How they relate",
        "strength": "strong|medium|weak",
        "temporal": "2023-01-15|before|after|during|null",
        "sequence_id": 1
      }}
    }}
  ]
}}

Guidelines:
- **Importance Scoring**: Rate entities 1-10. 10 = Critical medical diagnosis/treatment or core project. 1 = Minor detail.
- **Temporal Tracking**: If a relationship has a specific date or order, capture it in "temporal".
- Extract 5-15 important entities per chunk.
- For medical content: strictly identify treatments, conditions, medications, dosages.
- Return ONLY the JSON object, no markdown code blocks, no explanations"""

        for attempt in range(self.max_retries):
            try:
                max_tokens = 6000 if retry_count > 0 else 4096
                temperature = 0.1 if retry_count > 0 else 0.3
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object"} if "kimi" in self.model.lower() else None
                )
                
                response_text = response.choices[0].message.content.strip()
                graph_data = self._parse_json_response(response_text, metadata, attempt)
                
                if 'entities' not in graph_data: graph_data['entities'] = []
                if 'relationships' not in graph_data: graph_data['relationships'] = []
                
                # Add source metadata
                for entity in graph_data.get('entities', []):
                    if 'properties' not in entity or not isinstance(entity['properties'], dict): 
                        entity['properties'] = {}
                    
                    if 'sources' not in entity['properties']: 
                        entity['properties']['sources'] = []
                        
                    entity['properties']['sources'].append({
                        'filename': metadata.get('filename', 'Unknown'),
                        'chunk_id': metadata.get('chunk_id', 'Unknown')
                    })
                
                for rel in graph_data.get('relationships', []):
                    if 'properties' not in rel or not isinstance(rel['properties'], dict): 
                        rel['properties'] = {}
                    
                    if 'sources' not in rel['properties']: 
                        rel['properties']['sources'] = []
                        
                    rel['properties']['sources'].append({
                        'filename': metadata.get('filename', 'Unknown'),
                        'chunk_id': metadata.get('chunk_id', 'Unknown')
                    })
                
                self.extraction_stats['chunks_processed'] += 1
                if retry_count > 0: self.extraction_stats['successful_retries'] += 1
                self.extraction_stats['entities_extracted'] += len(graph_data.get('entities', []))
                self.extraction_stats['relationships_extracted'] += len(graph_data.get('relationships', []))
                
                return graph_data
                
            except Exception as e:
                error_msg = str(e)
                if (attempt + 1) >= self.max_retries:
                    self.extraction_stats['errors'] += 1
                    logger.error(f"Error extracting from chunk: {error_msg[:100]}")
                    self.failed_chunks.append({
                        'text': chunk_text,
                        'metadata': metadata,
                        'error': error_msg,
                        'attempts': retry_count + self.max_retries
                    })
                    return {'entities': [], 'relationships': []}
                else:
                    self.extraction_stats['retries'] += 1
                    wait_time = (2 ** attempt) * 1
                    time.sleep(wait_time)
                    continue
    
    def _parse_json_response(self, response_text: str, metadata: Dict, attempt: int = 0) -> Dict[str, Any]:
        """Robustly parse JSON response"""
        if response_text.startswith('```'):
            parts = response_text.split('```')
            for part in parts:
                part = part.strip()
                if part.startswith('json'): part = part[4:].strip()
                if part.startswith('{'):
                    response_text = part
                    break
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*\}', response_text, re.MULTILINE | re.DOTALL)
            if json_match:
                try: return json.loads(json_match.group())
                except: pass
        return {'entities': [], 'relationships': []}

    def add_to_graph(self, graph_data: Dict[str, Any]):
        """Add extracted entities and relationships to the graph"""
        for entity in graph_data.get('entities', []):
            if 'name' not in entity: continue
            entity_name = entity['name']
            entity_type = entity.get('type', 'unknown')
            entity_props = entity.get('properties', {})
            
            if self.graph.has_node(entity_name):
                existing = self.graph.nodes[entity_name]
                existing['sources'] = existing.get('sources', []) + entity_props.get('sources', [])
                for key, value in entity_props.items():
                    if key != 'sources' and key not in existing:
                        existing[key] = value
            else:
                self.graph.add_node(entity_name, entity_type=entity_type, **entity_props)
                self.entity_cache[entity_name.lower()] = entity_name
        
        for rel in graph_data.get('relationships', []):
            if 'source' not in rel or 'target' not in rel: continue
            source_norm = self.entity_cache.get(rel['source'].lower(), rel['source'])
            target_norm = self.entity_cache.get(rel['target'].lower(), rel['target'])
            if self.graph.has_node(source_norm) and self.graph.has_node(target_norm):
                self.graph.add_edge(source_norm, target_norm, relationship_type=rel.get('type', 'relates_to'), **rel.get('properties', {}))

    def build_graph_from_chunks(self, chunks: List[Dict], batch_size: int = 10, skip_processed: bool = True):
        """Build graph from multiple chunks"""
        total = len(chunks)
        for i, chunk in enumerate(chunks):
            chunk_hash = self._get_chunk_hash(chunk['text'], chunk['metadata'])
            if skip_processed and chunk_hash in self.processed_chunks: continue
            graph_data = self.extract_graph_from_chunk(chunk['text'], chunk['metadata'])
            self.add_to_graph(graph_data)
            self.processed_chunks.add(chunk_hash)
            if (i + 1) % batch_size == 0:
                self.save_graph(str(GRAPH_DATA_DIR / f"graph_checkpoint_{i+1}.pkl"))
        logger.info(f"Graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")

    def save_graph(self, filepath: str = None):
        """Save graph to disk"""
        if filepath is None: filepath = str(GRAPH_DATA_DIR / "knowledge_graph.pkl")
        file_path = Path(filepath)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'wb') as f:
            pickle.dump({
                'graph': self.graph,
                'stats': self.extraction_stats,
                'processed_chunks': list(self.processed_chunks),
                'timestamp': datetime.now().isoformat()
            }, f)

    def load_graph(self, filepath: str = None):
        """Load graph from disk"""
        if filepath is None: filepath = str(GRAPH_DATA_DIR / "knowledge_graph.pkl")
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            self.graph = data['graph']
            # Safely update stats ensuring all keys exist (handling backwards compatibility)
            loaded_stats = data.get('stats', {})
            if isinstance(loaded_stats, dict):
                self.extraction_stats.update(loaded_stats)
            # self.extraction_stats already initialized with defaults in __init__
            self.processed_chunks = set(data.get('processed_chunks', []))
            self.entity_cache = {name.lower(): name for name in self.graph.nodes()}


class GraphQuerier:
    """Query the knowledge graph using Kimi/OpenRouter reasoning"""
    
    def __init__(self, graph_builder: GraphBuilder, api_key: Optional[str] = None, model: str = None):
        self.graph = graph_builder.graph
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )
        self.model = model or os.environ.get("KIMI_MODEL", "moonshotai/kimi-k2-0905")
    
    def find_paths(self, source: str, target: str, max_depth: int = 3) -> List[List[str]]:
        """Find paths between two entities"""
        source = source.strip().strip('"\'')
        target = target.strip().strip('"\'')
        def find_best_match(name):
            name_lower = name.lower()
            matches = [n for n in self.graph.nodes() if name_lower in n.lower() or n.lower() in name_lower]
            return max(matches, key=lambda n: self.graph.degree(n)) if matches else None
        s_ent = find_best_match(source) if source not in self.graph else source
        t_ent = find_best_match(target) if target not in self.graph else target
        if not s_ent or not t_ent: return []
        try:
            paths = list(nx.all_simple_paths(self.graph.to_undirected(), s_ent, t_ent, cutoff=max_depth))
            return paths[:10]
        except: return []

    def get_entity_neighborhood(self, entity: str, depth: int = 1) -> Dict[str, Any]:
        """Get entities connected to this entity"""
        entity = entity.strip().strip('"\'')
        matches = [n for n in self.graph.nodes() if entity.lower() in n.lower() or n.lower() in entity.lower()]
        if not matches: return {'entity': entity, 'found': False}
        entity = max(matches, key=lambda n: self.graph.degree(n))
        neighbors = {'entity': entity, 'found': True, 'properties': dict(self.graph.nodes[entity]), 'outgoing': [], 'incoming': []}
        for _, t, d in self.graph.out_edges(entity, data=True):
            neighbors['outgoing'].append({'target': t, 'relationship': d.get('relationship_type', 'related_to'), 'properties': d})
        for s, _, d in self.graph.in_edges(entity, data=True):
            neighbors['incoming'].append({'source': s, 'relationship': d.get('relationship_type', 'related_to'), 'properties': d})
        return neighbors
    
    def query_with_llm(self, user_query: str, max_entities: int = 20, additional_context: str = "", custom_system_prompt: str = "") -> tuple[str, list[dict]]:
        """
        Query the knowledge graph using the LLM with optional additional context.
        Returns: (answer_text, context_nodes)
        """
        entities_in_query = [node for node in self.graph.nodes() if node.lower() in user_query.lower()]
        logger.info(f"=== GRAPH BUILDER DEBUG ===")
        logger.info(f"Entities found in query: {entities_in_query[:10]}")
        
        # Get neighborhood for entities
        graph_context = [self.get_entity_neighborhood(e) for e in entities_in_query[:max_entities]]
        
        # Fallback to centrality if no entities found
        if not graph_context:
            centrality = nx.degree_centrality(self.graph)
            top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:10]
            logger.info(f"No entities in query, using top centrality nodes: {[node for node, _ in top_nodes]}")
            graph_context = [self.get_entity_neighborhood(node) for node, _ in top_nodes]

        context_text = "\n---\n".join([f"Entity: {c['entity']}\nRelationships: " +
            ", ".join([f"{c['entity']} --[{r['relationship']}]--> {r['target']}" for r in c['outgoing']]) for c in graph_context])

        logger.info(f"Graph context (first 500 chars): {context_text[:500]}")
        logger.info(f"Using custom system prompt: {bool(custom_system_prompt)}")

        # Build prompt with optional custom system prompt
        if custom_system_prompt:
            prompt_parts = [custom_system_prompt]
        else:
            prompt_parts = ["You are analyzing a personal knowledge graph. Answer the user's question based on the graph structure and relationships."]

        if additional_context:
            prompt_parts.append(f"\nAdditional Context from Vector Search:\n<vector_context>\n{additional_context}\n</vector_context>")

        prompt_parts.append(f"\nKnowledge Graph Context:\n<graph>\n{context_text}\n</graph>")
        prompt_parts.append(f"\nUser Question: {user_query}")
        prompt_parts.append("\nProvide a comprehensive answer cite specific entities when relevant.")

        prompt = "\n".join(prompt_parts)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000
        )
        
        return response.choices[0].message.content, graph_context

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get graph statistics"""
        return {'total_nodes': self.graph.number_of_nodes(), 'total_edges': self.graph.number_of_edges()}
