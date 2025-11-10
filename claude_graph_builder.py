"""
Claude-Powered Knowledge Graph Builder for Obsidian Vault

This service uses Claude API to extract entities and relationships from your
Obsidian vault chunks, building a queryable knowledge graph.
"""

import json
import os
import re
import time
import hashlib
import logging
from typing import List, Dict, Any, Optional, Union, Set
from anthropic import Anthropic
import networkx as nx
from pathlib import Path
import pickle
from datetime import datetime

# Configure logging
# If logging is not configured, set up basic config
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)

# Graph data directory
GRAPH_DATA_DIR = Path("graph_data")
# Try to create directory, but don't fail if filesystem is read-only
# The directory will be created when actually needed (e.g., when saving graph)
try:
    GRAPH_DATA_DIR.mkdir(exist_ok=True)
except OSError:
    # Directory creation failed (e.g., read-only filesystem)
    # This is OK - we'll handle it when actually trying to save
    pass


class ClaudeGraphBuilder:
    """Build knowledge graph using Claude's reasoning capabilities"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = None, max_retries: int = 3):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=self.api_key)
        # Default to Haiku 4.5 for cost savings, but allow override via env var or parameter
        # Use "claude-sonnet-4-5-20250929" for better quality if needed
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

    def add_entity(self, name: str, entity_type: str = "unknown", **properties):
        """Add a single entity to the graph (convenience method for testing)"""
        # Handle 'properties' dict if passed
        props = properties.pop('properties', {})
        # Merge properties dict with other kwargs
        all_props = {**props, **properties}

        # If entity exists, update it
        if self.graph.has_node(name):
            existing = self.graph.nodes[name]
            for key, value in all_props.items():
                existing[key] = value
        else:
            # Add new entity
            self.graph.add_node(name, entity_type=entity_type, **all_props)
            self.entity_cache[name.lower()] = name

    def add_relationship(self, source: str, target: str, relationship_type: str = "relates_to", **properties):
        """Add a single relationship to the graph (convenience method for testing)"""
        # Ensure both entities exist
        if not self.graph.has_node(source):
            self.add_entity(source)
        if not self.graph.has_node(target):
            self.add_entity(target)

        # Store relationship type as 'relationship' key for compatibility with tests
        self.graph.add_edge(source, target, relationship=relationship_type, **properties)

    def clean_entity_name(self, name: str) -> str:
        """Clean entity name by removing extra whitespace and newlines"""
        import re
        # Remove leading/trailing whitespace
        cleaned = name.strip()
        # Replace multiple whitespace/newlines with single space
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned

    def merge_graph(self, other_graph: nx.MultiDiGraph):
        """Merge another graph into this one"""
        # Add all nodes from other graph
        for node, data in other_graph.nodes(data=True):
            if self.graph.has_node(node):
                # Merge properties if node exists
                existing = self.graph.nodes[node]
                for key, value in data.items():
                    if key not in existing:
                        existing[key] = value
            else:
                # Add new node
                self.graph.add_node(node, **data)
                self.entity_cache[node.lower()] = node

        # Add all edges from other graph
        for source, target, data in other_graph.edges(data=True):
            self.graph.add_edge(source, target, **data)

    def _get_chunk_hash(self, chunk_text: str, metadata: Dict) -> str:
        """Generate a unique hash for a chunk to track if it's been processed"""
        chunk_id = f"{metadata.get('filename', '')}:{metadata.get('chunk_id', '')}:{chunk_text[:100]}"
        return hashlib.md5(chunk_id.encode()).hexdigest()

    def extract_graph_from_chunk(self, chunk_text: str, metadata: Dict, retry_count: int = 0) -> Dict[str, Any]:
        """
        Use Claude to extract entities and relationships from a single chunk with retry logic
        
        Args:
            chunk_text: The text content of the chunk
            metadata: Metadata about the chunk
            retry_count: Current retry attempt (0 = first try)
        
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
                # Use longer max_tokens and lower temperature for better JSON reliability on retry
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
                graph_data = self._parse_json_response(response_text, metadata, attempt)
                
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
                    logger.error(f"Error extracting from chunk (after {self.max_retries} attempts): {error_msg[:100]}")
                    logger.error(f"Source: {metadata.get('filename', 'Unknown')}")
                    
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
                    logger.warning(f"Attempt {attempt + 1}/{self.max_retries} failed: {error_msg[:80]}")
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
    
    def _parse_json_response(self, response_text: str, metadata: Dict, attempt: int = 0) -> Dict[str, Any]:
        """
        Robustly parse JSON response from Claude, handling common malformation issues
        Uses multiple recovery strategies for maximum reliability
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
            original_error = e
            pass
        
        # Strategy 3: Extract JSON object from text
        json_match = re.search(r'\{[\s\S]*\}', response_text, re.MULTILINE | re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Strategy 4: Fix common JSON issues
        try:
            fixed_text = self._fix_common_json_issues(response_text)
            if fixed_text != response_text:
                return json.loads(fixed_text)
        except (json.JSONDecodeError, Exception):
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
        
        # Strategy 7: Try existing repair methods (backward compatibility)
        try:
            fixed_text = self._repair_json_strings(response_text)
            if fixed_text != response_text:
                return json.loads(fixed_text)
        except (json.JSONDecodeError, Exception):
            pass
        
        try:
            partial_json = self._extract_complete_json(response_text)
            if partial_json:
                return json.loads(partial_json)
        except (json.JSONDecodeError, Exception):
            pass
        
        try:
            entities = self._extract_entities_list(response_text)
            relationships = self._extract_relationships_list(response_text)
            if entities is not None or relationships is not None:
                return {
                    'entities': entities if entities is not None else [],
                    'relationships': relationships if relationships is not None else []
                }
        except Exception:
            pass
        
        # All strategies failed
        error_pos = original_error.pos if hasattr(original_error, 'pos') else 'unknown'
        logger.warning(f"Could not parse JSON response (char {error_pos})")
        logger.debug(f"Response preview (first 500 chars): {response_text[:500]}")
        if error_pos != 'unknown' and isinstance(error_pos, int):
            # Show context around the error
            start = max(0, error_pos - 100)
            end = min(len(response_text), error_pos + 100)
            logger.debug(f"Context around error: {response_text[start:end]}")
        raise ValueError(f"Malformed JSON response from Claude: {original_error}")
    
    def _repair_json_strings(self, text: str) -> str:
        """Try to repair unterminated strings in JSON"""
        # Find all string values and ensure they're properly closed
        # This is a simple heuristic - find patterns like "key": "value that might be unterminated
        result = []
        i = 0
        in_string = False
        escape_next = False
        
        while i < len(text):
            char = text[i]
            
            if escape_next:
                result.append(char)
                escape_next = False
                i += 1
                continue
            
            if char == '\\':
                result.append(char)
                escape_next = True
                i += 1
                continue
            
            if char == '"':
                if in_string:
                    # Check if this is the end of the string (followed by : or , or } or ])
                    lookahead = i + 1
                    while lookahead < len(text) and text[lookahead] in ' \t\n\r':
                        lookahead += 1
                    if lookahead < len(text) and text[lookahead] in ':,\\]}':
                        in_string = False
                        result.append(char)
                    else:
                        # Might be an escaped quote or part of the string
                        result.append(char)
                else:
                    in_string = True
                    result.append(char)
            else:
                result.append(char)
            
            i += 1
        
        # If we ended in a string, try to close it
        if in_string:
            result.append('"')
        
        return ''.join(result)
    
    def _extract_complete_json(self, text: str) -> Optional[str]:
        """Extract a complete JSON object by matching braces"""
        start = text.find('{')
        if start == -1:
            return None
        
        brace_count = 0
        in_string = False
        escape_next = False
        
        for i in range(start, len(text)):
            char = text[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
            elif not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return text[start:i+1]
        
        return None
    
    def _extract_entities_list(self, text: str) -> Optional[List]:
        """Try to extract entities array from malformed JSON"""
        # Look for "entities": [ ... ]
        match = re.search(r'"entities"\s*:\s*\[', text)
        if not match:
            return None
        
        # Try to find the closing bracket
        start = match.end()
        bracket_count = 1
        in_string = False
        escape_next = False
        
        for i in range(start, len(text)):
            char = text[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
            elif not in_string:
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        array_text = text[match.start():i+1]
                        # Try to extract just the array part
                        array_match = re.search(r'\[[\s\S]*\]', array_text)
                        if array_match:
                            try:
                                # Wrap in a JSON object to parse
                                wrapped = '{"entities": ' + array_match.group() + '}'
                                parsed = json.loads(wrapped)
                                return parsed.get('entities', [])
                            except:
                                pass
                        break
        
        return None
    
    def _extract_relationships_list(self, text: str) -> Optional[List]:
        """Try to extract relationships array from malformed JSON"""
        # Look for "relationships": [ ... ]
        match = re.search(r'"relationships"\s*:\s*\[', text)
        if not match:
            return None
        
        # Try to find the closing bracket
        start = match.end()
        bracket_count = 1
        in_string = False
        escape_next = False
        
        for i in range(start, len(text)):
            char = text[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
            elif not in_string:
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        array_text = text[match.start():i+1]
                        # Try to extract just the array part
                        array_match = re.search(r'\[[\s\S]*\]', array_text)
                        if array_match:
                            try:
                                # Wrap in a JSON object to parse
                                wrapped = '{"relationships": ' + array_match.group() + '}'
                                parsed = json.loads(wrapped)
                                return parsed.get('relationships', [])
                            except:
                                pass
                        break
        
        return None
    
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
        """Add extracted entities and relationships to the NetworkX graph"""
        
        # Add entities as nodes
        for entity in graph_data.get('entities', []):
            # Skip if missing required fields
            if 'name' not in entity:
                continue
                
            entity_name = entity['name']
            entity_type = entity.get('type', 'unknown')
            entity_props = entity.get('properties', {})
            
            # If entity exists, merge properties
            if self.graph.has_node(entity_name):
                existing = self.graph.nodes[entity_name]
                # Merge sources
                existing_sources = existing.get('sources', [])
                new_sources = entity_props.get('sources', [])
                existing['sources'] = existing_sources + new_sources
                # Update other properties if needed
                for key, value in entity_props.items():
                    if key != 'sources' and key not in existing:
                        existing[key] = value
            else:
                # Add new entity
                self.graph.add_node(
                    entity_name,
                    entity_type=entity_type,
                    **entity_props
                )
                self.entity_cache[entity_name.lower()] = entity_name
        
        # Add relationships as edges
        for rel in graph_data.get('relationships', []):
            # Skip if missing required fields
            if 'source' not in rel or 'target' not in rel:
                continue
                
            source = rel['source']
            target = rel['target']
            rel_type = rel.get('type', 'relates_to')  # Default to 'relates_to' if missing
            rel_props = rel.get('properties', {})
            
            # Normalize entity names using cache
            source_norm = self.entity_cache.get(source.lower(), source)
            target_norm = self.entity_cache.get(target.lower(), target)
            
            # Only add edge if both entities exist
            if self.graph.has_node(source_norm) and self.graph.has_node(target_norm):
                self.graph.add_edge(
                    source_norm,
                    target_norm,
                    relationship_type=rel_type,
                    **rel_props
                )
    
    def build_graph_from_chunks(self, chunks: List[Dict], batch_size: int = 10, skip_processed: bool = True):
        """
        Build graph from multiple chunks with improved error handling
        
        Args:
            chunks: List of {'text': str, 'metadata': dict}
            batch_size: Save checkpoint every N chunks
            skip_processed: Skip chunks that have already been processed (by hash)
        """
        total = len(chunks)
        self.failed_chunks = []  # Reset failed chunks list
        
        logger.info(f"Processing {total} chunks with improved error handling...")
        logger.info(f"Model: {self.model}")
        logger.info(f"Max retries: {self.max_retries}")
        logger.info(f"Skip already processed: {skip_processed}")
        
        for i, chunk in enumerate(chunks):
            chunk_hash = self._get_chunk_hash(chunk['text'], chunk['metadata'])
            
            # Skip if already processed
            if skip_processed and chunk_hash in self.processed_chunks:
                continue
            
            logger.debug(f"Processing chunk {i+1}/{total}...")
            
            graph_data = self.extract_graph_from_chunk(
                chunk['text'],
                chunk['metadata']
            )
            
            self.add_to_graph(graph_data)
            self.processed_chunks.add(chunk_hash)
            
            # Show progress
            if graph_data.get('entities') or graph_data.get('relationships'):
                logger.info(f"Chunk {i+1}/{total}: {len(graph_data.get('entities', []))} entities, {len(graph_data.get('relationships', []))} relationships")
            else:
                logger.warning(f"Chunk {i+1}/{total}: no data extracted")
            
            # Save checkpoint
            if (i + 1) % batch_size == 0:
                checkpoint_path = GRAPH_DATA_DIR / f"graph_checkpoint_{i+1}.pkl"
                self.save_graph(str(checkpoint_path))
                logger.info(f"Checkpoint saved at chunk {i+1}")
        
        logger.info("Processing complete!")
        logger.info(f"Successful: {self.extraction_stats['chunks_processed']}")
        logger.info(f"Errors: {self.extraction_stats['errors']}")
        logger.info(f"Retries: {self.extraction_stats['retries']}")
        logger.info(f"Successful retries: {self.extraction_stats['successful_retries']}")
        logger.info(f"Graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        
        if self.failed_chunks:
            logger.warning(f"{len(self.failed_chunks)} chunks failed and can be retried")
            failed_file = GRAPH_DATA_DIR / "failed_chunks.pkl"
            try:
                with open(failed_file, 'wb') as f:
                    pickle.dump(self.failed_chunks, f)
                logger.info(f"Failed chunks saved to: {failed_file}")
            except OSError:
                logger.warning(f"Could not save failed chunks (read-only filesystem)")
    
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
            logger.error(f"Failed chunks file not found: {failed_chunks_file}")
            return
        
        logger.info("=" * 70)
        logger.info("RETRYING FAILED CHUNKS")
        logger.info("=" * 70)
        
        with open(failed_chunks_file, 'rb') as f:
            failed_chunks = pickle.load(f)
        
        logger.info(f"Found {len(failed_chunks)} failed chunks to retry")
        
        if use_sonnet:
            original_model = self.model
            self.model = "claude-sonnet-4-5-20250929"
            logger.info("Using Claude Sonnet for better reliability (more expensive)")
        
        retry_success = 0
        retry_failed = 0
        
        for i, chunk_data in enumerate(failed_chunks):
            logger.info(f"Retrying chunk {i+1}/{len(failed_chunks)}...")
            logger.debug(f"Source: {chunk_data['metadata'].get('filename', 'Unknown')}")
            logger.debug(f"Previous attempts: {chunk_data.get('attempts', 0)}")
            
            graph_data = self.extract_graph_from_chunk(
                chunk_data['text'],
                chunk_data['metadata'],
                retry_count=chunk_data.get('attempts', 0)
            )
            
            if graph_data.get('entities') or graph_data.get('relationships'):
                self.add_to_graph(graph_data)
                retry_success += 1
                logger.info(f"Chunk {i+1} success: {len(graph_data.get('entities', []))} entities")
            else:
                retry_failed += 1
                logger.warning(f"Chunk {i+1} still failed")
        
        if use_sonnet:
            self.model = original_model
        
        logger.info("Retry Results:")
        logger.info(f"Successful: {retry_success}")
        logger.info(f"Still failed: {retry_failed}")
    
    def save_graph(self, filepath: str = None):
        """Save graph to disk"""
        if filepath is None:
            filepath = str(GRAPH_DATA_DIR / "knowledge_graph.pkl")
        elif not Path(filepath).is_absolute() and not filepath.startswith("graph_data/"):
            # If relative path doesn't include graph_data, add it
            filepath = str(GRAPH_DATA_DIR / Path(filepath).name)
        
        # Ensure directory exists before saving
        file_path = Path(filepath)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'wb') as f:
            pickle.dump({
                'graph': self.graph,
                'stats': self.extraction_stats,
                'processed_chunks': list(self.processed_chunks),
                'timestamp': datetime.now().isoformat()
            }, f)
        logger.info(f"Graph saved to {filepath}")
    
    def load_graph(self, filepath: str = None):
        """Load graph from disk"""
        if filepath is None:
            filepath = str(GRAPH_DATA_DIR / "knowledge_graph.pkl")
        elif not Path(filepath).is_absolute() and not filepath.startswith("graph_data/"):
            # If relative path doesn't include graph_data, try graph_data first
            graph_data_path = GRAPH_DATA_DIR / Path(filepath).name
            if graph_data_path.exists():
                filepath = str(graph_data_path)
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
            logger.info(f"Graph loaded: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
            logger.info(f"Already processed: {self.extraction_stats.get('chunks_processed', 0)} chunks")
    
    def export_graph_json(self, filepath: str = None):
        """Export graph to JSON for visualization"""
        if filepath is None:
            filepath = str(GRAPH_DATA_DIR / "knowledge_graph.json")
        elif not Path(filepath).is_absolute() and not filepath.startswith("graph_data/"):
            # If relative path doesn't include graph_data, add it
            filepath = str(GRAPH_DATA_DIR / Path(filepath).name)
        
        # Ensure directory exists before saving
        file_path = Path(filepath)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
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
        
        logger.info(f"Graph exported to {filepath}")


class ClaudeGraphQuerier:
    """Query the knowledge graph using Claude's reasoning"""
    
    def __init__(self, graph_builder: ClaudeGraphBuilder, api_key: Optional[str] = None, model: str = None):
        self.graph = graph_builder.graph
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        # Default to Haiku 4.5 for cost savings, but allow override via env var or parameter
        # Use "claude-sonnet-4-5-20250929" for better quality if needed
        self.model = model or os.environ.get("CLAUDE_QUERY_MODEL", "claude-haiku-4-5")
    
    def find_paths(self, source: str, target: str, max_depth: int = 3) -> List[List[str]]:
        """Find paths between two entities (handles directed graph with bidirectional search)"""
        # Clean up entity names
        source = source.strip().strip('"\'')
        target = target.strip().strip('"\'')
        
        # Find source and target entities (with fuzzy matching like get_entity_neighborhood)
        def find_best_match(entity_name):
            entity_lower = entity_name.lower()
            matches = [n for n in self.graph.nodes() if entity_lower in n.lower() or n.lower() in entity_lower]
            if matches:
                return max(matches, key=lambda n: self.graph.degree(n))
            return None
        
        source_entity = find_best_match(source) if source not in self.graph else source
        target_entity = find_best_match(target) if target not in self.graph else target
        
        if not source_entity or not target_entity:
            return []
        
        if source_entity == target_entity:
            return [[source_entity]]
        
        all_paths = []
        
        # Try forward paths (following edge direction)
        try:
            forward_paths = list(nx.all_simple_paths(self.graph, source_entity, target_entity, cutoff=max_depth))
            all_paths.extend(forward_paths[:10])
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass
        except Exception:
            pass
        
        # Try reverse paths (going backwards through edges)
        try:
            reverse_paths = list(nx.all_simple_paths(self.graph.reverse(copy=False), source_entity, target_entity, cutoff=max_depth))
            # Reverse the path back to forward direction for display
            reverse_paths = [list(reversed(p)) for p in reverse_paths]
            all_paths.extend(reverse_paths[:10])
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass
        except Exception:
            pass
        
        # If no directed paths, try undirected (ignoring edge direction)
        if not all_paths:
            try:
                undirected = self.graph.to_undirected()
                undirected_paths = list(nx.all_simple_paths(undirected, source_entity, target_entity, cutoff=max_depth))
                all_paths.extend(undirected_paths[:10])
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                pass
            except Exception:
                pass
        
        # Remove duplicates and return
        seen = set()
        unique_paths = []
        for path in all_paths:
            path_tuple = tuple(path)
            if path_tuple not in seen:
                seen.add(path_tuple)
                unique_paths.append(path)
        
        return unique_paths[:10]
    
    def get_entity_neighborhood(self, entity: str, depth: int = 1) -> Dict[str, Any]:
        """Get entities connected to this entity"""
        # Clean up entity name (remove quotes, extra spaces)
        entity = entity.strip().strip('"\'')
        entity_lower = entity.lower()
        
        # Find all potential matches (even if exact match exists, there might be a better one)
        matches = [n for n in self.graph.nodes() if entity_lower in n.lower() or n.lower() in entity_lower]
        
        if not matches:
            return {'entity': entity, 'found': False}
        
        # Always prefer the match with most connections (most important entity)
        # This handles cases like "Principal Residence Exemption" matching both
        # "Principal Residence Exemption" (2 connections) and 
        # "Principal Residence Exemption (PRE)" (15 connections)
        entity = max(matches, key=lambda n: self.graph.degree(n))
        
        # Get neighbors
        neighbors = {
            'entity': entity,
            'found': True,  # Explicitly mark as found
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
            model=self.model,
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
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Example usage
    logger.info("Claude Graph Builder - Example Usage")
    logger.info("=" * 50)
    
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
    logger.info("1. Building graph from chunks...")
    # builder.build_graph_from_chunks(example_chunks)
    
    # Save graph
    # builder.save_graph("my_knowledge_graph.pkl")
    
    # Load existing graph
    # builder.load_graph("my_knowledge_graph.pkl")
    
    # Query the graph
    logger.info("2. Querying the graph...")
    # querier = ClaudeGraphQuerier(builder)
    # answer = querier.query_with_claude("How does CAR-T therapy work for lymphoma?")
    # logger.info(answer)
    
    logger.info("Ready to process your vault!")
