#!/usr/bin/env python3
"""
Lightweight cluster analysis for knowledge graph
No heavy dependencies - just JSON parsing
"""

import json
import sys
from pathlib import Path
from collections import defaultdict, Counter

def load_graph_data():
    """Load graph data from JSON files"""
    db_dir = Path('./lightrag_db')
    
    # Load entities
    with open(db_dir / 'kv_store_full_entities.json', 'r') as f:
        entities = json.load(f)
    
    # Load relations  
    with open(db_dir / 'kv_store_full_relations.json', 'r') as f:
        relations = json.load(f)
    
    return entities, relations

def analyze_topic_clusters(entities, relations):
    """Analyze topic clusters from entities and relations"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║              Topic Cluster Analysis                        ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    # Extract all entities with their descriptions
    all_entities = []
    entity_counts = Counter()
    
    for doc_id, entity_data in entities.items():
        # entity_data has 'entity_names' as a list
        entity_names = entity_data.get('entity_names', [])
        for entity_name in entity_names:
            if entity_name and len(entity_name) > 2:  # Filter meaningful entities
                all_entities.append({
                    'name': entity_name,
                    'description': entity_name,  # Use name as description for now
                    'doc_id': doc_id
                })
                entity_counts[entity_name] += 1
    
    # Group by topic keywords
    topic_clusters = defaultdict(list)
    
    # Define topic keywords
    topic_keywords = {
        'Home Automation': ['home assistant', 'esphome', 'thread', 'smart home', 'automation', 'zigbee', 'z-wave'],
        'Development': ['swift', 'swiftui', 'xcode', 'git', 'github', 'programming', 'code', 'development'],
        'Hardware': ['esp32', 'raspberry pi', 'kicad', 'electronics', 'circuit', 'microcontroller', 'arduino'],
        'Health': ['lymphoma', 'yescarta', 'treatment', 'medical', 'health', 'therapy', 'cancer'],
        'Learning': ['sequential thinking', 'learning', 'education', 'study', 'knowledge', 'concept'],
        'Tools': ['obsidian', 'readwise', 'macos', 'apple', 'software', 'tool', 'app'],
        'Projects': ['project', 'build', 'create', 'implement', 'setup', 'install', 'configure']
    }
    
    # Classify entities into clusters
    for entity in all_entities:
        name_lower = entity['name'].lower()
        desc_lower = entity['description'].lower()
        
        classified = False
        for topic, keywords in topic_keywords.items():
            if any(keyword in name_lower or keyword in desc_lower for keyword in keywords):
                topic_clusters[topic].append(entity)
                classified = True
                break
        
        if not classified:
            topic_clusters['Other'].append(entity)
    
    # Display clusters
    for topic, entities_list in topic_clusters.items():
        if len(entities_list) > 0:
            print(f"📁 {topic} ({len(entities_list)} entities)")
            
            # Show top entities in this cluster
            entity_names = [e['name'] for e in entities_list]
            name_counts = Counter(entity_names)
            top_entities = name_counts.most_common(5)
            
            for name, count in top_entities:
                print(f"   • {name} ({count} mentions)")
            print()
    
    return topic_clusters

def find_highly_connected_entities(entities, relations):
    """Find entities with many connections"""
    
    print("🌟 Highly Connected Entities:")
    print()
    
    # Count entity mentions across documents
    entity_mentions = Counter()
    entity_descriptions = {}
    
    for doc_id, entity_data in entities.items():
        entity_names = entity_data.get('entity_names', [])
        for entity_name in entity_names:
            if entity_name:
                entity_mentions[entity_name] += 1
                if entity_name not in entity_descriptions:
                    entity_descriptions[entity_name] = entity_name
    
    # Show top connected entities
    top_entities = entity_mentions.most_common(20)
    
    for i, (name, count) in enumerate(top_entities, 1):
        desc = entity_descriptions.get(name, '')[:60]
        print(f"   {i:2d}. {name:<25} ({count:3d} mentions) - {desc}...")
    
    print()
    return top_entities

def find_orphaned_notes(entities, relations):
    """Find notes with few or no connections"""
    
    print("🔍 Orphaned Notes Analysis:")
    print()
    
    # Count entities per document
    doc_entity_counts = {}
    doc_relation_counts = {}
    
    for doc_id, entity_data in entities.items():
        entity_count = len(entity_data.get('entity_names', []))
        doc_entity_counts[doc_id] = entity_count
    
    for doc_id, relation_list in relations.items():
        doc_relation_counts[doc_id] = len(relation_list)
    
    # Find documents with few connections
    low_connection_docs = []
    for doc_id in doc_entity_counts:
        entity_count = doc_entity_counts.get(doc_id, 0)
        relation_count = doc_relation_counts.get(doc_id, 0)
        total_connections = entity_count + relation_count
        
        if total_connections < 3:  # Threshold for "orphaned"
            low_connection_docs.append((doc_id, entity_count, relation_count))
    
    # Sort by connection count
    low_connection_docs.sort(key=lambda x: x[1] + x[2])
    
    print(f"Found {len(low_connection_docs)} notes with < 3 connections:")
    print()
    
    for doc_id, entity_count, relation_count in low_connection_docs[:10]:
        print(f"   • {doc_id} - {entity_count} entities, {relation_count} relations")
    
    if len(low_connection_docs) > 10:
        print(f"   ... and {len(low_connection_docs) - 10} more")
    
    print()
    return low_connection_docs

def suggest_organization_structure(topic_clusters, top_entities):
    """Suggest folder structure based on analysis"""
    
    print("📁 Suggested Organization Structure:")
    print()
    
    # Create folder suggestions based on clusters
    folder_structure = {
        "01-Areas": {},
        "02-Projects": {},
        "03-Resources": {},
        "04-Archive": {}
    }
    
    # Map clusters to folders
    for topic, entities in topic_clusters.items():
        if len(entities) >= 5:  # Only suggest folders for substantial clusters
            if topic in ['Home Automation', 'Development', 'Hardware']:
                folder_structure["01-Areas"][topic] = len(entities)
            elif topic in ['Health', 'Learning']:
                folder_structure["01-Areas"][topic] = len(entities)
            elif topic == 'Tools':
                folder_structure["03-Resources"][topic] = len(entities)
            else:
                folder_structure["02-Projects"][topic] = len(entities)
    
    # Display suggested structure
    for folder, topics in folder_structure.items():
        if topics:
            print(f"📁 {folder}/")
            for topic, count in sorted(topics.items(), key=lambda x: x[1], reverse=True):
                print(f"   📁 {topic}/ ({count} entities)")
            print()
    
    return folder_structure

def main():
    """Main analysis function"""
    
    # Check if database exists
    db_dir = Path('./lightrag_db')
    if not db_dir.exists():
        print("❌ Database not found!")
        print("   Run indexing first: ./Scripts/run_openrouter_index.sh")
        sys.exit(1)
    
    print("📊 Loading knowledge graph data...")
    entities, relations = load_graph_data()
    
    print("✅ Data loaded successfully!")
    print()
    
    # Run analyses
    topic_clusters = analyze_topic_clusters(entities, relations)
    top_entities = find_highly_connected_entities(entities, relations)
    orphaned_notes = find_orphaned_notes(entities, relations)
    folder_structure = suggest_organization_structure(topic_clusters, top_entities)
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                    Summary & Next Steps                    ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    print("🎯 Key Insights:")
    print(f"   • {len(topic_clusters)} topic clusters identified")
    print(f"   • {len(top_entities)} highly connected entities")
    print(f"   • {len(orphaned_notes)} notes need better connections")
    print()
    print("📋 Next Steps:")
    print("   1. Review suggested folder structure above")
    print("   2. Run: python3 find_related_notes.py <topic>")
    print("   3. Run: python3 classify_notes.py")
    print("   4. Start moving notes to suggested folders")
    print()

if __name__ == "__main__":
    main()
