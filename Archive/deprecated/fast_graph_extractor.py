#!/usr/bin/env python3
"""
Fast Knowledge Graph Extractor for Obsidian Vault
Uses simple entity extraction without complex relationship mapping
Much faster than full LightRAG approach
"""

import os
import json
import asyncio
import requests
from pathlib import Path
from typing import List, Set, Dict
import re

VAULT_PATH = "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
OLLAMA_HOST = "http://localhost:11434"
MODEL = "llama3.2:3b"
GRAPH_OUTPUT = "./knowledge_graph.json"

# Simple entity extraction prompt
ENTITY_PROMPT = """Extract key entities from this text. List ONLY the most important:
- People (names)
- Places (locations, cities, countries)
- Organizations (companies, institutions)
- Concepts (key ideas, topics)
- Products/Technologies

Text:
{text}

Output format (one per line):
ENTITY_TYPE: entity name

Example:
PERSON: John Smith
PLACE: New York
CONCEPT: Machine Learning
"""

class FastGraphExtractor:
    def __init__(self):
        self.entities = {}  # {entity: {type, count, docs}}
        self.entity_cooccurrence = {}  # Simple relationships
        
    async def extract_entities_from_text(self, text: str, doc_id: str) -> List[Dict]:
        """Extract entities using simple LLM call"""
        # Truncate long text
        text = text[:2000]  # Only first 2000 chars for speed
        
        prompt = ENTITY_PROMPT.format(text=text)
        
        try:
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json={
                    "model": MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_ctx": 2048}
                },
                timeout=30  # Fast timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                output = result.get("response", "")
                return self.parse_entities(output, doc_id)
            else:
                print(f"⚠️  Error from Ollama: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"⚠️  Error extracting entities: {e}")
            return []
    
    def parse_entities(self, output: str, doc_id: str) -> List[Dict]:
        """Parse entity output"""
        entities = []
        lines = output.strip().split('\n')
        
        for line in lines:
            if ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    entity_type = parts[0].strip().upper()
                    entity_name = parts[1].strip()
                    
                    if entity_name and len(entity_name) > 2:
                        entities.append({
                            'type': entity_type,
                            'name': entity_name,
                            'doc': doc_id
                        })
        
        return entities
    
    def add_entities(self, entities: List[Dict], doc_id: str):
        """Add entities to graph"""
        doc_entities = []
        
        for entity in entities:
            name = entity['name'].lower()
            entity_type = entity['type']
            
            if name not in self.entities:
                self.entities[name] = {
                    'name': entity['name'],  # Keep original case
                    'type': entity_type,
                    'count': 0,
                    'docs': set()
                }
            
            self.entities[name]['count'] += 1
            self.entities[name]['docs'].add(doc_id)
            doc_entities.append(name)
        
        # Simple co-occurrence (entities in same doc are related)
        for i, e1 in enumerate(doc_entities):
            for e2 in doc_entities[i+1:]:
                pair = tuple(sorted([e1, e2]))
                if pair not in self.entity_cooccurrence:
                    self.entity_cooccurrence[pair] = 0
                self.entity_cooccurrence[pair] += 1
    
    def save_graph(self):
        """Save graph to JSON"""
        # Convert sets to lists for JSON
        entities_json = {}
        for key, value in self.entities.items():
            entities_json[key] = {
                'name': value['name'],
                'type': value['type'],
                'count': value['count'],
                'docs': list(value['docs'])
            }
        
        graph = {
            'entities': entities_json,
            'relationships': [
                {
                    'entity1': pair[0],
                    'entity2': pair[1],
                    'cooccurrence': count
                }
                for pair, count in self.entity_cooccurrence.items()
                if count > 1  # Only keep relationships appearing multiple times
            ]
        }
        
        with open(GRAPH_OUTPUT, 'w') as f:
            json.dump(graph, f, indent=2)
        
        print(f"\n✅ Graph saved to {GRAPH_OUTPUT}")
        print(f"   Entities: {len(self.entities)}")
        print(f"   Relationships: {len(graph['relationships'])}")


async def main():
    print("="*60)
    print("Fast Knowledge Graph Extraction")
    print("="*60)
    print()
    
    extractor = FastGraphExtractor()
    vault_path = Path(VAULT_PATH)
    
    # Get all markdown files
    md_files = list(vault_path.rglob("*.md"))
    
    # Filter out unwanted directories
    exclude_patterns = ['.obsidian', '.trash', 'Templates', 'Excalidraw']
    md_files = [
        f for f in md_files 
        if not any(pattern in str(f) for pattern in exclude_patterns)
    ]
    
    print(f"📚 Found {len(md_files)} markdown files")
    print(f"🤖 Using model: {MODEL}")
    print()
    
    processed = 0
    skipped = 0
    
    for i, md_file in enumerate(md_files):
        if i % 50 == 0:
            print(f"Progress: {i}/{len(md_files)} files ({i*100//len(md_files)}%)")
            print(f"  Entities so far: {len(extractor.entities)}")
        
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            if len(content) < 50:  # Skip very short files
                skipped += 1
                continue
            
            doc_id = str(md_file.relative_to(vault_path))
            entities = await extractor.extract_entities_from_text(content, doc_id)
            
            if entities:
                extractor.add_entities(entities, doc_id)
                processed += 1
            else:
                skipped += 1
                
        except Exception as e:
            print(f"⚠️  Error processing {md_file.name}: {e}")
            skipped += 1
    
    print()
    print("="*60)
    print(f"✅ Processing complete!")
    print(f"   Processed: {processed} files")
    print(f"   Skipped: {skipped} files")
    print("="*60)
    
    extractor.save_graph()


if __name__ == "__main__":
    asyncio.run(main())

