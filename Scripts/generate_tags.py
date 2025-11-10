#!/usr/bin/env python3
"""
Generate Tags - Suggest relevant tags using knowledge graph, semantic search, and content analysis.

For each note:
- Query knowledge graph for related entities
- Use semantic search to find similar notes and their tags
- Analyze content for domain, topic, and type tags
- Generate tag suggestions (5-10 tags per note)
- Preserve existing tags, add new ones
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set
import pickle
import os

# Try to import optional dependencies
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

try:
    from claude_graph_builder import ClaudeGraphBuilder
    GRAPH_BUILDER_AVAILABLE = True
except ImportError:
    GRAPH_BUILDER_AVAILABLE = False


def parse_frontmatter(content: str) -> tuple[Dict | None, str]:
    """Extract frontmatter from markdown content."""
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(frontmatter_pattern, content, re.DOTALL)
    
    if not match:
        return None, content
    
    frontmatter_text = match.group(1)
    body = match.group(2)
    
    try:
        import yaml
        frontmatter = yaml.safe_load(frontmatter_text)
        # Ensure frontmatter is a dict, not a string or other type
        if frontmatter is None:
            frontmatter = {}
        elif not isinstance(frontmatter, dict):
            # If YAML parsed to a non-dict (e.g., string), treat as no frontmatter
            return None, content
        return frontmatter, body
    except Exception:
        return None, content


def load_knowledge_graph(graph_path: str) -> Optional[object]:
    """Load knowledge graph from pickle file."""
    if not GRAPH_BUILDER_AVAILABLE:
        return None
    
    try:
        graph_file = Path(graph_path)
        if not graph_file.exists():
            # Try default locations
            script_dir = Path(__file__).parent.parent
            default_paths = [
                script_dir / "graph_data" / "knowledge_graph_full.pkl",
                script_dir / "graph_data" / "knowledge_graph_test.pkl",
                script_dir / "graph_data" / "knowledge_graph.pkl",
            ]
            for path in default_paths:
                if path.exists():
                    graph_file = path
                    break
        
        if not graph_file.exists():
            return None
        
        builder = ClaudeGraphBuilder(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
        builder.load_graph(str(graph_file))
        return builder
    except Exception as e:
        print(f"Warning: Could not load knowledge graph: {e}", file=sys.stderr)
        return None


def query_graph_for_entities(builder: object, filename: str, content: str) -> List[str]:
    """Query knowledge graph for entities related to this note."""
    if not builder or not hasattr(builder, 'graph'):
        return []
    
    try:
        graph = builder.graph
        entities = []
        
        # Search for nodes that might be related
        filename_lower = filename.lower()
        content_lower = content.lower()[:500]  # First 500 chars
        
        # Check if any graph nodes appear in filename or content
        for node in graph.nodes():
            node_lower = str(node).lower()
            if node_lower in filename_lower or node_lower in content_lower:
                entities.append(str(node))
        
        # Also check neighbors of matching nodes
        for node in graph.nodes():
            node_lower = str(node).lower()
            if node_lower in filename_lower or node_lower in content_lower:
                neighbors = list(graph.neighbors(node))
                entities.extend([str(n) for n in neighbors[:5]])  # Limit neighbors
        
        return list(set(entities))[:10]  # Return unique, limit to 10
    except Exception:
        return []


def query_chromadb_for_similar_notes(chroma_db_path: str, filename: str, content: str, n_results: int = 5) -> List[Dict]:
    """Query ChromaDB for similar notes and extract their tags."""
    if not CHROMADB_AVAILABLE:
        return []
    
    try:
        client = chromadb.PersistentClient(path=chroma_db_path)
        
        # Try to get collection
        collection = None
        for name in ['obsidian_vault', 'documents', 'knowledge_base', 'vault']:
            try:
                collection = client.get_collection(name=name)
                break
            except:
                continue
        
        if not collection:
            return []
        
        # Generate embedding for content (simple approach - use first 500 chars)
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        query_text = content[:500] if len(content) > 500 else content
        query_embedding = model.encode(query_text).tolist()
        
        # Query
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=['metadatas', 'documents']
        )
        
        similar_notes = []
        if results['metadatas'] and len(results['metadatas']) > 0:
            for meta in results['metadatas'][0]:
                similar_notes.append(meta)
        
        return similar_notes
    except Exception as e:
        print(f"Warning: ChromaDB query failed: {e}", file=sys.stderr)
        return []


def extract_tags_from_similar_notes(similar_notes: List[Dict]) -> List[str]:
    """Extract tags from similar notes' metadata."""
    tags = []
    for note in similar_notes:
        note_tags = note.get('tags', [])
        if isinstance(note_tags, list):
            tags.extend([str(t) for t in note_tags])
        elif note_tags:
            tags.append(str(note_tags))
    return list(set(tags))  # Remove duplicates


def detect_content_type(filename: str, content: str) -> str:
    """Detect the primary content type of the note."""
    filename_lower = filename.lower()
    content_lower = content.lower()[:500]  # First 500 chars for efficiency
    
    # Recipe/cooking indicators
    recipe_indicators = ['recipe', 'cook', 'ingredient', 'serving', 'prep time', 'cook time', 'oven', 'bake', 'fry', 'sauté', 'simmer', 'boil', 'recipe', 'cuisine', 'dish', 'meal']
    if any(indicator in filename_lower or indicator in content_lower for indicator in recipe_indicators):
        return 'recipe'
    
    # Medical/health indicators
    medical_indicators = ['treatment', 'diagnosis', 'symptom', 'patient', 'doctor', 'hospital', 'lymphoma', 'cancer', 'therapy', 'medication']
    if any(indicator in filename_lower or indicator in content_lower for indicator in medical_indicators):
        return 'medical'
    
    # Tech/programming indicators
    tech_indicators = ['code', 'programming', 'function', 'class', 'import', 'api', 'github', 'git', 'python', 'swift', 'javascript', 'software', 'development']
    if any(indicator in filename_lower or indicator in content_lower for indicator in tech_indicators):
        return 'tech'
    
    # Hardware/electronics indicators
    hardware_indicators = ['esp32', 'raspberry pi', 'arduino', 'circuit', 'electronics', 'sensor', 'microcontroller', 'gpio', 'pin']
    if any(indicator in filename_lower or indicator in content_lower for indicator in hardware_indicators):
        return 'hardware'
    
    # AI/ML indicators
    ai_indicators = ['machine learning', 'llm', 'gpt', 'claude', 'rag', 'embedding', 'vector', 'neural', 'model', 'training']
    if any(indicator in filename_lower or indicator in content_lower for indicator in ai_indicators):
        return 'ai'
    
    return 'general'


def analyze_content_for_tags(filename: str, content: str) -> List[str]:
    """Analyze content to extract domain, topic, and type tags with relevance filtering."""
    tags = []
    filename_lower = filename.lower()
    content_lower = content.lower()
    content_type = detect_content_type(filename, content)
    
    # Domain tags (only if content type matches)
    domain_keywords = {
        'medical': {
            'keywords': ['medical', 'health', 'treatment', 'therapy', 'diagnosis', 'symptom', 'disease', 'patient', 'doctor', 'hospital', 'lymphoma', 'cancer'],
            'min_matches': 2  # Require at least 2 keywords
        },
        'tech': {
            'keywords': ['code', 'programming', 'software', 'development', 'api', 'github', 'git', 'python', 'swift', 'javascript', 'function', 'class'],
            'min_matches': 2
        },
        'hardware': {
            'keywords': ['esp32', 'raspberry pi', 'arduino', 'circuit', 'electronics', 'sensor', 'microcontroller', 'gpio'],
            'min_matches': 1
        },
        'home-automation': {
            'keywords': ['home assistant', 'homekit', 'smart home', 'automation', 'zigbee', 'thread', 'matter'],
            'min_matches': 1
        },
        'ai': {
            'keywords': ['machine learning', 'llm', 'gpt', 'claude', 'rag', 'embedding', 'vector', 'neural network'],
            'min_matches': 2  # Require stronger signal for AI
        },
        'cooking': {
            'keywords': ['recipe', 'cook', 'ingredient', 'serving', 'prep time', 'cook time', 'oven', 'bake', 'fry', 'cuisine', 'dish', 'meal'],
            'min_matches': 1
        }
    }
    
    # Exclude domains based on content type
    excluded_domains = {
        'recipe': ['tech', 'ai', 'hardware', 'medical'],  # Recipes shouldn't get tech/ai tags
        'medical': ['tech', 'ai', 'hardware', 'cooking'],
        'tech': ['cooking', 'medical'],
        'hardware': ['cooking', 'medical'],
        'ai': ['cooking', 'medical', 'hardware'],
        'general': []
    }
    
    excluded = excluded_domains.get(content_type, [])
    
    for domain, config in domain_keywords.items():
        if domain in excluded:
            continue
        
        keywords = config['keywords']
        min_matches = config['min_matches']
        
        matches = sum(1 for keyword in keywords if keyword in filename_lower or keyword in content_lower)
        if matches >= min_matches:
            tags.append(domain)
    
    # Type tags (more strict matching)
    type_keywords = {
        'project': {
            'keywords': ['project', 'setup', 'install', 'configure', 'build'],
            'min_matches': 2,
            'exclude_for': ['recipe', 'medical']  # Recipes/medical notes rarely are "projects"
        },
        'tutorial': {
            'keywords': ['tutorial', 'guide', 'how to', 'step by step', 'instructions'],
            'min_matches': 1,
            'exclude_for': []
        },
        'reference': {
            'keywords': ['reference', 'cheatsheet', 'documentation', 'api', 'specification'],
            'min_matches': 2,  # Require stronger signal
            'exclude_for': ['recipe']  # Recipes aren't "reference" docs
        },
        'main': {
            'keywords': ['main course', 'main dish'],  # Only if explicitly mentioned as "main course"
            'min_matches': 1,
            'exclude_for': ['recipe', 'tech', 'ai', 'hardware', 'medical']  # "main" is too generic - exclude from all
        },
        'meeting': {
            'keywords': ['meeting', 'agenda', 'minutes', 'attendees'],
            'min_matches': 2,  # Require multiple indicators
            'exclude_for': ['recipe', 'medical', 'tech', 'hardware']  # Very specific to meetings
        },
        'question': {
            'keywords': ['question', 'questions', 'faq', 'q&a'],
            'min_matches': 2,  # Require multiple indicators
            'exclude_for': ['recipe']  # Recipes aren't Q&A
        },
        'recipe': {
            'keywords': ['recipe', 'ingredient', 'serving', 'prep', 'cook time'],
            'min_matches': 1,
            'exclude_for': []
        }
    }
    
    for note_type, config in type_keywords.items():
        if content_type in config.get('exclude_for', []):
            continue
        
        keywords = config['keywords']
        min_matches = config['min_matches']
        
        matches = sum(1 for keyword in keywords if keyword in filename_lower or keyword in content_lower)
        if matches >= min_matches:
            tags.append(note_type)
    
    # Extract key terms (capitalized words, technical terms)
    # Find capitalized words that might be entities
    capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', content[:1000])
    # Filter out common words
    common_words = {'The', 'This', 'That', 'These', 'Those', 'There', 'Here', 'When', 'Where', 'What', 'How', 'Why', 'Note', 'Notes', 'Main', 'Idea', 'References'}
    key_terms = [w.lower() for w in capitalized_words if w not in common_words and len(w) > 3]
    tags.extend(key_terms[:5])  # Add top 5 key terms
    
    return list(set(tags))  # Remove duplicates


def find_backlink_moc(note_file_path: Path, moc_list: List[Dict], vault_root: Path) -> Optional[str]:
    """Find which MoC links to this note (backlink)."""
    # Get note name without extension
    note_name = note_file_path.stem
    note_basename = note_file_path.name
    note_relative = note_file_path.relative_to(vault_root)
    note_relative_str = str(note_relative).replace('\\', '/')
    
    for moc_info in moc_list:
        moc_path = vault_root / moc_info['file']
        if not moc_path.exists():
            continue
        
        try:
            moc_content = moc_path.read_text(encoding='utf-8')
            # Check multiple variations of the note link
            # 1. Exact note name: [[Note Name]]
            if f"[[{note_name}]]" in moc_content:
                moc_filename = Path(moc_info['file']).stem
                return moc_filename
            
            # 2. With extension: [[Note Name.md]]
            if f"[[{note_basename}]]" in moc_content:
                moc_filename = Path(moc_info['file']).stem
                return moc_filename
            
            # 3. Relative path: [[path/to/Note Name]]
            if f"[[{note_relative_str}]]" in moc_content:
                moc_filename = Path(moc_info['file']).stem
                return moc_filename
            
            # 4. Just the filename part (in case of subdirectories)
            if '/' in note_relative_str:
                note_dir_part = note_relative_str.rsplit('/', 1)[0]
                if f"[[{note_dir_part}/{note_name}]]" in moc_content:
                    moc_filename = Path(moc_info['file']).stem
                    return moc_filename
        except Exception:
            continue
    
    return None


def generate_tags_for_note(
    file_path: Path,
    vault_root: Path,
    graph_builder: Optional[object],
    chroma_db_path: Optional[str],
    moc_list: Optional[List[Dict]] = None
) -> Dict:
    """Generate tag suggestions for a single note."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'error': str(e),
            'suggested_tags': [],
            'suggested_backlink': None
        }
    
    frontmatter, body = parse_frontmatter(content)
    filename = file_path.name
    
    # Find backlink MoC
    suggested_backlink = None
    if moc_list:
        suggested_backlink = find_backlink_moc(file_path, moc_list, vault_root)
    
    # Get existing tags
    existing_tags = []
    if frontmatter:
        tags_raw = frontmatter.get('tags', [])
        if isinstance(tags_raw, list):
            existing_tags = [str(t).lower() for t in tags_raw]
        elif tags_raw:
            existing_tags = [str(tags_raw).lower()]
    
    # Generate tag suggestions from multiple sources
    suggested_tags = []
    
    # 1. From knowledge graph
    if graph_builder:
        entities = query_graph_for_entities(graph_builder, filename, body)
        suggested_tags.extend([e.lower() for e in entities[:5]])
    
    # 2. From ChromaDB similar notes (optional, skip if ChromaDB has issues)
    if chroma_db_path:
        try:
            similar_notes = query_chromadb_for_similar_notes(chroma_db_path, filename, body)
            similar_tags = extract_tags_from_similar_notes(similar_notes)
            suggested_tags.extend([t.lower() for t in similar_tags[:5]])
        except Exception as e:
            # ChromaDB may have issues, continue without it
            pass
    
    # 3. From content analysis
    content_tags = analyze_content_for_tags(filename, body)
    suggested_tags.extend([t.lower() for t in content_tags])
    
    # Combine and deduplicate
    all_suggested = list(set(suggested_tags))
    
    # Remove existing tags from suggestions
    new_tags = [t for t in all_suggested if t not in existing_tags]
    
    # Limit to 10 tags total (existing + new)
    final_tags = existing_tags + new_tags[:10]
    
    return {
        'file': str(file_path.relative_to(vault_root)),
        'filename': filename,
        'existing_tags': existing_tags,
        'suggested_tags': new_tags[:10],
        'final_tags': final_tags[:10],
        'suggested_backlink': suggested_backlink,
        'sources': {
            'from_graph': len([t for t in new_tags if t in [e.lower() for e in (query_graph_for_entities(graph_builder, filename, body) if graph_builder else [])]]),
            'from_similar_notes': len([t for t in new_tags if t in [t2.lower() for t2 in extract_tags_from_similar_notes(query_chromadb_for_similar_notes(chroma_db_path, filename, body) if chroma_db_path else [])]]),
            'from_content_analysis': len([t for t in new_tags if t in [t2.lower() for t2 in content_tags]])
        }
    }


def generate_tags_for_all_notes(
    notes_list_path: str,
    vault_path: str,
    graph_path: Optional[str] = None,
    chroma_db_path: Optional[str] = None,
    moc_list_path: Optional[str] = None,
    output_path: str = 'tag_suggestions.json'
) -> Dict:
    """Generate tag suggestions for all notes."""
    vault_root = Path(vault_path)
    
    # Load notes list
    with open(notes_list_path, 'r', encoding='utf-8') as f:
        notes_list = json.load(f)
    
    # Load MoC list for backlink identification
    moc_list = None
    if moc_list_path and Path(moc_list_path).exists():
        with open(moc_list_path, 'r', encoding='utf-8') as f:
            moc_list = json.load(f)
        print(f"Loaded {len(moc_list)} MoCs for backlink identification")
    else:
        # Try default location
        default_moc_list = vault_root.parent / 'obsidian_rag' / 'moc_list.json'
        if default_moc_list.exists():
            with open(default_moc_list, 'r', encoding='utf-8') as f:
                moc_list = json.load(f)
            print(f"Loaded {len(moc_list)} MoCs from default location")
    
    print(f"Generating tags for {len(notes_list)} notes")
    
    # Load knowledge graph if available
    graph_builder = None
    if graph_path:
        print("Loading knowledge graph...")
        graph_builder = load_knowledge_graph(graph_path)
        if graph_builder:
            print(f"✅ Loaded graph: {graph_builder.graph.number_of_nodes()} nodes")
        else:
            print("⚠️  Could not load knowledge graph")
    
    # Check ChromaDB if available (skip if not provided or corrupted)
    if chroma_db_path:
        if not Path(chroma_db_path).exists():
            print(f"⚠️  ChromaDB path does not exist: {chroma_db_path}")
            chroma_db_path = None
        else:
            # Try to initialize ChromaDB to check for corruption
            # Use a separate process or just skip if it panics
            try:
                import chromadb
                # Wrap in try-except to catch panics
                try:
                    test_client = chromadb.PersistentClient(path=chroma_db_path)
                    # Test query to ensure it works
                    collections = test_client.list_collections()
                    print("✅ ChromaDB available")
                except (Exception, SystemError) as e:
                    # Catch both Python exceptions and Rust panics
                    print(f"⚠️  ChromaDB has issues (corruption?), will skip: {str(e)[:100]}")
                    chroma_db_path = None
            except ImportError:
                print("⚠️  ChromaDB not installed, will skip")
                chroma_db_path = None
    else:
        print("ℹ️  ChromaDB not specified, skipping similar note tag suggestions")
    
    # Generate tags for each note
    results = []
    for i, note_info in enumerate(notes_list, 1):
        if i % 50 == 0:
            print(f"  Processed {i}/{len(notes_list)} notes...")
        
        file_path = vault_root / note_info['file']
        if not file_path.exists():
            continue
        
        result = generate_tags_for_note(file_path, vault_root, graph_builder, chroma_db_path, moc_list)
        results.append(result)
    
    # Save results
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Summary
    total_new_tags = sum(len(r.get('suggested_tags', [])) for r in results)
    notes_with_suggestions = sum(1 for r in results if r.get('suggested_tags'))
    notes_with_backlinks = sum(1 for r in results if r.get('suggested_backlink'))
    
    print("\n" + "="*70)
    print("TAG GENERATION SUMMARY")
    print("="*70)
    print(f"Total notes: {len(results)}")
    print(f"Notes with tag suggestions: {notes_with_suggestions}")
    print(f"Total new tags suggested: {total_new_tags}")
    print(f"Notes with backlink suggestions: {notes_with_backlinks}")
    print(f"\nResults saved to: {output_path}")
    print("="*70)
    
    return {
        'total_notes': len(results),
        'notes_with_suggestions': notes_with_suggestions,
        'total_new_tags': total_new_tags,
        'results': results
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate tag suggestions for notes')
    parser.add_argument(
        '--notes-list',
        type=str,
        required=True,
        help='Path to notes list JSON file (from identify_mocs.py or vault_analyzer.py)'
    )
    parser.add_argument(
        '--vault-path',
        type=str,
        default=os.getenv('OBSIDIAN_VAULT_PATH', '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel'),
        help='Path to Obsidian vault'
    )
    parser.add_argument(
        '--graph-path',
        type=str,
        help='Path to knowledge graph pickle file (optional)'
    )
    parser.add_argument(
        '--chroma-db-path',
        type=str,
        default=None,
        help='Path to ChromaDB directory (optional, will skip if not provided or corrupted)'
    )
    parser.add_argument(
        '--moc-list',
        type=str,
        help='Path to MoC list JSON file (for backlink identification)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='tag_suggestions.json',
        help='Output path for tag suggestions JSON'
    )
    
    args = parser.parse_args()
    
    try:
        generate_tags_for_all_notes(
            args.notes_list,
            args.vault_path,
            args.graph_path,
            args.chroma_db_path,
            args.moc_list,
            args.output
        )
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

