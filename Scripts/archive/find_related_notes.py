#!/usr/bin/env python3
"""
Find notes related to a specific topic using the knowledge graph
Lightweight CLI tool - no heavy dependencies
"""

import json
import sys
import requests
from pathlib import Path
from collections import defaultdict

def query_graph_for_topic(topic, mode="graph-local", top_k=20):
    """Query the graph for notes related to a topic"""
    
    try:
        response = requests.post('http://localhost:8001/query', 
            json={
                'query': f"Find all notes related to {topic}",
                'mode': mode,
                'top_k': top_k
            },
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Graph query failed: {response.status_code}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to LightRAG service")
        print("   Start services: ./Scripts/docker_start.sh")
        return None
    except Exception as e:
        print(f"❌ Error querying graph: {e}")
        return None

def find_notes_by_entities(topic):
    """Find notes by searching entity descriptions"""
    
    db_dir = Path('./lightrag_db')
    
    # Load entities
    with open(db_dir / 'kv_store_full_entities.json', 'r') as f:
        entities = json.load(f)
    
    # Load document status for filenames
    with open(db_dir / 'kv_store_doc_status.json', 'r') as f:
        doc_status = json.load(f)
    
    # Search for topic in entity descriptions
    matching_docs = defaultdict(list)
    
    for doc_id, entity_data in entities.items():
        entity_names = entity_data.get('entity_names', [])
        for entity_name in entity_names:
            name_lower = entity_name.lower()
            
            if topic.lower() in name_lower:
                # Get filename from doc status
                filename = doc_status.get(doc_id, {}).get('filename', doc_id)
                matching_docs[doc_id].append({
                    'entity_name': entity_name,
                    'description': entity_name,  # Use name as description
                    'filename': filename
                })
    
    return matching_docs, doc_status

def display_results(topic, graph_results=None, entity_results=None):
    """Display search results in a clean format"""
    
    print(f"╔════════════════════════════════════════════════════════════╗")
    print(f"║              Notes Related to: {topic:<20} ║")
    print(f"╚════════════════════════════════════════════════════════════╝")
    print()
    
    if graph_results:
        print("🌐 Graph Query Results:")
        print()
        
        answer = graph_results.get('answer', '')
        if answer:
            print(f"Summary: {answer}")
            print()
        
        # Show sources if available
        sources = graph_results.get('sources', [])
        if sources:
            print("📄 Related Documents:")
            for i, source in enumerate(sources[:10], 1):
                print(f"   {i:2d}. {source}")
            print()
    
    if entity_results:
        matching_docs, doc_status = entity_results
        
        print("🏷️  Entity-Based Results:")
        print()
        
        if matching_docs:
            # Group by filename for cleaner display
            filename_groups = defaultdict(list)
            for doc_id, entities in matching_docs.items():
                filename = doc_status.get(doc_id, {}).get('filename', doc_id)
                filename_groups[filename].extend(entities)
            
            for filename, entities in list(filename_groups.items())[:15]:
                print(f"📄 {filename}")
                for entity in entities[:3]:  # Show top 3 entities per file
                    name = entity['entity_name']
                    desc = entity['description'][:60]
                    print(f"   • {name}: {desc}...")
                if len(entities) > 3:
                    print(f"   ... and {len(entities) - 3} more entities")
                print()
        else:
            print("   No matching entities found")
    
    print()

def suggest_actions(topic, matching_docs=None):
    """Suggest actions based on search results"""
    
    print("💡 Suggested Actions:")
    print()
    
    if matching_docs and len(matching_docs) > 0:
        print(f"   📁 Create folder: '{topic}/'")
        print(f"   📝 Create MOC: '{topic} MOC.md'")
        print(f"   🔗 Link related notes")
        print(f"   📊 Found {len(matching_docs)} documents to organize")
    else:
        print(f"   🔍 Try broader search terms")
        print(f"   📝 Create new notes about {topic}")
        print(f"   🏷️  Add tags to existing notes")
    
    print()

def main():
    """Main function"""
    
    if len(sys.argv) < 2:
        print("Usage: python3 find_related_notes.py <topic>")
        print()
        print("Examples:")
        print("  python3 find_related_notes.py 'Home Assistant'")
        print("  python3 find_related_notes.py 'ESP32'")
        print("  python3 find_related_notes.py 'Swift development'")
        sys.exit(1)
    
    topic = ' '.join(sys.argv[1:])
    
    print(f"🔍 Searching for notes related to: {topic}")
    print()
    
    # Method 1: Graph query (if service is running)
    print("🌐 Querying knowledge graph...")
    graph_results = query_graph_for_topic(topic)
    
    # Method 2: Entity search (always works)
    print("🏷️  Searching entity database...")
    entity_results = find_notes_by_entities(topic)
    
    # Display results
    display_results(topic, graph_results, entity_results)
    
    # Suggest actions
    matching_docs = entity_results[0] if entity_results else None
    suggest_actions(topic, matching_docs)
    
    print("✨ Analysis complete!")

if __name__ == "__main__":
    main()
