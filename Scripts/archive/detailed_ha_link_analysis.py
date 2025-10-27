#!/usr/bin/env python3
"""
Detailed Home Assistant Link Analysis Tool
Provides specific cross-linking suggestions with examples
"""

import os
import re
import json
from pathlib import Path
from collections import defaultdict, Counter
import requests

def load_knowledge_graph():
    """Load knowledge graph data"""
    try:
        with open('./lightrag_db/kv_store_doc_status.json', 'r') as f:
            doc_status = json.load(f)
        with open('./lightrag_db/kv_store_full_entities.json', 'r') as f:
            entities = json.load(f)
        return doc_status, entities
    except Exception as e:
        print(f"❌ Error loading knowledge graph: {e}")
        return {}, {}

def find_home_assistant_notes(doc_status, entities):
    """Find all Home Assistant related notes"""
    ha_notes = {}
    
    for doc_id, entity_data in entities.items():
        entity_names = entity_data.get('entity_names', [])
        for entity_name in entity_names:
            if 'home assistant' in entity_name.lower():
                filename = doc_status.get(doc_id, {}).get('filename', doc_id)
                filepath = doc_status.get(doc_id, {}).get('filepath', '')
                
                ha_notes[doc_id] = {
                    'filename': filename,
                    'filepath': filepath,
                    'entities': entity_names
                }
                break
    
    return ha_notes

def analyze_note_content(filepath):
    """Analyze note content for existing links and content"""
    if not os.path.exists(filepath):
        return {'content': '', 'existing_links': [], 'sections': [], 'backlinks': []}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find existing links
        existing_links = re.findall(r'\[\[([^\]]+)\]\]', content)
        
        # Find sections
        sections = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
        
        # Find backlink sections
        backlinks = re.findall(r'### Backlink\s*\n(.*?)(?=\n###|\n#|\Z)', content, re.DOTALL)
        
        return {
            'content': content,
            'existing_links': existing_links,
            'sections': sections,
            'backlinks': backlinks
        }
    except Exception as e:
        print(f"⚠️ Error reading {filepath}: {e}")
        return {'content': '', 'existing_links': [], 'sections': [], 'backlinks': []}

def get_top_ha_notes():
    """Get the top Home Assistant notes from MCP search results"""
    return [
        'Home-Assistant MoC.md',
        '$13 voice assistant for Home Assistant.md',
        'Home-Assistant OS.md',
        'Raspberry Pi Home Assistant.md',
        'Home Assistant ssh.md',
        'Sending messages from Home Assistant to SwiftUI app.md',
        'Notification Target.md',
        'ChatGPT in an iOS Shortcut.md',
        'Home-Assistant - Alexa Integration.md',
        'GarageHass Communication Considerations.md'
    ]

def analyze_top_notes(ha_notes, top_notes):
    """Analyze the top Home Assistant notes"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║           Top Home Assistant Notes Analysis               ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    analysis_results = {}
    
    for filename in top_notes:
        # Find the note in our data
        note_data = None
        for doc_id, data in ha_notes.items():
            if data['filename'] == filename:
                note_data = data
                break
        
        if not note_data:
            print(f"⚠️ Note not found: {filename}")
            continue
        
        filepath = note_data['filepath']
        analysis = analyze_note_content(filepath)
        
        analysis_results[filename] = {
            'filepath': filepath,
            'existing_links': analysis['existing_links'],
            'sections': analysis['sections'],
            'backlinks': analysis['backlinks'],
            'content_length': len(analysis['content'])
        }
        
        print(f"📄 {filename}")
        print(f"   📍 Path: {filepath}")
        print(f"   🔗 Links: {len(analysis['existing_links'])}")
        print(f"   📑 Sections: {len(analysis['sections'])}")
        print(f"   📝 Content: {len(analysis['content'])} chars")
        
        if analysis['existing_links']:
            print(f"   🔗 Current links: {', '.join(analysis['existing_links'][:5])}")
        
        print()
    
    return analysis_results

def suggest_specific_links(analysis_results):
    """Suggest specific cross-links with examples"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║              Specific Cross-Linking Suggestions           ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    # Define specific linking strategies
    linking_strategies = {
        'Home-Assistant MoC.md': {
            'should_link_to': [
                'Home-Assistant OS',
                'Raspberry Pi Home Assistant',
                'Home Assistant ssh',
                'Home-Assistant - Alexa Integration',
                'Node-Red Home Assistant',
                'HACS',
                'Sending messages from Home Assistant to SwiftUI app',
                'Notification Target',
                '$13 voice assistant for Home Assistant',
                'GarageHass Communication Considerations',
                'Home Assistant Matter MoC'
            ],
            'reason': 'MOC should link to all major Home Assistant topics'
        },
        'Home-Assistant OS.md': {
            'should_link_to': [
                'Home-Assistant MoC',
                'Raspberry Pi Home Assistant',
                'Home Assistant ssh'
            ],
            'reason': 'OS notes should link to installation and access methods'
        },
        'Raspberry Pi Home Assistant.md': {
            'should_link_to': [
                'Home-Assistant MoC',
                'Home-Assistant OS',
                'Home Assistant ssh'
            ],
            'reason': 'Hardware setup should link to OS and access methods'
        },
        'Home Assistant ssh.md': {
            'should_link_to': [
                'Home-Assistant MoC',
                'Home-Assistant OS',
                'Raspberry Pi Home Assistant'
            ],
            'reason': 'SSH access should link to installation and setup notes'
        },
        'Home-Assistant - Alexa Integration.md': {
            'should_link_to': [
                'Home-Assistant MoC',
                '$13 voice assistant for Home Assistant'
            ],
            'reason': 'Voice integrations should cross-reference each other'
        },
        'Sending messages from Home Assistant to SwiftUI app.md': {
            'should_link_to': [
                'Home-Assistant MoC',
                'Notification Target',
                'ChatGPT in an iOS Shortcut'
            ],
            'reason': 'Mobile integrations should link to each other'
        },
        'Notification Target.md': {
            'should_link_to': [
                'Home-Assistant MoC',
                'Sending messages from Home Assistant to SwiftUI app'
            ],
            'reason': 'Notification systems should cross-reference'
        },
        '$13 voice assistant for Home Assistant.md': {
            'should_link_to': [
                'Home-Assistant MoC',
                'Home-Assistant - Alexa Integration'
            ],
            'reason': 'Voice assistants should cross-reference each other'
        }
    }
    
    for filename, data in analysis_results.items():
        if filename not in linking_strategies:
            continue
        
        strategy = linking_strategies[filename]
        current_links = data['existing_links']
        missing_links = []
        
        for should_link in strategy['should_link_to']:
            if should_link not in current_links:
                missing_links.append(should_link)
        
        if missing_links:
            print(f"📄 {filename}")
            print(f"   💡 {strategy['reason']}")
            print(f"   ➕ Missing links:")
            for link in missing_links:
                print(f"      • [[{link}]]")
            print()
        else:
            print(f"✅ {filename} - All recommended links present!")
            print()

def generate_link_examples():
    """Generate specific examples of where to add links"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                Link Implementation Examples                ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    examples = [
        {
            'file': 'Home-Assistant OS.md',
            'section': '### Backlink',
            'current': '[[Home-Assistant MoC]]',
            'suggested': '[[Home-Assistant MoC]]\n[[Raspberry Pi Home Assistant]]\n[[Home Assistant ssh]]',
            'reason': 'Add links to related installation and access methods'
        },
        {
            'file': 'Raspberry Pi Home Assistant.md',
            'section': '### Backlink',
            'current': '[[Raspberry Pi Projects MOC]]',
            'suggested': '[[Raspberry Pi Projects MOC]]\n[[Home-Assistant MoC]]\n[[Home-Assistant OS]]',
            'reason': 'Link to Home Assistant specific content'
        },
        {
            'file': 'Home Assistant ssh.md',
            'section': '### Reference',
            'current': '- [Debugging the Home Assistant Operating System](https://developer.home-assistant.io/docs/operating-system/debugging/)',
            'suggested': '- [Debugging the Home Assistant Operating System](https://developer.home-assistant.io/docs/operating-system/debugging/)\n- [[Home-Assistant MoC]]\n- [[Home-Assistant OS]]',
            'reason': 'Add internal links to related notes'
        },
        {
            'file': 'Sending messages from Home Assistant to SwiftUI app.md',
            'section': '### Backlink',
            'current': '[[Home-Assistant MoC]]',
            'suggested': '[[Home-Assistant MoC]]\n[[Notification Target]]\n[[ChatGPT in an iOS Shortcut]]',
            'reason': 'Link to other mobile integration notes'
        }
    ]
    
    for example in examples:
        print(f"📄 {example['file']}")
        print(f"   📍 Section: {example['section']}")
        print(f"   💡 Reason: {example['reason']}")
        print(f"   ➕ Add these links:")
        print(f"      {example['suggested']}")
        print()

def generate_implementation_plan():
    """Generate a step-by-step implementation plan"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                Implementation Plan                         ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    print("🎯 PHASE 1: Core Links (High Priority)")
    print("1. Ensure every Home Assistant note links to [[Home-Assistant MoC]]")
    print("2. Add bidirectional links between core notes:")
    print("   • Home-Assistant OS ↔ Raspberry Pi Home Assistant")
    print("   • Home-Assistant OS ↔ Home Assistant ssh")
    print("   • Raspberry Pi Home Assistant ↔ Home Assistant ssh")
    print()
    
    print("🎯 PHASE 2: Category Links (Medium Priority)")
    print("3. Link integration notes:")
    print("   • Home-Assistant - Alexa Integration ↔ $13 voice assistant")
    print("   • Node-Red Home Assistant ↔ Home-Assistant MoC")
    print("   • HACS ↔ Home-Assistant MoC")
    print()
    
    print("4. Link mobile integration notes:")
    print("   • Sending messages from Home Assistant to SwiftUI app ↔ Notification Target")
    print("   • Sending messages from Home Assistant to SwiftUI app ↔ ChatGPT in an iOS Shortcut")
    print()
    
    print("🎯 PHASE 3: Project Links (Lower Priority)")
    print("5. Link project notes:")
    print("   • GarageHass Communication Considerations ↔ Home-Assistant MoC")
    print("   • Home Assistant Matter MoC ↔ Home-Assistant MoC")
    print()
    
    print("📝 IMPLEMENTATION TIPS:")
    print("• Add links in context where they're most relevant")
    print("• Use the '### Backlink' section for general connections")
    print("• Use inline links for specific references")
    print("• Test all links to ensure they work")
    print("• Update the MOC to include all new connections")
    print()

def main():
    """Main function"""
    print("🔍 Loading Home Assistant notes...")
    
    # Load knowledge graph
    doc_status, entities = load_knowledge_graph()
    if not doc_status:
        print("❌ Could not load knowledge graph data")
        return
    
    # Find Home Assistant notes
    ha_notes = find_home_assistant_notes(doc_status, entities)
    print(f"✅ Found {len(ha_notes)} Home Assistant related notes")
    
    if not ha_notes:
        print("❌ No Home Assistant notes found")
        return
    
    # Get top notes from MCP search
    top_notes = get_top_ha_notes()
    
    # Analyze top notes
    analysis_results = analyze_top_notes(ha_notes, top_notes)
    
    # Suggest specific links
    suggest_specific_links(analysis_results)
    
    # Generate examples
    generate_link_examples()
    
    # Generate implementation plan
    generate_implementation_plan()
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                    Summary & Next Steps                    ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    print("🎯 **Key Findings:**")
    print("• Your Home Assistant notes have good basic linking")
    print("• Opportunities exist for more cross-references")
    print("• Focus on bidirectional links between related topics")
    print()
    print("🚀 **Recommended Actions:**")
    print("1. **Start with Phase 1** - Core links (highest impact)")
    print("2. **Add links gradually** - Don't overwhelm yourself")
    print("3. **Test links** - Make sure they work")
    print("4. **Update MOC** - Keep it current")
    print()
    print("💡 **Pro Tip**: Add links where they provide the most value to readers!")
    print()

if __name__ == "__main__":
    main()





