#!/usr/bin/env python3
"""
Home Assistant Cross-Linking Enhancement Tool
Analyzes Home Assistant notes and suggests cross-links
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
        return {'content': '', 'existing_links': [], 'sections': []}
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find existing links
        existing_links = re.findall(r'\[\[([^\]]+)\]\]', content)
        
        # Find sections
        sections = re.findall(r'^#+\s+(.+)$', content, re.MULTILINE)
        
        return {
            'content': content,
            'existing_links': existing_links,
            'sections': sections
        }
    except Exception as e:
        print(f"⚠️ Error reading {filepath}: {e}")
        return {'content': '', 'existing_links': [], 'sections': []}

def suggest_cross_links(ha_notes):
    """Suggest cross-links between Home Assistant notes"""
    suggestions = {}
    
    # Define relationship patterns
    relationship_patterns = {
        'core': ['Home-Assistant MoC', 'Home-Assistant OS', 'Raspberry Pi Home Assistant'],
        'integration': ['Home Assistant ssh', 'Home-Assistant - Alexa Integration', 'Node-Red Home Assistant', 'HACS'],
        'mobile': ['Sending messages from Home Assistant to SwiftUI app', 'Notification Target', 'ChatGPT in an iOS Shortcut'],
        'project': ['$13 voice assistant for Home Assistant', 'GarageHass Communication Considerations', 'Home Assistant Matter MoC']
    }
    
    for doc_id, note_info in ha_notes.items():
        filename = note_info['filename']
        filepath = note_info['filepath']
        
        if not filepath or not os.path.exists(filepath):
            continue
            
        # Analyze current content
        analysis = analyze_note_content(filepath)
        existing_links = analysis['existing_links']
        
        # Find suggested links
        suggested_links = []
        
        # Core links (every HA note should link to MOC)
        if 'Home-Assistant MoC' not in existing_links and filename != 'Home-Assistant MoC.md':
            suggested_links.append({
                'target': 'Home-Assistant MoC',
                'reason': 'Central hub for all Home Assistant content',
                'priority': 'high'
            })
        
        # Category-based suggestions
        for category, related_files in relationship_patterns.items():
            if any(related in filename for related in related_files):
                for related_file in related_files:
                    if related_file not in existing_links and related_file != filename:
                        suggested_links.append({
                            'target': related_file.replace('.md', ''),
                            'reason': f'Related {category} functionality',
                            'priority': 'medium'
                        })
        
        # Content-based suggestions
        content_lower = analysis['content'].lower()
        
        if 'ssh' in content_lower and 'Home Assistant ssh' not in existing_links:
            suggested_links.append({
                'target': 'Home Assistant ssh',
                'reason': 'SSH-related content detected',
                'priority': 'medium'
            })
        
        if 'alexa' in content_lower and 'Home-Assistant - Alexa Integration' not in existing_links:
            suggested_links.append({
                'target': 'Home-Assistant - Alexa Integration',
                'reason': 'Alexa integration mentioned',
                'priority': 'medium'
            })
        
        if 'swift' in content_lower or 'ios' in content_lower:
            swift_links = ['Sending messages from Home Assistant to SwiftUI app', 'Notification Target']
            for link in swift_links:
                if link not in existing_links:
                    suggested_links.append({
                        'target': link.replace('.md', ''),
                        'reason': 'iOS/Swift integration mentioned',
                        'priority': 'medium'
                    })
        
        if 'matter' in content_lower and 'Home Assistant Matter MoC' not in existing_links:
            suggested_links.append({
                'target': 'Home Assistant Matter MoC',
                'reason': 'Matter protocol mentioned',
                'priority': 'medium'
            })
        
        if suggested_links:
            suggestions[filename] = {
                'filepath': filepath,
                'existing_links': existing_links,
                'suggested_links': suggested_links,
                'sections': analysis['sections']
            }
    
    return suggestions

def generate_link_report(suggestions):
    """Generate a comprehensive link enhancement report"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║           Home Assistant Cross-Linking Analysis            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    total_suggestions = sum(len(s['suggested_links']) for s in suggestions.values())
    high_priority = sum(1 for s in suggestions.values() 
                       for link in s['suggested_links'] 
                       if link['priority'] == 'high')
    
    print(f"📊 Analysis Summary:")
    print(f"   • Notes analyzed: {len(suggestions)}")
    print(f"   • Total suggestions: {total_suggestions}")
    print(f"   • High priority: {high_priority}")
    print()
    
    # Group by priority
    high_priority_suggestions = []
    medium_priority_suggestions = []
    
    for filename, data in suggestions.items():
        for link in data['suggested_links']:
            suggestion = {
                'source': filename,
                'target': link['target'],
                'reason': link['reason'],
                'filepath': data['filepath']
            }
            
            if link['priority'] == 'high':
                high_priority_suggestions.append(suggestion)
            else:
                medium_priority_suggestions.append(suggestion)
    
    # High Priority Suggestions
    if high_priority_suggestions:
        print("🔴 HIGH PRIORITY LINKS (Essential):")
        print()
        for suggestion in high_priority_suggestions:
            print(f"📄 {suggestion['source']}")
            print(f"   ➤ Add link: [[{suggestion['target']}]]")
            print(f"   💡 Reason: {suggestion['reason']}")
            print()
    
    # Medium Priority Suggestions
    if medium_priority_suggestions:
        print("🟡 MEDIUM PRIORITY LINKS (Recommended):")
        print()
        for suggestion in medium_priority_suggestions[:10]:  # Show first 10
            print(f"📄 {suggestion['source']}")
            print(f"   ➤ Add link: [[{suggestion['target']}]]")
            print(f"   💡 Reason: {suggestion['reason']}")
            print()
        
        if len(medium_priority_suggestions) > 10:
            print(f"   ... and {len(medium_priority_suggestions) - 10} more suggestions")
        print()
    
    # Detailed analysis by note
    print("📋 DETAILED ANALYSIS BY NOTE:")
    print()
    
    for filename, data in suggestions.items():
        print(f"📄 {filename}")
        print(f"   📍 Path: {data['filepath']}")
        print(f"   🔗 Existing links: {len(data['existing_links'])}")
        print(f"   ➕ Suggested links: {len(data['suggested_links'])}")
        
        if data['sections']:
            print(f"   📑 Sections: {', '.join(data['sections'][:3])}")
        
        print()

def generate_link_implementation_guide(suggestions):
    """Generate step-by-step implementation guide"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║              Link Implementation Guide                     ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    print("🎯 IMPLEMENTATION STRATEGY:")
    print()
    print("1. **Start with High Priority Links**")
    print("   • Every Home Assistant note should link to [[Home-Assistant MoC]]")
    print("   • Add these links in the 'Backlink' section of each note")
    print()
    
    print("2. **Add Category-Based Links**")
    print("   • Core notes: Link to OS and installation notes")
    print("   • Integration notes: Link to related integrations")
    print("   • Mobile notes: Link to other mobile integrations")
    print("   • Project notes: Link to related projects")
    print()
    
    print("3. **Content-Based Links**")
    print("   • Add links based on content analysis")
    print("   • Use contextual linking (link where relevant)")
    print()
    
    print("📝 IMPLEMENTATION STEPS:")
    print()
    
    # Group suggestions by source file
    by_file = defaultdict(list)
    for filename, data in suggestions.items():
        for link in data['suggested_links']:
            by_file[filename].append(link)
    
    for filename, links in by_file.items():
        print(f"📄 {filename}")
        
        # Sort by priority
        high_links = [l for l in links if l['priority'] == 'high']
        medium_links = [l for l in links if l['priority'] == 'medium']
        
        if high_links:
            print("   🔴 High Priority:")
            for link in high_links:
                print(f"      • Add [[{link['target']}]] - {link['reason']}")
        
        if medium_links:
            print("   🟡 Medium Priority:")
            for link in medium_links[:3]:  # Show first 3
                print(f"      • Add [[{link['target']}]] - {link['reason']}")
        
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
    
    # Analyze and suggest links
    print("🔗 Analyzing cross-linking opportunities...")
    suggestions = suggest_cross_links(ha_notes)
    
    if not suggestions:
        print("✅ All Home Assistant notes are already well-linked!")
        return
    
    # Generate reports
    generate_link_report(suggestions)
    generate_link_implementation_guide(suggestions)
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                    Next Steps                              ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    print("1. **Review the suggestions above**")
    print("2. **Start with high priority links** (MOC links)")
    print("3. **Add links gradually** - don't overwhelm yourself")
    print("4. **Test links** - make sure they work")
    print("5. **Update MOC** - ensure it includes all notes")
    print()
    print("💡 **Pro Tip**: Add links in context where they're most relevant!")
    print()

if __name__ == "__main__":
    main()
