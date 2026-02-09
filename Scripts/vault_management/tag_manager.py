#!/usr/bin/env python3
"""
Tag Manager for Obsidian Vault
Implements phases of the Vault Semantic Tagging System.

Commands:
    cleanup: Phase 1 - Remove meaningless tags (blocklist, single-occurrence, short/numeric).
    scaffold: Generate a tag mapping template based on existing taxonomy.
    apply: Phase 2 - Apply semantic tags based on the mapping file.
"""

import argparse
import os
import re
import sys
import yaml
from collections import Counter, defaultdict
from pathlib import Path
from datetime import datetime

# Default "useless" tags as per spec
DEFAULT_BLOCKLIST = {
    'temp', 'test', 'debug', 'todo', 'wip', 'draft', 'scratch',
    'speed', 'current', 'old', 'new', 'copy', 'backup'
}

def get_frontmatter(content):
    """Extract frontmatter and body from content."""
    if not content.startswith('---\n'):
        return None, content
    
    parts = content.split('---\n')
    if len(parts) < 3:
        return None, content
    
    frontmatter_raw = parts[1]
    body = '---\n'.join(parts[2:])
    
    try:
        metadata = yaml.safe_load(frontmatter_raw)
        return metadata, body
    except yaml.YAMLError:
        return None, content

def dump_frontmatter(metadata, body):
    """Reconstruct file content with updated metadata."""
    if not metadata:
        return body
    
    # Use sort_keys=False to preserve order if possible, though yaml dicts aren't ordered
    fm_str = yaml.dump(metadata, sort_keys=False, default_flow_style=False).strip()
    return f"---\n{fm_str}\n---\n{body}"

def is_meaningless(tag, count, blocklist):
    """Check if a tag is meaningless based on rules."""
    tag_clean = tag.strip().lower()
    
    # Rule 1: Blocklist
    if tag_clean in blocklist:
        return "Blocklisted"
    
    # Rule 2: Single characters
    if len(tag_clean) <= 1:
        return "Single Character"
    
    # Rule 3: Numeric only
    if tag_clean.isdigit():
        return "Numeric"
        
    # Rule 4: Single occurrence (needs context of vault counts)
    if count == 1:
        return "Single Occurrence"
        
    return None

def scan_tags(vault_path):
    """Scan entire vault for tag frequencies."""
    tag_counts = Counter()
    file_tags = defaultdict(list)
    
    for root, _, files in os.walk(vault_path):
        for file in files:
            if not file.endswith('.md'):
                continue
            
            filepath = Path(root) / file
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                metadata, _ = get_frontmatter(content)
                if metadata and 'tags' in metadata:
                    tags = metadata['tags']
                    # Handle string vs list tags
                    if isinstance(tags, str):
                        tags_list = [t.strip() for t in tags.split(',')]
                    elif isinstance(tags, list):
                        tags_list = tags
                    else:
                        tags_list = []
                    
                    for t in tags_list:
                        if t:
                            tag_counts[t] += 1
                            file_tags[str(filepath)].append(t)
                            
            except Exception as e:
                # print(f"Error reading {filepath}: {e}")
                pass
                
    return tag_counts, file_tags

def cmd_cleanup(args):
    """Execute cleanup command."""
    vault_path = Path(args.vault_path)
    if not vault_path.exists():
        print(f"Error: Vault path {vault_path} does not exist.")
        return

    print("Scanning vault for tags...")
    tag_counts, file_map = scan_tags(vault_path)
    
    removals = defaultdict(list) # reason -> list of tags
    tag_to_reason = {}
    
    for tag, count in tag_counts.items():
        reason = is_meaningless(tag, count, DEFAULT_BLOCKLIST)
        if reason:
            removals[reason].append((tag, count))
            tag_to_reason[tag] = reason

    print("\nProposed Cleanup Plan:")
    print("======================")
    total_removals = 0
    for reason, tags in removals.items():
        print(f"\n[{reason}] - {len(tags)} tags:")
        # Sort by count desc
        sorted_tags = sorted(tags, key=lambda x: x[0])
        for t, c in sorted_tags[:20]:
            print(f"  - {t} (x{c})")
        if len(tags) > 20:
            print(f"  ... and {len(tags)-20} more")
        total_removals += len(tags)
            
    if total_removals == 0:
        print("\nNo meaningless tags found!")
        return

    if args.dry_run:
        print(f"\n[DRY RUN] Would remove {total_removals} unique tags from files.")
        return

    if not args.yes:
        confirm = input("\nProceed with deletion? [y/N] ").lower()
        if confirm != 'y':
            print("Aborted.")
            return

    # Execute Deletion
    updated_files = 0
    for root, _, files in os.walk(vault_path):
        for file in files:
            if not file.endswith('.md'):
                continue
                
            filepath = Path(root) / file
            modified = False
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                metadata, body = get_frontmatter(content)
                if metadata and 'tags' in metadata:
                    original_tags = metadata['tags']
                    new_tags = []
                    
                    if isinstance(original_tags, str):
                        tag_list = [t.strip() for t in original_tags.split(',')]
                    elif isinstance(original_tags, list):
                        tag_list = original_tags
                    else:
                        continue
                        
                    for t in tag_list:
                        if t in tag_to_reason:
                            modified = True
                        else:
                            new_tags.append(t)
                            
                    if modified:
                        metadata['tags'] = new_tags
                        new_content = dump_frontmatter(metadata, body)
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        updated_files += 1
                        
            except Exception as e:
                print(f"Error processing {filepath}: {e}")

    print(f"\nCleanup complete. Updated {updated_files} files.")

def cmd_scaffold(args):
    """Execute scaffold command."""
    vault_path = Path(args.vault_path)
    output_path = Path("tag_mapping.yaml")
    
    print("Analyzing vault structure...")
    tag_counts, file_map = scan_tags(vault_path)
    
    # Get top tags to suggest as "Corpus Tags"
    top_tags = [t for t, c in tag_counts.most_common(50) if not is_meaningless(t, c, DEFAULT_BLOCKLIST)]
    
    scaffold = {
        "config": {
            "tier1_categories": [
                "treatment", "drug", "diagnostic", "concept", 
                "prognosis", "side-effect", "procedure", "doctor", "journal"
            ],
            "tier2_categories": [
                "car-t", "asct", "gcb", "double-hit", "relapse", "general"
            ]
        },
        "files": {}
    }
    
    print(f"Found {len(file_map)} files with tags.")
    
    for filepath_str, tags in file_map.items():
        fname = Path(filepath_str).name
        # Simple heuristic suggestion based on filename or existing tags
        suggested_t1 = "?"
        suggested_t2 = "?"
        
        # Check if any existing tag matches a top corpus tag
        current_matches = [t for t in tags if t in top_tags]
        
        scaffold["files"][fname] = {
            "current_tags": tags,
            "tier1": suggested_t1,
            "tier2": suggested_t2,
            "suggested_corpus_tags": current_matches
        }

    with open(output_path, 'w') as f:
        yaml.dump(scaffold, f, sort_keys=False)
        
    print(f"\nGenerated {output_path} with {len(scaffold['files'])} entries.")
    print("Please edit this file to define your mappings before running 'apply'.")

def cmd_apply(args):
    """Execute apply command."""
    mapping_path = Path(args.mapping)
    if not mapping_path.exists():
        print(f"Error: Mapping file {mapping_path} not found.")
        return
        
    with open(mapping_path, 'r') as f:
        config = yaml.safe_load(f)
        
    file_mappings = config.get('files', {})
    vault_path = Path(args.vault_path)
    
    updates = 0
    allowed_t1 = set(config.get('config', {}).get('tier1_categories', []))
    
    for root, _, files in os.walk(vault_path):
        for file in files:
            if file not in file_mappings:
                continue
                
            entry = file_mappings[file]
            t1 = entry.get('tier1')
            t2 = entry.get('tier2')
            
            # Skip if not configured
            if t1 == '?' or not t1:
                continue
                
            if t1 not in allowed_t1:
                print(f"Warning: {file} has invalid Tier 1 tag '{t1}'")
                continue

            filepath = Path(root) / file
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                metadata, body = get_frontmatter(content)
                if metadata is None:
                    metadata = {}
                    
                tags = metadata.get('tags', [])
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(',')]
                
                # Add semantic tags
                if t1 and t1 not in tags:
                    tags.append(t1)
                if t2 and t2 != '?' and t2 not in tags:
                    tags.append(t2)
                    
                metadata['tags'] = tags
                
                # Write back
                new_content = dump_frontmatter(metadata, body)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                updates += 1
                
            except Exception as e:
                print(f"Error applying tags to {file}: {e}")
                
    print(f"Applied semantic tags to {updates} files.")

def main():
    parser = argparse.ArgumentParser(description="Obsidian Vault Tag Manager")
    parser.add_argument("--vault-path", default=os.environ.get("OBSIDIAN_VAULT_PATH", "."), help="Path to vault root")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Cleanup Command
    p_clean = subparsers.add_parser("cleanup", help="Remove meaningless tags")
    p_clean.add_argument("--dry-run", action="store_true", help="Show what would be removed without deleting")
    p_clean.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    
    # Scaffold Command
    p_scaffold = subparsers.add_parser("scaffold", help="Generate mapping template")
    
    # Apply Command
    p_apply = subparsers.add_parser("apply", help="Apply tags from mapping file")
    p_apply.add_argument("--mapping", default="tag_mapping.yaml", help="Path to mapping file")
    
    args = parser.parse_args()
    
    if args.command == "cleanup":
        cmd_cleanup(args)
    elif args.command == "scaffold":
        cmd_scaffold(args)
    elif args.command == "apply":
        cmd_apply(args)

if __name__ == "__main__":
    main()
