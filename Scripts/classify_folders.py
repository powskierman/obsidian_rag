#!/usr/bin/env python3
"""
Classify Folders - Suggest appropriate folders based on content analysis, knowledge graph, and existing folder patterns.

For each note:
- Analyze content and metadata
- Check existing folder location
- Query knowledge graph for related notes
- Use semantic similarity to find notes in similar folders
- Suggest target folder based on content domain, note type, and existing patterns
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
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


def analyze_content_for_domain(filename: str, content: str, tags: List[str]) -> str:
    """Determine content domain from filename, content, and tags."""
    filename_lower = filename.lower()
    content_lower = content.lower()[:1000]  # First 1000 chars
    tags_lower = [t.lower() for t in tags]
    
    # Medical domain
    medical_keywords = ['medical', 'health', 'treatment', 'therapy', 'diagnosis', 'symptom', 'disease', 
                       'patient', 'doctor', 'hospital', 'lymphoma', 'cancer', 'medication', 'prescription']
    if any(kw in filename_lower or kw in content_lower or kw in tags_lower for kw in medical_keywords):
        return 'Medical'
    
    # Tech domain
    tech_keywords = ['code', 'programming', 'software', 'development', 'api', 'github', 'git', 
                    'python', 'swift', 'javascript', 'tech', 'technology']
    if any(kw in filename_lower or kw in content_lower or kw in tags_lower for kw in tech_keywords):
        return 'Tech'
    
    # Hardware domain
    hardware_keywords = ['esp32', 'raspberry pi', 'arduino', 'circuit', 'electronics', 'sensor', 
                        'microcontroller', 'hardware']
    if any(kw in filename_lower or kw in content_lower or kw in tags_lower for kw in hardware_keywords):
        return 'Tech'  # Hardware is under Tech
    
    # Home Automation
    ha_keywords = ['home assistant', 'homekit', 'smart home', 'automation', 'zigbee', 'thread', 'matter']
    if any(kw in filename_lower or kw in content_lower or kw in tags_lower for kw in ha_keywords):
        return 'Tech'
    
    # AI domain
    ai_keywords = ['ai', 'machine learning', 'llm', 'gpt', 'claude', 'rag', 'embedding', 'vector']
    if any(kw in filename_lower or kw in content_lower or kw in tags_lower for kw in ai_keywords):
        return 'Tech'
    
    # Personal/Important Documents
    personal_keywords = ['important', 'banking', 'insurance', 'mortgage', 'passport', 'license', 'tax']
    if any(kw in filename_lower or kw in content_lower or kw in tags_lower for kw in personal_keywords):
        return 'Important Documents'
    
    # Books/Reading
    book_keywords = ['book', 'ebook', 'reading', 'kobo', 'barnes']
    if any(kw in filename_lower or kw in content_lower or kw in tags_lower for kw in book_keywords):
        return 'Books'
    
    # Recipes
    recipe_keywords = ['recipe', 'cooking', 'baking', 'coffee', 'espresso', 'dessert']
    if any(kw in filename_lower or kw in content_lower or kw in tags_lower for kw in recipe_keywords):
        return 'Recipes'
    
    return 'Unclassified'


def find_similar_notes_in_folders(chroma_db_path: Optional[str], filename: str, content: str, n_results: int = 5) -> List[Dict]:
    """Find similar notes and their folder locations."""
    if not CHROMADB_AVAILABLE or not chroma_db_path:
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
        
        # Generate embedding
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
                filepath = meta.get('filepath', '')
                if filepath:
                    similar_notes.append({
                        'filepath': filepath,
                        'folder': str(Path(filepath).parent) if filepath else ''
                    })
        
        return similar_notes
    except Exception:
        return []


def suggest_folder_for_note(
    file_path: Path,
    vault_root: Path,
    graph_builder: Optional[object],
    chroma_db_path: Optional[str]
) -> Dict:
    """Suggest appropriate folder for a note."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'error': str(e),
            'suggested_folder': None
        }
    
    frontmatter, body = parse_frontmatter(content)
    filename = file_path.name
    current_folder = str(file_path.parent.relative_to(vault_root))
    
    # Extract tags
    tags = []
    if frontmatter:
        tags_raw = frontmatter.get('tags', [])
        if isinstance(tags_raw, list):
            tags = [str(t) for t in tags_raw]
        elif tags_raw:
            tags = [str(tags_raw)]
    
    # Determine domain
    domain = analyze_content_for_domain(filename, body, tags)
    
    # Find similar notes and their folders
    similar_notes = find_similar_notes_in_folders(chroma_db_path, filename, body)
    
    # Analyze folder patterns from similar notes
    folder_votes = {}
    for note in similar_notes:
        folder = note.get('folder', '')
        if folder and folder != '.':
            folder_votes[folder] = folder_votes.get(folder, 0) + 1
    
    # Suggest folder based on domain and similar notes
    suggested_folder = None
    
    if domain == 'Medical':
        suggested_folder = 'Medical'
        # Check for subfolder hints
        if 'lymphoma' in filename.lower() or 'lymphoma' in body.lower():
            suggested_folder = 'Medical/Lymphoma'
    elif domain == 'Tech':
        suggested_folder = 'Tech'
        # Check for subfolder hints
        if 'ai' in filename.lower() or 'rag' in filename.lower() or any('ai' in t.lower() or 'rag' in t.lower() for t in tags):
            suggested_folder = 'Tech/AI'
        elif 'home assistant' in body.lower() or 'homekit' in body.lower():
            suggested_folder = 'Tech/Electronics/Software/Home-Assistant'
        elif 'esp' in filename.lower() or 'esp32' in body.lower():
            suggested_folder = 'Tech/Electronics/Hardware/ESP'
    elif domain == 'Important Documents':
        suggested_folder = 'Important Documents'
    elif domain == 'Books':
        suggested_folder = 'Books'
    elif domain == 'Recipes':
        suggested_folder = 'Recipes'
    
    # If similar notes suggest a different folder, consider it
    if folder_votes:
        most_common_folder = max(folder_votes.items(), key=lambda x: x[1])[0]
        if folder_votes[most_common_folder] >= 2:  # At least 2 similar notes
            suggested_folder = most_common_folder
    
    # If no suggestion, keep current folder
    if not suggested_folder:
        suggested_folder = current_folder
    
    # Normalize folder path (remove leading/trailing slashes, handle relative paths)
    if suggested_folder.startswith('/'):
        suggested_folder = suggested_folder[1:]
    if suggested_folder == '.':
        suggested_folder = ''
    
    return {
        'file': str(file_path.relative_to(vault_root)),
        'filename': filename,
        'current_folder': current_folder,
        'suggested_folder': suggested_folder,
        'domain': domain,
        'reason': f"Domain: {domain}" + (f", Similar notes in: {most_common_folder}" if folder_votes else ""),
        'folder_change_needed': current_folder != suggested_folder
    }


def classify_folders_for_all_notes(
    notes_list_path: str,
    vault_path: str,
    graph_path: Optional[str] = None,
    chroma_db_path: Optional[str] = None,
    output_path: str = 'folder_suggestions.json'
) -> Dict:
    """Classify folders for all notes."""
    vault_root = Path(vault_path)
    
    # Load notes list
    with open(notes_list_path, 'r', encoding='utf-8') as f:
        notes_list = json.load(f)
    
    print(f"Classifying folders for {len(notes_list)} notes")
    
    # Load knowledge graph if available
    graph_builder = None
    if graph_path:
        print("Loading knowledge graph...")
        try:
            from claude_graph_builder import ClaudeGraphBuilder
            graph_file = Path(graph_path)
            if not graph_file.exists():
                script_dir = Path(__file__).parent.parent
                default_paths = [
                    script_dir / "graph_data" / "knowledge_graph_full.pkl",
                    script_dir / "graph_data" / "knowledge_graph_test.pkl",
                ]
                for path in default_paths:
                    if path.exists():
                        graph_file = path
                        break
            
            if graph_file.exists():
                builder = ClaudeGraphBuilder(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))
                builder.load_graph(str(graph_file))
                graph_builder = builder
                print(f"✅ Loaded graph: {graph_builder.graph.number_of_nodes()} nodes")
        except Exception as e:
            print(f"⚠️  Could not load knowledge graph: {e}")
    
    # Check ChromaDB if available
    if chroma_db_path and not Path(chroma_db_path).exists():
        print(f"⚠️  ChromaDB path does not exist: {chroma_db_path}")
        chroma_db_path = None
    
    # Classify folders for each note
    results = []
    for i, note_info in enumerate(notes_list, 1):
        if i % 50 == 0:
            print(f"  Processed {i}/{len(notes_list)} notes...")
        
        file_path = vault_root / note_info['file']
        if not file_path.exists():
            continue
        
        result = suggest_folder_for_note(file_path, vault_root, graph_builder, chroma_db_path)
        results.append(result)
    
    # Save results
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Summary
    notes_needing_move = sum(1 for r in results if r.get('folder_change_needed', False))
    
    print("\n" + "="*70)
    print("FOLDER CLASSIFICATION SUMMARY")
    print("="*70)
    print(f"Total notes: {len(results)}")
    print(f"Notes needing folder change: {notes_needing_move}")
    print(f"\nResults saved to: {output_path}")
    print("="*70)
    
    return {
        'total_notes': len(results),
        'notes_needing_move': notes_needing_move,
        'results': results
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Classify folders for notes')
    parser.add_argument(
        '--notes-list',
        type=str,
        required=True,
        help='Path to notes list JSON file'
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
        default='./chroma_db',
        help='Path to ChromaDB directory (optional)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='folder_suggestions.json',
        help='Output path for folder suggestions JSON'
    )
    
    args = parser.parse_args()
    
    try:
        classify_folders_for_all_notes(
            args.notes_list,
            args.vault_path,
            args.graph_path,
            args.chroma_db_path,
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

