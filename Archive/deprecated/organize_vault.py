#!/usr/bin/env python3
"""
Vault Organization Tool
Uses vector search to analyze notes and suggest tags/directory organization
"""

import os
import sys
import json
import requests
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
import argparse

# Default embedding service URL
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")

def get_all_documents(service_url: str = None) -> List[Dict]:
    """Get all documents from ChromaDB with metadata"""
    service_url = service_url or EMBEDDING_SERVICE_URL
    
    try:
        # Get stats first
        stats_response = requests.get(f"{service_url}/stats", timeout=10)
        if stats_response.status_code != 200:
            print(f"❌ Could not get stats: {stats_response.status_code}")
            return []
        
        stats = stats_response.json()
        total_docs = stats.get('total_documents', 0)
        print(f"📊 Found {total_docs} documents in database")
        
        if total_docs == 0:
            return []
        
        # Query with a very broad query to get all documents
        # We'll use a generic query and request many results
        query_response = requests.post(
            f"{service_url}/query",
            json={
                "query": "document note file",
                "n_results": min(total_docs, 1000),  # Get up to 1000 documents
                "reranking": False,
                "deduplicate": True
            },
            timeout=30
        )
        
        if query_response.status_code != 200:
            print(f"❌ Query failed: {query_response.status_code}")
            return []
        
        results = query_response.json()
        documents = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        
        # Combine into document list
        doc_list = []
        for doc, meta in zip(documents, metadatas):
            doc_list.append({
                'text': doc,
                'metadata': meta,
                'filepath': meta.get('filepath', ''),
                'filename': meta.get('filename', ''),
            })
        
        return doc_list
    
    except Exception as e:
        print(f"❌ Error getting documents: {e}")
        return []

def analyze_content_for_tags(text: str, filename: str) -> List[str]:
    """Analyze content to suggest tags"""
    text_lower = text.lower()
    filename_lower = filename.lower()
    
    suggested_tags = []
    
    # Common tag patterns
    tag_patterns = {
        '#medical': ['medical', 'health', 'doctor', 'treatment', 'diagnosis', 'symptom', 'disease', 'medicine', 'hospital', 'patient'],
        '#book-notes': ['book', 'author', 'reading', 'chapter', 'quote', 'highlight', 'kindle'],
        '#project': ['project', 'task', 'todo', 'deadline', 'milestone', 'deliverable'],
        '#tech': ['code', 'programming', 'software', 'hardware', 'technology', 'computer', 'algorithm', 'api', 'software'],
        '#electronics': ['esp32', 'arduino', 'sensor', 'circuit', 'wiring', 'gpio', 'microcontroller', 'iot'],
        '#home-automation': ['home assistant', 'smart home', 'automation', 'hass', 'zigbee', 'z-wave', 'mqtt'],
        '#finance': ['tax', 'investment', 'capital gain', 'principal residence', 'income', 'deduction', 'irs', 'financial'],
        '#cooking': ['recipe', 'cooking', 'ingredient', 'kitchen', 'food', 'meal', 'cuisine'],
        '#travel': ['travel', 'trip', 'vacation', 'hotel', 'flight', 'destination', 'itinerary'],
        '#photography': ['photo', 'camera', 'lens', 'aperture', 'shutter', 'iso', 'photography'],
    }
    
    # Check for tag matches
    for tag, keywords in tag_patterns.items():
        if any(keyword in text_lower or keyword in filename_lower for keyword in keywords):
            suggested_tags.append(tag)
    
    # Check for existing tags in text
    import re
    existing_tags = re.findall(r'#[\w-]+', text)
    suggested_tags.extend(existing_tags)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in suggested_tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    
    return unique_tags[:5]  # Limit to 5 tags

def suggest_directory(text: str, filename: str, current_path: str) -> str:
    """Suggest appropriate directory based on content"""
    text_lower = text.lower()
    filename_lower = filename.lower()
    current_path_lower = current_path.lower()
    
    # Directory mapping based on content
    directory_suggestions = {
        'Medical': ['medical', 'health', 'doctor', 'treatment', 'diagnosis', 'symptom', 'disease', 'medicine', 'hospital', 'patient', 'lymphoma', 'cancer'],
        'Books': ['book', 'author', 'reading', 'chapter', 'quote', 'highlight', 'kindle', 'readwise'],
        'Tech/Electronics': ['esp32', 'arduino', 'sensor', 'circuit', 'wiring', 'gpio', 'microcontroller', 'iot', 'electronics'],
        'Tech/Software': ['code', 'programming', 'software', 'algorithm', 'api', 'python', 'javascript', 'development'],
        'Tech/Home-Assistant': ['home assistant', 'smart home', 'automation', 'hass', 'zigbee', 'z-wave', 'mqtt'],
        'Finance': ['tax', 'investment', 'capital gain', 'principal residence', 'income', 'deduction', 'irs', 'financial', 'pre'],
        'Recipes': ['recipe', 'cooking', 'ingredient', 'kitchen', 'food', 'meal', 'cuisine'],
        'Travel': ['travel', 'trip', 'vacation', 'hotel', 'flight', 'destination', 'itinerary'],
        'Photography': ['photo', 'camera', 'lens', 'aperture', 'shutter', 'iso', 'photography'],
        'Projects': ['project', 'task', 'todo', 'deadline', 'milestone'],
    }
    
    # Score each directory
    scores = {}
    for directory, keywords in directory_suggestions.items():
        score = sum(1 for keyword in keywords if keyword in text_lower or keyword in filename_lower)
        if score > 0:
            scores[directory] = score
    
    if scores:
        # Return highest scoring directory
        best_dir = max(scores.items(), key=lambda x: x[1])[0]
        return best_dir
    
    return None

def analyze_vault(vault_path: str, service_url: str = None) -> Dict:
    """Analyze vault and suggest organization"""
    print("🔍 Analyzing vault...")
    print()
    
    # Get all documents
    documents = get_all_documents(service_url)
    
    if not documents:
        print("❌ No documents found. Make sure indexing is complete.")
        return {}
    
    # Analyze each document
    analysis = {
        'untagged_files': [],
        'tag_suggestions': defaultdict(list),
        'directory_suggestions': defaultdict(list),
        'files_by_category': defaultdict(list),
    }
    
    print(f"📄 Analyzing {len(documents)} documents...")
    print()
    
    for i, doc in enumerate(documents, 1):
        filepath = doc.get('filepath', '')
        filename = doc.get('filename', '')
        text = doc.get('text', '')
        metadata = doc.get('metadata', {})
        
        if not filepath or not filename:
            continue
        
        # Get current directory
        current_dir = str(Path(filepath).parent) if filepath else ''
        
        # Check for existing tags
        existing_tags = metadata.get('tags', '')
        if not existing_tags or existing_tags == 'default':
            # Suggest tags
            suggested_tags = analyze_content_for_tags(text[:500], filename)  # Use first 500 chars
            if suggested_tags:
                analysis['untagged_files'].append({
                    'filepath': filepath,
                    'filename': filename,
                    'suggested_tags': suggested_tags
                })
                for tag in suggested_tags:
                    analysis['tag_suggestions'][tag].append(filename)
        
        # Suggest directory
        suggested_dir = suggest_directory(text[:500], filename, current_dir)
        if suggested_dir:
            # Only suggest if different from current
            if suggested_dir.lower() not in current_dir.lower():
                analysis['directory_suggestions'][suggested_dir].append({
                    'filepath': filepath,
                    'filename': filename,
                    'current_path': current_dir
                })
                analysis['files_by_category'][suggested_dir].append(filename)
    
    return analysis

def print_analysis(analysis: Dict, vault_path: str):
    """Print analysis results"""
    print("=" * 70)
    print("📊 VAULT ORGANIZATION ANALYSIS")
    print("=" * 70)
    print()
    
    # Untagged files
    untagged = analysis.get('untagged_files', [])
    if untagged:
        print(f"🏷️  UNTAGGED FILES ({len(untagged)} files)")
        print("-" * 70)
        for item in untagged[:20]:  # Show first 20
            print(f"  📄 {item['filename']}")
            print(f"     Suggested tags: {', '.join(item['suggested_tags'])}")
            print()
        if len(untagged) > 20:
            print(f"  ... and {len(untagged) - 20} more files")
        print()
    
    # Tag suggestions
    tag_suggestions = analysis.get('tag_suggestions', {})
    if tag_suggestions:
        print(f"🏷️  TAG SUGGESTIONS")
        print("-" * 70)
        for tag, files in sorted(tag_suggestions.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"  {tag}: {len(files)} files")
            if len(files) <= 5:
                for filename in files:
                    print(f"     - {filename}")
            else:
                for filename in files[:3]:
                    print(f"     - {filename}")
                print(f"     ... and {len(files) - 3} more")
            print()
    
    # Directory suggestions
    dir_suggestions = analysis.get('directory_suggestions', {})
    if dir_suggestions:
        print(f"📁 DIRECTORY SUGGESTIONS")
        print("-" * 70)
        for directory, files in sorted(dir_suggestions.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"  📂 {directory} ({len(files)} files)")
            for item in files[:5]:  # Show first 5
                current = Path(item['current_path']).name if item['current_path'] else 'root'
                print(f"     • {item['filename']}")
                print(f"       Current: {current}")
            if len(files) > 5:
                print(f"     ... and {len(files) - 5} more")
            print()
    
    # Summary
    print("=" * 70)
    print("📈 SUMMARY")
    print("=" * 70)
    print(f"  • Untagged files: {len(untagged)}")
    print(f"  • Tag suggestions: {len(tag_suggestions)} unique tags")
    print(f"  • Directory suggestions: {len(dir_suggestions)} directories")
    print(f"  • Files by category: {sum(len(files) for files in analysis.get('files_by_category', {}).values())}")
    print()

def export_analysis(analysis: Dict, output_file: str):
    """Export analysis to JSON file"""
    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    print(f"💾 Analysis exported to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Analyze vault and suggest tags/directories')
    parser.add_argument('vault_path', nargs='?', help='Path to Obsidian vault')
    parser.add_argument('--service-url', default=EMBEDDING_SERVICE_URL, help='Embedding service URL')
    parser.add_argument('--export', help='Export analysis to JSON file')
    parser.add_argument('--tags-only', action='store_true', help='Only show tag suggestions')
    parser.add_argument('--dirs-only', action='store_true', help='Only show directory suggestions')
    
    args = parser.parse_args()
    
    # Get vault path
    vault_path = args.vault_path or os.getenv("OBSIDIAN_VAULT_PATH")
    if not vault_path:
        # Try to get from docker-compose.yml
        docker_compose_path = Path(__file__).parent / "docker-compose.yml"
        if docker_compose_path.exists():
            import re
            with open(docker_compose_path) as f:
                for line in f:
                    if "/app/vault" in line:
                        match = re.search(r'["\']([^"\']+):/app/vault', line)
                        if match:
                            vault_path = match.group(1)
                            break
    
    if not vault_path:
        print("❌ Vault path not found")
        print("Usage: python organize_vault.py <vault_path>")
        print("Or set OBSIDIAN_VAULT_PATH environment variable")
        sys.exit(1)
    
    print(f"📚 Vault: {vault_path}")
    print(f"🔗 Service: {args.service_url}")
    print()
    
    # Analyze
    analysis = analyze_vault(vault_path, args.service_url)
    
    if not analysis:
        print("❌ Analysis failed")
        sys.exit(1)
    
    # Filter if requested
    if args.tags_only:
        analysis = {
            'untagged_files': analysis.get('untagged_files', []),
            'tag_suggestions': analysis.get('tag_suggestions', {}),
        }
    elif args.dirs_only:
        analysis = {
            'directory_suggestions': analysis.get('directory_suggestions', {}),
            'files_by_category': analysis.get('files_by_category', {}),
        }
    
    # Print results
    print_analysis(analysis, vault_path)
    
    # Export if requested
    if args.export:
        export_analysis(analysis, args.export)

if __name__ == "__main__":
    main()



