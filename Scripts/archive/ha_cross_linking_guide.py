#!/usr/bin/env python3
"""
Practical Home Assistant Cross-Linking Tool
Creates specific, actionable suggestions based on your MCP search results
"""

def generate_cross_linking_guide():
    """Generate a practical cross-linking guide based on MCP results"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║        Home Assistant Cross-Linking Enhancement Guide     ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    # Based on your MCP search results
    ha_notes = {
        'Home-Assistant MoC.md': {
            'priority': 'HIGH',
            'current_links': ['Home-Assistant MoC'],
            'suggested_additions': [
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
            'reason': 'MOC should be the central hub linking to all major HA topics'
        },
        'Home-Assistant OS.md': {
            'priority': 'HIGH',
            'current_links': ['Home-Assistant MoC'],
            'suggested_additions': [
                'Raspberry Pi Home Assistant',
                'Home Assistant ssh'
            ],
            'reason': 'OS notes should link to installation and access methods'
        },
        'Raspberry Pi Home Assistant.md': {
            'priority': 'HIGH', 
            'current_links': ['Raspberry Pi Projects MOC'],
            'suggested_additions': [
                'Home-Assistant MoC',
                'Home-Assistant OS',
                'Home Assistant ssh'
            ],
            'reason': 'Hardware setup should link to OS and access methods'
        },
        'Home Assistant ssh.md': {
            'priority': 'HIGH',
            'current_links': ['Home-Assistant MoC'],
            'suggested_additions': [
                'Home-Assistant OS',
                'Raspberry Pi Home Assistant'
            ],
            'reason': 'SSH access should link to installation and setup notes'
        },
        'Home-Assistant - Alexa Integration.md': {
            'priority': 'MEDIUM',
            'current_links': ['Home-Assistant MoC'],
            'suggested_additions': [
                '$13 voice assistant for Home Assistant'
            ],
            'reason': 'Voice integrations should cross-reference each other'
        },
        'Sending messages from Home Assistant to SwiftUI app.md': {
            'priority': 'MEDIUM',
            'current_links': ['Home-Assistant MoC'],
            'suggested_additions': [
                'Notification Target',
                'ChatGPT in an iOS Shortcut'
            ],
            'reason': 'Mobile integrations should link to each other'
        },
        'Notification Target.md': {
            'priority': 'MEDIUM',
            'current_links': ['Home-Assistant MoC'],
            'suggested_additions': [
                'Sending messages from Home Assistant to SwiftUI app'
            ],
            'reason': 'Notification systems should cross-reference'
        },
        '$13 voice assistant for Home Assistant.md': {
            'priority': 'MEDIUM',
            'current_links': ['Home-Assistant MoC'],
            'suggested_additions': [
                'Home-Assistant - Alexa Integration'
            ],
            'reason': 'Voice assistants should cross-reference each other'
        }
    }
    
    print("🎯 **CROSS-LINKING STRATEGY**")
    print()
    print("Based on your MCP search results, here are specific suggestions:")
    print()
    
    # High Priority Links
    print("🔴 **HIGH PRIORITY** (Start Here):")
    print()
    
    high_priority = {k: v for k, v in ha_notes.items() if v['priority'] == 'HIGH'}
    
    for filename, data in high_priority.items():
        print(f"📄 **{filename}**")
        print(f"   💡 {data['reason']}")
        print(f"   ➕ Add these links:")
        for link in data['suggested_additions']:
            print(f"      • [[{link}]]")
        print()
    
    # Medium Priority Links
    print("🟡 **MEDIUM PRIORITY** (Next Phase):")
    print()
    
    medium_priority = {k: v for k, v in ha_notes.items() if v['priority'] == 'MEDIUM'}
    
    for filename, data in medium_priority.items():
        print(f"📄 **{filename}**")
        print(f"   💡 {data['reason']}")
        print(f"   ➕ Add these links:")
        for link in data['suggested_additions']:
            print(f"      • [[{link}]]")
        print()

def generate_implementation_examples():
    """Generate specific implementation examples"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                Implementation Examples                     ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    examples = [
        {
            'file': 'Home-Assistant OS.md',
            'section': '### Backlink',
            'current_content': '[[Home-Assistant MoC]]',
            'enhanced_content': '[[Home-Assistant MoC]]\n[[Raspberry Pi Home Assistant]]\n[[Home Assistant ssh]]',
            'explanation': 'Add links to related installation and access methods'
        },
        {
            'file': 'Raspberry Pi Home Assistant.md', 
            'section': '### Backlink',
            'current_content': '[[Raspberry Pi Projects MOC]]',
            'enhanced_content': '[[Raspberry Pi Projects MOC]]\n[[Home-Assistant MoC]]\n[[Home-Assistant OS]]',
            'explanation': 'Link to Home Assistant specific content'
        },
        {
            'file': 'Home Assistant ssh.md',
            'section': '### Reference', 
            'current_content': '- [Debugging the Home Assistant Operating System](https://developer.home-assistant.io/docs/operating-system/debugging/)',
            'enhanced_content': '- [Debugging the Home Assistant Operating System](https://developer.home-assistant.io/docs/operating-system/debugging/)\n- [[Home-Assistant MoC]]\n- [[Home-Assistant OS]]',
            'explanation': 'Add internal links to related notes'
        },
        {
            'file': 'Sending messages from Home Assistant to SwiftUI app.md',
            'section': '### Backlink',
            'current_content': '[[Home-Assistant MoC]]', 
            'enhanced_content': '[[Home-Assistant MoC]]\n[[Notification Target]]\n[[ChatGPT in an iOS Shortcut]]',
            'explanation': 'Link to other mobile integration notes'
        }
    ]
    
    for example in examples:
        print(f"📄 **{example['file']}**")
        print(f"   📍 Section: {example['section']}")
        print(f"   💡 {example['explanation']}")
        print(f"   🔄 Change from:")
        print(f"      {example['current_content']}")
        print(f"   ➡️  To:")
        print(f"      {example['enhanced_content']}")
        print()

def generate_step_by_step_plan():
    """Generate a step-by-step implementation plan"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                Step-by-Step Implementation Plan            ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    print("🎯 **PHASE 1: Core Links (Start Here)**")
    print()
    print("1. **Home-Assistant MoC.md** - Add links to all major topics:")
    print("   • Open the file")
    print("   • Find the main content section")
    print("   • Add links to: Home-Assistant OS, Raspberry Pi Home Assistant, etc.")
    print()
    
    print("2. **Home-Assistant OS.md** - Add installation links:")
    print("   • Add [[Raspberry Pi Home Assistant]] to Backlink section")
    print("   • Add [[Home Assistant ssh]] to Backlink section")
    print()
    
    print("3. **Raspberry Pi Home Assistant.md** - Add OS links:")
    print("   • Add [[Home-Assistant MoC]] to Backlink section")
    print("   • Add [[Home-Assistant OS]] to Backlink section")
    print()
    
    print("4. **Home Assistant ssh.md** - Add setup links:")
    print("   • Add [[Home-Assistant OS]] to Reference section")
    print("   • Add [[Raspberry Pi Home Assistant]] to Reference section")
    print()
    
    print("🎯 **PHASE 2: Integration Links**")
    print()
    print("5. **Voice Integration Cross-Links:**")
    print("   • Home-Assistant - Alexa Integration → Add [[$13 voice assistant for Home Assistant]]")
    print("   • $13 voice assistant for Home Assistant → Add [[Home-Assistant - Alexa Integration]]")
    print()
    
    print("6. **Mobile Integration Cross-Links:**")
    print("   • Sending messages from Home Assistant to SwiftUI app → Add [[Notification Target]]")
    print("   • Notification Target → Add [[Sending messages from Home Assistant to SwiftUI app]]")
    print()
    
    print("🎯 **PHASE 3: Project Links**")
    print()
    print("7. **Project Cross-Links:**")
    print("   • GarageHass Communication Considerations → Add [[Home-Assistant MoC]]")
    print("   • Home Assistant Matter MoC → Add [[Home-Assistant MoC]]")
    print()
    
    print("📝 **IMPLEMENTATION TIPS:**")
    print("• Add links in context where they're most relevant")
    print("• Use the '### Backlink' section for general connections")
    print("• Use inline links for specific references")
    print("• Test all links to ensure they work")
    print("• Update the MOC to include all new connections")
    print()

def generate_quick_reference():
    """Generate a quick reference card"""
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                    Quick Reference Card                    ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    
    print("🔗 **ESSENTIAL LINKS TO ADD:**")
    print()
    
    essential_links = [
        ("Home-Assistant MoC.md", "Add links to ALL major HA topics"),
        ("Home-Assistant OS.md", "Add [[Raspberry Pi Home Assistant]] and [[Home Assistant ssh]]"),
        ("Raspberry Pi Home Assistant.md", "Add [[Home-Assistant MoC]] and [[Home-Assistant OS]]"),
        ("Home Assistant ssh.md", "Add [[Home-Assistant OS]] and [[Raspberry Pi Home Assistant]]"),
        ("Home-Assistant - Alexa Integration.md", "Add [[$13 voice assistant for Home Assistant]]"),
        ("Sending messages from Home Assistant to SwiftUI app.md", "Add [[Notification Target]]"),
        ("Notification Target.md", "Add [[Sending messages from Home Assistant to SwiftUI app]]"),
        ("$13 voice assistant for Home Assistant.md", "Add [[Home-Assistant - Alexa Integration]]")
    ]
    
    for filename, action in essential_links:
        print(f"📄 {filename}")
        print(f"   ➤ {action}")
        print()
    
    print("⚡ **QUICK WIN:** Start with the MOC - add links to all major topics!")
    print()

def main():
    """Main function"""
    generate_cross_linking_guide()
    generate_implementation_examples()
    generate_step_by_step_plan()
    generate_quick_reference()
    
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                    Summary & Next Steps                    ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print()
    print("🎯 **Key Recommendations:**")
    print("1. **Start with Phase 1** - Core links (highest impact)")
    print("2. **Focus on bidirectional links** - Make connections work both ways")
    print("3. **Add links gradually** - Don't overwhelm yourself")
    print("4. **Test links** - Make sure they work")
    print("5. **Update MOC** - Keep it current")
    print()
    print("💡 **Pro Tips:**")
    print("• Add links where they provide the most value to readers")
    print("• Use contextual linking (link where relevant)")
    print("• Consider adding a 'Related Notes' section")
    print("• Regular maintenance keeps links current")
    print()
    print("🚀 **Ready to enhance your Home Assistant cross-linking!**")
    print()

if __name__ == "__main__":
    main()





