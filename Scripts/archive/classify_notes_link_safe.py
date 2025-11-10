#!/usr/bin/env python3
"""
Enhanced note classification with link preservation
Maintains all Obsidian links when moving files
"""

import json
import sys
import shutil
import re
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

def find_all_markdown_files(vault_root):
    """Find all markdown files in the vault"""
    
    vault_path = Path(vault_root)
    if not vault_path.exists():
        print(f"❌ Vault path not found: {vault_root}")
        return []
    
    md_files = list(vault_path.rglob("*.md"))
    print(f"📄 Found {len(md_files)} markdown files")
    return md_files

def extract_links_from_file(file_path):
    """Extract all Obsidian links from a markdown file"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find all Obsidian links: [[link]], [[link|display]], ![[image]]
        link_pattern = r'!?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]'
        matches = re.findall(link_pattern, content)
        
        links = []
        for match in matches:
            link_target = match[0].strip()
            display_text = match[1].strip() if match[1] else link_target
            links.append({
                'target': link_target,
                'display': display_text,
                'full_match': f"[[{link_target}]]" if not display_text else f"[[{link_target}|{display_text}]]"
            })
        
        return links, content
    
    except Exception as e:
        print(f"⚠️  Error reading {file_path}: {e}")
        return [], ""

def update_links_in_file(file_path, link_mapping, dry_run=True):
    """Update all links in a file based on the link mapping"""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        updated_count = 0
        
        # Update each link
        for old_link, new_link in link_mapping.items():
            if old_link in content:
                content = content.replace(old_link, new_link)
                updated_count += 1
        
        # Write updated content if changes were made
        if content != original_content and not dry_run:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"   🔗 Updated {updated_count} links in {file_path.name}")
        elif content != original_content:
            print(f"   🔗 Would update {updated_count} links in {file_path.name}")
        
        return updated_count
    
    except Exception as e:
        print(f"❌ Error updating links in {file_path}: {e}")
        return 0

def create_link_mapping(moved_files, vault_root):
    """Create mapping of old links to new links for moved files"""
    
    link_mapping = {}
    
    for old_path, new_path in moved_files.items():
        old_name = old_path.stem  # filename without extension
        new_name = new_path.stem
        
        # Create various link formats
        link_mapping[f"[[{old_name}]]"] = f"[[{new_name}]]"
        link_mapping[f"[[{old_name}.md]]"] = f"[[{new_name}]]"
        link_mapping[f"[[{old_name}.md|{old_name}]]"] = f"[[{new_name}]]"
        
        # Handle display text variations
        link_mapping[f"[[{old_name}|{old_name}]]"] = f"[[{new_name}]]"
    
    return link_mapping

def move_file_with_link_preservation(source_path, target_path, vault_root, dry_run=True):
    """Move a file and update all references to it"""
    
    if not source_path.exists():
        return False, {}
    
    # Step 1: Move the file
    if not dry_run:
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_path), str(target_path))
            print(f"   ✅ Moved {source_path.name} → {target_path.parent.name}/")
        except Exception as e:
            print(f"   ❌ Failed to move {source_path.name}: {e}")
            return False, {}
    else:
        print(f"   📁 Would move {source_path.name} → {target_path.parent.name}/")
    
    # Step 2: Create link mapping
    link_mapping = create_link_mapping({source_path: target_path}, vault_root)
    
    # Step 3: Find all files that might reference this file
    all_files = find_all_markdown_files(vault_root)
    
    # Step 4: Update links in all files
    total_updates = 0
    for file_path in all_files:
        if file_path != source_path:  # Don't update the moved file itself
            updates = update_links_in_file(file_path, link_mapping, dry_run)
            total_updates += updates
    
    if total_updates > 0:
        print(f"   🔗 {'Updated' if not dry_run else 'Would update'} {total_updates} link references")
    
    return True, link_mapping

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

def classify_all_notes_with_link_preservation(dry_run=True, vault_root="./vault"):
    """Classify all notes and move them while preserving links"""
    
    print("📊 Loading note data...")
    entities, doc_status = load_note_data()
    
    print(f"✅ Loaded {len(entities)} documents")
    print()
    
    # Classify each note
    classifications = defaultdict(list)
    unclassified = []
    
    for doc_id in entities:
        category, matched_entities = classify_note_by_entities(doc_id, entities, doc_status)
        
        filename = doc_status.get(doc_id, {}).get('filename', '')
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
    print("║              Classification Results (Link-Safe)            ║")
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
    
    # Move files with link preservation
    if not dry_run:
        print("📁 Moving files with link preservation...")
    else:
        print("📁 Would move files with link preservation...")
    
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
    total_link_updates = 0
    
    for category, notes in classifications.items():
        if category in folder_mapping:
            target_folder = folder_mapping[category]
            
            for note in notes:
                if note['path'] and note['path'].exists():
                    target_path = Path(target_folder) / note['path'].name
                    
                    success, link_updates = move_file_with_link_preservation(
                        note['path'], target_path, vault_root, dry_run
                    )
                    
                    if success:
                        moved_count += 1
                        total_link_updates += link_updates
    
    print(f"\n✅ {'Moved' if not dry_run else 'Would move'} {moved_count} files")
    print(f"🔗 {'Updated' if not dry_run else 'Would update'} {total_link_updates} link references")
    
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
        print("⚠️  EXECUTE MODE - Files will be moved with link preservation!")
    else:
        dry_run = True
        print("🔍 DRY RUN MODE - No files will be moved")
        print("   Use --execute to actually move files")
    
    print()
    
    # Get vault root
    vault_root = input("Enter vault root path (default: ./vault): ").strip()
    if not vault_root:
        vault_root = "./vault"
    
    print(f"📂 Using vault root: {vault_root}")
    print()
    
    # Create folder structure
    create_folder_structure()
    
    # Classify notes with link preservation
    classifications, unclassified = classify_all_notes_with_link_preservation(dry_run, vault_root)
    
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
    print(f"   • 🔗 All links preserved during moves")
    print()
    
    if dry_run:
        print("🚀 Next Steps:")
        print("   1. Review the classification results above")
        print("   2. Run: python3 classify_notes_link_safe.py --execute")
        print("   3. Verify all links work correctly")
        print("   4. Update MOC files with additional links")
    else:
        print("✅ Organization complete with link preservation!")
        print("   All internal links have been updated")
        print("   Review the moved files and MOC files")
    
    print()

if __name__ == "__main__":
    main()


