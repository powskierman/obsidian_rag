"""
Improved Claude-Powered Knowledge Graph Builder with Better Error Handling

This version includes:
- Retry logic for failed chunks
- Better JSON parsing with multiple recovery strategies
- Tracking of failed chunks for later retry
- Option to use Sonnet for better reliability
- Maintains existing data when resuming
"""

import json
import os
import re
import time
from typing import List, Dict, Any, Optional, Union, Set
from anthropic import Anthropic
import networkx as nx
from pathlib import Path
import pickle
from datetime import datetime
import hashlib

# Graph data directory
GRAPH_DATA_DIR = Path("graph_data")
GRAPH_DATA_DIR.mkdir(exist_ok=True)


class ImprovedClaudeGraphBuilder:
    """Improved knowledge graph builder with retry logic and better error handling"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = None, max_retries: int = 3):
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        # Default to Haiku 4.5 for cost savings, but allow override
        # Use "claude-sonnet-4-5-20250929" for better quality/reliability
        self.model = model or os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5")
        self.max_retries = max_retries
        self.graph = nx.MultiDiGraph()
        self.entity_cache = {}
        self.extraction_stats = {
            'chunks_processed': 0,
            'entities_extracted': 0,
            'relationships_extracted': 0,
            'errors': 0,
            'retries': 0,
            'successful_retries': 0
        }
        # Track failed chunks for later retry
        self.failed_chunks: List[Dict] = []
        # Track processed chunk hashes to avoid duplicates
        self.processed_chunks: Set[str] = set()
    
    def _get_chunk_hash(self, chunk_text: str, metadata: Dict) -> str:
        """Generate a unique hash for a chunk to track if it's been processed"""
        chunk_id = f"{metadata.get('filename', '')}:{metadata.get('chunk_id', '')}:{chunk_text[:100]}"
        return hashlib.md5(chunk_id.encode()).hexdigest()
    
    def extract_graph_from_chunk(self, chunk_text: str, metadata: Dict, retry_count: int = 0) -> Dict[str, Any]:
        """
        Extract entities and relationships from a chunk with retry logic
        
        Args:
            chunk_text: The text content of the chunk
            metadata: Metadata about the chunk
            retry_count: Current retry attempt (0 = first try)
        
        Returns:
            Dictionary with 'entities' and 'relationships' lists
        """
        # Skip if chunk is too short
        if len(chunk_text.strip()) < 50:
            return {'entities': [], 'relationships': []}
        
        prompt = f"""Analyze this text from a personal knowledge base and extract:

1. **Entities**: Important concepts, people, places, treatments, technologies, projects, etc.
2. **Relationships**: How these entities relate to each other

Text to analyze:
<text>
{chunk_text[:8000]}  # Limit to 8000 chars to avoid token limits
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
- Return ONLY the JSON object, no markdown code blocks, no explanations"""

        for attempt in range(self.max_retries):
            try:
                # Use longer max_tokens and lower temperature for better JSON reliability
                max_tokens = 6000 if retry_count > 0 else 4096  # More tokens on retry
                temperature = 0.1 if retry_count > 0 else 0.3  # Lower temp on retry for consistency
                
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }]
                )
                
                response_text = response.content[0].text.strip()
                
                # Try to parse with improved error handling
                graph_data = self._parse_json_response_improved(response_text, metadata, attempt)
                
                # Validate structure
                if 'entities' not in graph_data:
                    graph_data['entities'] = []
                if 'relationships' not in graph_data:
                    graph_data['relationships'] = []
                
                # Add source metadata
                for entity in graph_data.get('entities', []):
                    if 'properties' not in entity:
                        entity['properties'] = {}
                    if 'sources' not in entity['properties']:
                        entity['properties']['sources'] = []
                    entity['properties']['sources'].append({
                        'filename': metadata.get('filename', 'Unknown'),
                        'chunk_id': metadata.get('chunk_id', 'Unknown')
                    })
                
                for rel in graph_data.get('relationships', []):
                    if 'properties' not in rel:
                        rel['properties'] = {}
                    if 'sources' not in rel['properties']:
                        rel['properties']['sources'] = []
                    rel['properties']['sources'].append({
                        'filename': metadata.get('filename', 'Unknown'),
                        'chunk_id': metadata.get('chunk_id', 'Unknown')
                    })
                
                # Success!
                self.extraction_stats['chunks_processed'] += 1
                if retry_count > 0:
                    self.extraction_stats['successful_retries'] += 1
                self.extraction_stats['entities_extracted'] += len(graph_data.get('entities', []))
                self.extraction_stats['relationships_extracted'] += len(graph_data.get('relationships', []))
                
                return graph_data
                
            except Exception as e:
                error_msg = str(e)
                is_last_attempt = (attempt + 1) >= self.max_retries
                
                if is_last_attempt:
                    # Final attempt failed
                    self.extraction_stats['errors'] += 1
                    print(f"❌ Error extracting from chunk (after {self.max_retries} attempts): {error_msg[:100]}")
                    print(f"   📝 Source: {metadata.get('filename', 'Unknown')}")
                    
                    # Save failed chunk for later retry
                    self.failed_chunks.append({
                        'text': chunk_text,
                        'metadata': metadata,
                        'error': error_msg,
                        'attempts': retry_count + self.max_retries
                    })
                    
                    return {'entities': [], 'relationships': []}
                else:
                    # Retry with exponential backoff
                    self.extraction_stats['retries'] += 1
                    wait_time = (2 ** attempt) * 1  # 1s, 2s, 4s
                    print(f"⚠️  Attempt {attempt + 1}/{self.max_retries} failed: {error_msg[:80]}")
                    print(f"   Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
    
    def _parse_json_response_improved(self, response_text: str, metadata: Dict, attempt: int) -> Dict[str, Any]:
        """
        Improved JSON parsing with multiple recovery strategies
        """
        # Strategy 1: Remove markdown code blocks
        if response_text.startswith('```'):
            parts = response_text.split('```')
            for part in parts:
                part = part.strip()
                if part.startswith('json'):
                    part = part[4:].strip()
                if part.startswith('{'):
                    response_text = part
                    break
        
        # Strategy 2: Direct parse
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            pass
        
        # Strategy 3: Extract JSON object from text
        json_match = re.search(r'\{[\s\S]*\}', response_text, re.MULTILINE | re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Strategy 4: Fix common JSON issues
        fixed_text = self._fix_common_json_issues(response_text)
        if fixed_text != response_text:
            try:
                return json.loads(fixed_text)
            except json.JSONDecodeError:
                pass
        
        # Strategy 5: Extract entities and relationships separately
        try:
            entities = self._extract_entities_from_text(response_text)
            relationships = self._extract_relationships_from_text(response_text)
            if entities is not None or relationships is not None:
                return {
                    'entities': entities if entities is not None else [],
                    'relationships': relationships if relationships is not None else []
                }
        except Exception:
            pass
        
        # Strategy 6: Try to salvage partial JSON
        try:
            partial = self._salvage_partial_json(response_text)
            if partial:
                return partial
        except Exception:
            pass
        
        # All strategies failed
        raise ValueError(f"Could not parse JSON response after {attempt + 1} attempts")
    
    def _fix_common_json_issues(self, text: str) -> str:
        """Fix common JSON formatting issues"""
        # Fix trailing commas
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        
        # Fix unclosed strings (add quote at end of line if missing)
        lines = text.split('\n')
        fixed_lines = []
        for i, line in enumerate(lines):
            # If line has an unclosed string (starts with quote but doesn't end with quote before comma/brace)
            if '"' in line and not line.strip().endswith('"') and not line.strip().endswith('",'):
                # Try to close it
                if '":' in line and line.count('"') % 2 == 1:
                    # Unclosed string value
                    if not line.rstrip().endswith('"'):
                        line = line.rstrip() + '"'
            fixed_lines.append(line)
        text = '\n'.join(fixed_lines)
        
        # Fix single quotes to double quotes (basic cases)
        text = re.sub(r"'([^']*)':", r'"\1":', text)
        text = re.sub(r":\s*'([^']*)'", r': "\1"', text)
        
        return text
    
    def _extract_entities_from_text(self, text: str) -> Optional[List[Dict]]:
        """Try to extract entities list from malformed JSON"""
        # Look for entities array
        entities_match = re.search(r'"entities"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if entities_match:
            try:
                entities_str = '[' + entities_match.group(1) + ']'
                # Try to parse as JSON array
                entities = json.loads(entities_str)
                if isinstance(entities, list):
                    return entities
            except:
                pass
        return None
    
    def _extract_relationships_from_text(self, text: str) -> Optional[List[Dict]]:
        """Try to extract relationships list from malformed JSON"""
        # Look for relationships array
        rels_match = re.search(r'"relationships"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if rels_match:
            try:
                rels_str = '[' + rels_match.group(1) + ']'
                relationships = json.loads(rels_str)
                if isinstance(relationships, list):
                    return relationships
            except:
                pass
        return None
    
    def _salvage_partial_json(self, text: str) -> Optional[Dict]:
        """Try to salvage partial JSON by finding complete structures"""
        # Find the largest valid JSON object we can extract
        depth = 0
        start = -1
        for i, char in enumerate(text):
            if char == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0 and start >= 0:
                    try:
                        return json.loads(text[start:i+1])
                    except:
                        pass
        return None
    
    def add_to_graph(self, graph_data: Dict[str, Any]):
        """Add extracted entities and relationships to the graph"""
        # Add entities as nodes
        for entity in graph_data.get('entities', []):
            entity_name = entity.get('name', '').strip()
            if not entity_name:
                continue
            
            # Get entity properties
            entity_props = entity.get('properties', {})
            entity_type = entity_props.get('entity_type', entity.get('type', 'concept'))
            
            # Add or update node
            if self.graph.has_node(entity_name):
                # Merge properties, preserving existing sources
                existing = self.graph.nodes[entity_name]
                existing_sources = existing.get('sources', [])
                new_sources = entity_props.get('sources', [])
                # Merge sources lists (avoid duplicates)
                merged_sources = existing_sources + [s for s in new_sources if s not in existing_sources]
                existing['sources'] = merged_sources
                # Update other properties
                for key, value in entity_props.items():
                    if key != 'sources' and key not in existing:
                        existing[key] = value
            else:
                self.graph.add_node(entity_name, entity_type=entity_type, **entity_props)
                # Cache entity name for normalization
                self.entity_cache[entity_name.lower()] = entity_name
        
        # Add relationships as edges
        for rel in graph_data.get('relationships', []):
            source = rel.get('source', '').strip()
            target = rel.get('target', '').strip()
            rel_type = rel.get('type', 'relates_to')
            
            if not source or not target:
                continue
            
            # Normalize entity names using cache
            source_norm = self.entity_cache.get(source.lower(), source)
            target_norm = self.entity_cache.get(target.lower(), target)
            
            # Ensure nodes exist
            if source_norm not in self.graph:
                self.graph.add_node(source_norm, entity_type='unknown')
                self.entity_cache[source_norm.lower()] = source_norm
            if target_norm not in self.graph:
                self.graph.add_node(target_norm, entity_type='unknown')
                self.entity_cache[target_norm.lower()] = target_norm
            
            # Add edge with properties
            rel_props = rel.get('properties', {})
            self.graph.add_edge(source_norm, target_norm, relationship_type=rel_type, **rel_props)
    
    def build_graph_from_chunks(self, chunks: List[Dict], batch_size: int = 10, 
                                skip_processed: bool = True):
        """
        Build graph from chunks with improved error handling
        
        Args:
            chunks: List of {'text': str, 'metadata': dict}
            batch_size: Save checkpoint every N chunks
            skip_processed: Skip chunks that have already been processed (by hash)
        """
        total = len(chunks)
        self.failed_chunks = []  # Reset failed chunks list
        
        print(f"\n🏗️  Processing {total} chunks with improved error handling...")
        print(f"   Model: {self.model}")
        print(f"   Max retries: {self.max_retries}")
        print(f"   Skip already processed: {skip_processed}\n")
        
        for i, chunk in enumerate(chunks):
            chunk_hash = self._get_chunk_hash(chunk['text'], chunk['metadata'])
            
            # Skip if already processed
            if skip_processed and chunk_hash in self.processed_chunks:
                continue
            
            print(f"Processing chunk {i+1}/{total}...", end=' ')
            
            graph_data = self.extract_graph_from_chunk(
                chunk['text'],
                chunk['metadata']
            )
            
            self.add_to_graph(graph_data)
            self.processed_chunks.add(chunk_hash)
            
            # Show progress
            if graph_data.get('entities') or graph_data.get('relationships'):
                print(f"✅ ({len(graph_data.get('entities', []))} entities, {len(graph_data.get('relationships', []))} relationships)")
            else:
                print("⚠️  (no data extracted)")
            
            # Save checkpoint
            if (i + 1) % batch_size == 0:
                checkpoint_path = GRAPH_DATA_DIR / f"graph_checkpoint_{i+1}.pkl"
                self.save_graph(str(checkpoint_path))
                print(f"   💾 Checkpoint saved")
        
        print(f"\n✅ Processing complete!")
        print(f"   Successful: {self.extraction_stats['chunks_processed']}")
        print(f"   Errors: {self.extraction_stats['errors']}")
        print(f"   Retries: {self.extraction_stats['retries']}")
        print(f"   Successful retries: {self.extraction_stats['successful_retries']}")
        
        if self.failed_chunks:
            print(f"\n⚠️  {len(self.failed_chunks)} chunks failed and can be retried")
            failed_file = GRAPH_DATA_DIR / "failed_chunks.pkl"
            with open(failed_file, 'wb') as f:
                pickle.dump(self.failed_chunks, f)
            print(f"   Failed chunks saved to: {failed_file}")
    
    def retry_failed_chunks(self, failed_chunks_file: str = None, use_sonnet: bool = False):
        """
        Retry chunks that failed during initial processing
        
        Args:
            failed_chunks_file: Path to failed_chunks.pkl (defaults to graph_data/failed_chunks.pkl)
            use_sonnet: Use Claude Sonnet for retry (more reliable but more expensive)
        """
        if failed_chunks_file is None:
            failed_chunks_file = str(GRAPH_DATA_DIR / "failed_chunks.pkl")
        
        if not Path(failed_chunks_file).exists():
            print(f"❌ Failed chunks file not found: {failed_chunks_file}")
            return
        
        print("=" * 70)
        print("🔄 RETRYING FAILED CHUNKS")
        print("=" * 70)
        
        with open(failed_chunks_file, 'rb') as f:
            failed_chunks = pickle.load(f)
        
        print(f"\n📊 Found {len(failed_chunks)} failed chunks to retry")
        
        if use_sonnet:
            original_model = self.model
            self.model = "claude-sonnet-4-5-20250929"
            print(f"   Using Claude Sonnet for better reliability (more expensive)")
        
        retry_success = 0
        retry_failed = 0
        
        for i, chunk_data in enumerate(failed_chunks):
            print(f"\nRetrying chunk {i+1}/{len(failed_chunks)}...")
            print(f"   Source: {chunk_data['metadata'].get('filename', 'Unknown')}")
            print(f"   Previous attempts: {chunk_data.get('attempts', 0)}")
            
            graph_data = self.extract_graph_from_chunk(
                chunk_data['text'],
                chunk_data['metadata'],
                retry_count=chunk_data.get('attempts', 0)
            )
            
            if graph_data.get('entities') or graph_data.get('relationships'):
                self.add_to_graph(graph_data)
                retry_success += 1
                print(f"   ✅ Success! ({len(graph_data.get('entities', []))} entities)")
            else:
                retry_failed += 1
                print(f"   ❌ Still failed")
        
        if use_sonnet:
            self.model = original_model
        
        print(f"\n📊 Retry Results:")
        print(f"   Successful: {retry_success}")
        print(f"   Still failed: {retry_failed}")
    
    def load_graph(self, filepath: str = None):
        """Load existing graph (maintains compatibility)"""
        if filepath is None:
            filepath = str(GRAPH_DATA_DIR / "knowledge_graph.pkl")
        
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
            self.graph = data['graph']
            # Load stats and ensure all keys exist (for compatibility with old graphs)
            loaded_stats = data.get('stats', {})
            self.extraction_stats = {
                'chunks_processed': loaded_stats.get('chunks_processed', 0),
                'entities_extracted': loaded_stats.get('entities_extracted', 0),
                'relationships_extracted': loaded_stats.get('relationships_extracted', 0),
                'errors': loaded_stats.get('errors', 0),
                'retries': loaded_stats.get('retries', 0),  # New field
                'successful_retries': loaded_stats.get('successful_retries', 0)  # New field
            }
            # Load processed chunks if available
            if 'processed_chunks' in data:
                self.processed_chunks = set(data['processed_chunks'])
            # Rebuild entity cache from graph nodes
            self.entity_cache = {name.lower(): name for name in self.graph.nodes()}
            print(f"✅ Loaded graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
            print(f"   Already processed: {self.extraction_stats.get('chunks_processed', 0)} chunks")
    
    def save_graph(self, filepath: str = None):
        """Save graph with processed chunks tracking"""
        if filepath is None:
            filepath = str(GRAPH_DATA_DIR / "knowledge_graph.pkl")
        
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'wb') as f:
            pickle.dump({
                'graph': self.graph,
                'stats': self.extraction_stats,
                'processed_chunks': list(self.processed_chunks),
                'timestamp': datetime.now().isoformat()
            }, f)
        print(f"💾 Graph saved to {filepath}")
    
    def export_graph_json(self, filepath: str = None):
        """Export graph to JSON (same as original)"""
        if filepath is None:
            filepath = str(GRAPH_DATA_DIR / "knowledge_graph.json")
        
        graph_data = {
            'nodes': [
                {
                    'id': node,
                    'type': data.get('entity_type', 'unknown'),
                    **{k: v for k, v in data.items() if k != 'entity_type'}
                }
                for node, data in self.graph.nodes(data=True)
            ],
            'edges': [
                {
                    'source': u,
                    'target': v,
                    'type': data.get('relationship_type', 'relates_to'),
                    **{k: v for k, v in data.items() if k != 'relationship_type'}
                }
                for u, v, data in self.graph.edges(data=True)
            ],
            'stats': self.extraction_stats
        }
        
        import json
        with open(filepath, 'w') as f:
            json.dump(graph_data, f, indent=2)
        print(f"📄 Graph exported to {filepath}")

