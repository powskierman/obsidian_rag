#!/usr/bin/env python3
"""
Classify notes into folders based on knowledge graph analysis
Lightweight CLI tool for vault organization
"""

import json
import sys
import shutil
from pathlib import Path
from collections import defaultdict, Counter

def load_note_data():
    """Load note metadata and entity data"""
    
    db_dir = Path('./lightrag_db')
    
    # Load entities
    with open(db_dir / 'kv_store_full_entities.json', 'r') as f:
        entities = json.load(f)
    
    # Load document status for filenames
    with open(db_dir / 'kv_store_doc_status.json', 'r') as f:
        doc_status = json.load(f)
    
    return entities, doc_status

def classify_note_by_entities(doc_id, entities, doc_status):
    """Classify a note based on its entities"""
    
    if doc_id not in entities:
        return "Unclassified", []
    
    entity_data = entities[doc_id]
    entity_names = entity_data.get('entity_names', [])
    
    # Define classification rules
    classification_rules = {
        'Home Automation': ['home assistant', 'esphome', 'thread', 'smart home', 'automation', 'zigbee', 'z-wave', 'mqtt'],
        'Development': ['swift', 'swiftui', 'xcode', 'git', 'github', 'programming', 'code', 'development', 'api'],
        'Hardware': ['esp32', 'raspberry pi', 'kicad', 'electronics', 'circuit', 'microcontroller', 'arduino', 'sensor'],
        'Health': ['lymphoma', 'yescarta', 'treatment', 'medical', 'health', 'therapy', 'cancer', 'hospital'],
        'Learning': ['sequential thinking', 'learning', 'education', 'study', 'knowledge', 'concept', 'theory'],
        'Tools': ['obsidian', 'readwise', 'macos', 'apple', 'software', 'tool', 'app', 'utility'],
        'Projects': ['project', 'build', 'create', 'implement', 'setup', 'install', 'configure', 'tutorial']
    }
    
    # Score each category
    category_scores = defaultdict(int)
    matched_entities = defaultdict(list)
    
    for entity_name in entity_names:
        name_lower = entity_name.lower()
        
        for category, keywords in classification_rules.items():
            for keyword in keywords:
                if keyword in name_lower:
                    category_scores[category] += 1
                    matched_entities[category].append(entity_name)
    
    # Find best category
    if category_scores:
        best_category = max(category_scores.items(), key=lambda x: x[1])
        return best_category[0], matched_entities[best_category[0]]
    else:
        return "Unclassified", []

def get_note_path(doc_id, doc_status):
    """Get the actual file path for a document"""
    
    filename = doc_status.get(doc_id, {}).get('filename', '')
    if not filename:
        return None
    
    # Try to find the file in common locations
    possible_paths = [
        Path(filename),
        Path(f"./vault/{filename}"),
        Path(f"../vault/{filename}"),
        # Add your vault path here if different
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None

def create_folder_structure():
    """Create suggested folder structure"""
    
    folders = [
        "01-Areas/Technology/Home-Automation",
        "01-Areas/Technology/Development", 
        "01-Areas/Technology/Hardware",
        "01-Areas/Health",
        "01-Areas/Learning",
        "02-Projects",
        "03-Resources/Tools",
        "04-Archive",
        "00-Inbox"
    ]
    
    for folder in folders:
        Path(folder).mkdir(parents=True, exist_ok=True)
        print(f"📁 Created folder: {folder}")

def classify_all_notes(dry_run=True):
    """Classify all notes and optionally move them"""
    
    print("📊 Loading note data...")
    entities, doc_status = load_note_data()
    
    print(f"✅ Loaded {len(entities)} documents")
    print()
    
    # Classify each note
    classifications = defaultdict(list)
    unclassified = []
    
    for doc_id in entities:
        category, matched_entities = classify_note_by_entities(doc_id, entities, doc_status)
        
        filename = doc_status.get(doc_id, {}).get('filename', doc_id)
        note_path = get_note_path(doc_id, doc_status)
        
        note_info = {
            'doc_id': doc_id,
            'filename': filename,
            'path': note_path,
            'matched_entities': matched_entities
        }
        
        if category == "Unclassified":
            unclassified.append(note_info)
        else:
            classifications[category].append(note_info)
    
    # Display results
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                    Classification Results                  ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    for category, notes in classifications.items():
        print(f"📁 {category} ({len(notes)} notes)")
        
        for note in notes[:5]:  # Show first 5 notes
            filename = note['filename']
            entities_str = ', '.join(note['matched_entities'][:3])
            if len(note['matched_entities']) > 3:
                entities_str += f" (+{len(note['matched_entities'])-3} more)"
            print(f"   • {filename}")
            print(f"     Entities: {entities_str}")
        
        if len(notes) > 5:
            print(f"   ... and {len(notes) - 5} more notes")
        print()
    
    if unclassified:
        print(f"❓ Unclassified ({len(unclassified)} notes)")
        for note in unclassified[:5]:
            print(f"   • {note['filename']}")
        if len(unclassified) > 5:
            print(f"   ... and {len(unclassified) - 5} more")
        print()
    
    # Move files if not dry run
    if not dry_run:
        print("📁 Moving files to classified folders...")
        
        folder_mapping = {
            'Home Automation': '01-Areas/Technology/Home-Automation',
            'Development': '01-Areas/Technology/Development',
            'Hardware': '01-Areas/Technology/Hardware',
            'Health': '01-Areas/Health',
            'Learning': '01-Areas/Learning',
            'Tools': '03-Resources/Tools',
            'Projects': '02-Projects'
        }
        
        moved_count = 0
        for category, notes in classifications.items():
            if category in folder_mapping:
                target_folder = folder_mapping[category]
                
                for note in notes:
                    if note['path'] and note['path'].exists():
                        try:
                            target_path = Path(target_folder) / note['path'].name
                            shutil.move(str(note['path']), str(target_path))
                            print(f"   ✅ Moved {note['filename']} → {target_folder}")
                            moved_count += 1
                        except Exception as e:
                            print(f"   ❌ Failed to move {note['filename']}: {e}")
        
        print(f"\n✅ Moved {moved_count} files")
    
    return classifications, unclassified

def create_moc_files(classifications):
    """Create Map of Content files for each category"""
    
    print("\n📝 Creating MOC files...")
    
    for category, notes in classifications.items():
        if len(notes) < 3:  # Skip categories with too few notes
            continue
        
        moc_filename = f"{category.replace(' ', '-')}-MOC.md"
        moc_path = Path(moc_filename)
        
        with open(moc_path, 'w') as f:
            f.write(f"# {category} MOC\n\n")
            f.write(f"*Map of Content for {category} related notes*\n\n")
            
            # Group by sub-topics if possible
            sub_topics = defaultdict(list)
            for note in notes:
                if note['matched_entities']:
                    # Use first entity as sub-topic
                    sub_topic = note['matched_entities'][0]
                    sub_topics[sub_topic].append(note)
            
            for sub_topic, sub_notes in sub_topics.items():
                f.write(f"## {sub_topic}\n\n")
                for note in sub_notes:
                    filename = note['filename'].replace('.md', '')
                    f.write(f"- [[{filename}]]\n")
                f.write("\n")
        
        print(f"   ✅ Created {moc_filename}")

def main():
    """Main function"""
    
    if len(sys.argv) > 1 and sys.argv[1] == "--execute":
        dry_run = False
        print("⚠️  EXECUTE MODE - Files will be moved!")
    else:
        dry_run = True
        print("🔍 DRY RUN MODE - No files will be moved")
        print("   Use --execute to actually move files")
    
    print()
    
    # Create folder structure
    create_folder_structure()
    
    # Classify notes
    classifications, unclassified = classify_all_notes(dry_run)
    
    # Create MOC files
    create_moc_files(classifications)
    
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║                    Summary & Next Steps                    ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    total_classified = sum(len(notes) for notes in classifications.values())
    print(f"📊 Results:")
    print(f"   • {total_classified} notes classified")
    print(f"   • {len(unclassified)} notes unclassified")
    print(f"   • {len(classifications)} categories created")
    print()
    
    if dry_run:
        print("🚀 Next Steps:")
        print("   1. Review the classification results above")
        print("   2. Run: python3 classify_notes.py --execute")
        print("   3. Review moved files and adjust as needed")
        print("   4. Update MOC files with additional links")
    else:
        print("✅ Organization complete!")
        print("   Review the moved files and MOC files")
    
    print()

if __name__ == "__main__":
    main()
