#!/usr/bin/env python3
"""
Remove Broken Links - Remove links to non-existent notes and fix Backlink format.

This script:
- Scans all notes for internal links [[Note Name]]
- Checks if linked notes exist
- Removes links to non-existent notes
- Fixes Backlink format (should be single link, not multiple)
- Supports dry-run and execute modes
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set
import yaml
import shutil


def parse_frontmatter(content: str) -> tuple[Dict | None, str]:
    """Extract frontmatter from markdown content."""
    frontmatter_pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(frontmatter_pattern, content, re.DOTALL)
    
    if not match:
        return None, content
    
    frontmatter_text = match.group(1)
    body = match.group(2)
    
    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if frontmatter is None:
            frontmatter = {}
        elif not isinstance(frontmatter, dict):
            return None, content
        return frontmatter, body
    except yaml.YAMLError:
        return None, content


def find_all_notes(vault_root: Path) -> Set[str]:
    """Find all existing note files and return their names (without extension)."""
    notes = set()
    
    for md_file in vault_root.rglob("*.md"):
        # Skip backup files
        if md_file.name.endswith('.backup'):
            continue
        
        # Get note name without extension
        note_name = md_file.stem
        notes.add(note_name)
        
        # Also add with path (relative to vault)
        relative_path = md_file.relative_to(vault_root)
        # Add path variants
        notes.add(str(relative_path).replace('\\', '/'))
        notes.add(str(relative_path.with_suffix('')).replace('\\', '/'))
    
    return notes


def extract_links_from_content(content: str) -> List[str]:
    """Extract all internal links [[Note Name]] from content."""
    # Pattern to match [[Note Name]] or [[Note Name|Display Text]]
    link_pattern = r'\[\[([^\]]+)\]\]'
    matches = re.findall(link_pattern, content)
    
    links = []
    for match in matches:
        # Handle [[Note Name|Display Text]] format
        link_name = match.split('|')[0].strip()
        links.append(link_name)
    
    return links


def find_broken_links(content: str, existing_notes: Set[str]) -> List[str]:
    """Find all links in content that point to non-existent notes."""
    links = extract_links_from_content(content)
    broken = []
    
    for link in links:
        # Check if note exists (try multiple variations)
        link_lower = link.lower()
        found = False
        
        # Check exact match
        if link in existing_notes:
            found = True
        
        # Check case-insensitive
        for note in existing_notes:
            if note.lower() == link_lower:
                found = True
                break
        
        # Check if it's a path (with slashes)
        if '/' in link or '\\' in link:
            # Try to find matching file
            link_path = link.replace('\\', '/')
            for note in existing_notes:
                if note.replace('\\', '/').lower() == link_path.lower():
                    found = True
                    break
        
        if not found:
            broken.append(link)
    
    return broken


def remove_broken_links_from_content(content: str, broken_links: List[str]) -> str:
    """Remove broken links from content."""
    if not broken_links:
        return content
    
    # Create a set for faster lookup
    broken_set = {link.lower() for link in broken_links}
    
    # Pattern to match [[Note Name]] or [[Note Name|Display Text]]
    def replace_link(match):
        full_match = match.group(0)  # [[...]]
        link_content = match.group(1)  # content inside brackets
        link_name = link_content.split('|')[0].strip()
        
        if link_name.lower() in broken_set:
            # Remove the link, keep display text if present
            if '|' in link_content:
                return link_content.split('|', 1)[1].strip()
            else:
                return ''  # Remove the entire link
        
        return full_match  # Keep the link
    
    link_pattern = r'\[\[([^\]]+)\]\]'
    content = re.sub(link_pattern, replace_link, content)
    
    # Clean up empty list items (lines with just "- " or "-" or "-  " etc.)
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        # Skip lines that are just "- " or "-" followed by only whitespace (empty list items)
        stripped = line.strip()
        if stripped == '-' or stripped == '':
            continue
        cleaned_lines.append(line)
    content = '\n'.join(cleaned_lines)
    
    # Clean up multiple consecutive empty lines (more than 2)
    content = re.sub(r'\n{3,}', '\n\n', content)
    
    return content


def fix_backlink_format(frontmatter: Dict) -> tuple[Dict, bool]:
    """Fix Backlink format - should be single link, not multiple."""
    if 'Backlink' not in frontmatter:
        return frontmatter, False
    
    backlink = frontmatter.get('Backlink', '')
    if not backlink:
        return frontmatter, False
    
    # Convert to string if needed
    if not isinstance(backlink, str):
        backlink = str(backlink)
    
    # Check if it contains multiple links (separated by | or ,)
    if '|' in backlink or ',' in backlink:
        # Extract first link
        if '|' in backlink:
            first_link = backlink.split('|')[0].strip()
        else:
            first_link = backlink.split(',')[0].strip()
        
        # Ensure it's in [[Link]] format
        if not first_link.startswith('[['):
            first_link = f"[[{first_link}]]"
        elif first_link.startswith('[[') and not first_link.endswith(']]'):
            # Might have extra characters
            first_link = first_link.split('[')[-1].split(']')[0]
            first_link = f"[[{first_link}]]"
        
        frontmatter['Backlink'] = first_link
        return frontmatter, True
    
    # Clean up existing backlink format
    backlink_clean = backlink.strip().strip('"').strip("'")
    if backlink_clean != backlink:
        frontmatter['Backlink'] = backlink_clean
        return frontmatter, True
    
    return frontmatter, False


def process_note(file_path: Path, vault_root: Path, existing_notes: Set[str], dry_run: bool = True) -> Dict:
    """Process a single note to remove broken links."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'error',
            'error': str(e)
        }
    
    frontmatter, body = parse_frontmatter(content)
    
    if not frontmatter:
        frontmatter = {}
    
    # Find broken links in body
    broken_links_body = find_broken_links(body, existing_notes)
    
    # Find broken links in frontmatter (Backlink field)
    broken_links_frontmatter = []
    if 'Backlink' in frontmatter:
        backlink = frontmatter.get('Backlink', '')
        if backlink:
            backlink_str = str(backlink)
            # Extract links from backlink
            backlink_links = extract_links_from_content(backlink_str)
            for link in backlink_links:
                link_lower = link.lower()
                found = False
                for note in existing_notes:
                    if note.lower() == link_lower:
                        found = True
                        break
                if not found:
                    broken_links_frontmatter.append(link)
    
    # Fix Backlink format
    frontmatter, backlink_fixed = fix_backlink_format(frontmatter)
    
    # Remove broken links from body
    new_body = remove_broken_links_from_content(body, broken_links_body)
    
    # Remove broken links from Backlink
    if broken_links_frontmatter and 'Backlink' in frontmatter:
        backlink = frontmatter.get('Backlink', '')
        if backlink:
            backlink_str = str(backlink)
            # Remove broken links from backlink
            for broken_link in broken_links_frontmatter:
                # Remove the broken link
                backlink_str = re.sub(rf'\[\[{re.escape(broken_link)}\]\]', '', backlink_str)
                backlink_str = re.sub(rf'\[\[{re.escape(broken_link)}\|[^\]]+\]\]', '', backlink_str)
                # Also remove if it's part of a pipe-separated list
                backlink_str = re.sub(rf'\s*\|\s*\[\[{re.escape(broken_link)}\]\]', '', backlink_str)
                backlink_str = re.sub(rf'\[\[{re.escape(broken_link)}\]\]\s*\|\s*', '', backlink_str)
            
            backlink_str = backlink_str.strip()
            if backlink_str:
                # Fix format - should be single link
                if '|' in backlink_str:
                    first_link = backlink_str.split('|')[0].strip()
                    if not first_link.startswith('[['):
                        first_link = f"[[{first_link}]]"
                    backlink_str = first_link
                frontmatter['Backlink'] = backlink_str
            else:
                # Remove Backlink if empty
                del frontmatter['Backlink']
    
    # Check if anything changed
    all_broken = broken_links_body + broken_links_frontmatter
    if not all_broken and not backlink_fixed:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'no_change',
            'broken_links': []
        }
    
    # Build new content
    if frontmatter:
        frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
        new_content = f"---\n{frontmatter_yaml}---\n{new_body}\n"
    else:
        new_content = new_body
    
    # Apply changes
    if not dry_run:
        # Create backup
        backup_path = file_path.with_suffix('.md.backup')
        shutil.copy2(file_path, backup_path)
        
        # Write new content
        file_path.write_text(new_content, encoding='utf-8')
        
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'updated',
            'broken_links_removed': all_broken,
            'backlink_fixed': backlink_fixed,
            'backup': str(backup_path.relative_to(vault_root))
        }
    else:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'would_update',
            'broken_links_removed': all_broken,
            'backlink_fixed': backlink_fixed
        }


def process_all_notes(
    notes_list_path: str,
    vault_path: str,
    dry_run: bool = True,
    output_path: str = 'broken_links_removal_results.json'
) -> Dict:
    """Process all notes to remove broken links."""
    vault_root = Path(vault_path)
    
    # Load notes list
    with open(notes_list_path, 'r', encoding='utf-8') as f:
        notes_list = json.load(f)
    
    print(f"Building index of existing notes...")
    existing_notes = find_all_notes(vault_root)
    print(f"Found {len(existing_notes)} existing notes")
    
    print(f"\nProcessing {len(notes_list)} notes")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print()
    
    results = []
    for i, note_info in enumerate(notes_list, 1):
        if i % 50 == 0:
            print(f"  Processed {i}/{len(notes_list)} notes...")
        
        file_path = vault_root / note_info['file']
        if not file_path.exists():
            continue
        
        result = process_note(file_path, vault_root, existing_notes, dry_run)
        results.append(result)
    
    # Summary
    updated = sum(1 for r in results if r.get('status') == 'updated')
    would_update = sum(1 for r in results if r.get('status') == 'would_update')
    no_change = sum(1 for r in results if r.get('status') == 'no_change')
    total_broken_removed = sum(len(r.get('broken_links_removed', [])) for r in results)
    backlinks_fixed = sum(1 for r in results if r.get('backlink_fixed', False))
    
    print("\n" + "="*70)
    print("BROKEN LINKS REMOVAL SUMMARY")
    print("="*70)
    if dry_run:
        print(f"Would update: {would_update}")
    else:
        print(f"Updated: {updated}")
    print(f"No change needed: {no_change}")
    print(f"Total broken links to remove: {total_broken_removed}")
    print(f"Backlinks to fix: {backlinks_fixed}")
    print("="*70)
    
    # Save results
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {output_path}")
    
    return {
        'dry_run': dry_run,
        'total': len(results),
        'updated': updated if not dry_run else 0,
        'would_update': would_update if dry_run else 0,
        'no_change': no_change,
        'total_broken_links_removed': total_broken_removed,
        'backlinks_fixed': backlinks_fixed,
        'results': results
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Remove broken links from notes')
    parser.add_argument(
        '--notes-list',
        type=str,
        default='regular_notes_list.json',
        help='Path to notes list JSON file'
    )
    parser.add_argument(
        '--vault-path',
        type=str,
        default=os.getenv('OBSIDIAN_VAULT_PATH', '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel'),
        help='Path to Obsidian vault'
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Execute changes (default is dry-run)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='broken_links_removal_results.json',
        help='Output path for results JSON'
    )
    
    args = parser.parse_args()
    
    try:
        process_all_notes(
            args.notes_list,
            args.vault_path,
            dry_run=not args.execute,
            output_path=args.output
        )
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

