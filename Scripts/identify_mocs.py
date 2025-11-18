#!/usr/bin/env python3
"""
Identify MoCs - Distinguish MoC notes from regular notes.

Criteria for MoC identification:
- Filename contains "MoC" (case-insensitive)
- Frontmatter contains tags: [..., "MoC"] or ContentType: MoC
- Content structure suggests index/navigation (links to multiple related notes)
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List
import yaml


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
        # Ensure frontmatter is a dict, not a string or other type
        if frontmatter is None:
            frontmatter = {}
        elif not isinstance(frontmatter, dict):
            # If YAML parsed to a non-dict (e.g., string), treat as no frontmatter
            return None, content
        return frontmatter, body
    except yaml.YAMLError:
        return None, content


def is_moc_note(filename: str, frontmatter: Dict | None, body: str) -> tuple[bool, List[str]]:
    """
    Determine if a note is a MoC.
    Returns (is_moc, reasons).
    """
    reasons = []
    
    # Check filename
    if 'moc' in filename.lower():
        reasons.append('filename_contains_moc')
    
    # Check frontmatter
    if frontmatter:
        # Check tags
        tags = frontmatter.get('tags', [])
        if isinstance(tags, list):
            tag_lower = [str(tag).lower() for tag in tags]
            if 'moc' in tag_lower:
                reasons.append('has_moc_tag')
        
        # Check ContentType
        if frontmatter.get('ContentType') == 'MoC':
            reasons.append('contenttype_moc')
    
    # Check content structure
    # Count internal links
    internal_links = re.findall(r'\[\[([^\]]+)\]\]', body)
    link_count = len(internal_links)
    
    # Check for MoC-like sections
    has_links_section = bool(re.search(r'^##\s+Links', body, re.MULTILINE))
    has_related_mocs = bool(re.search(r'^##\s+Related\s+MoCs', body, re.MULTILINE))
    has_external_resources = bool(re.search(r'^##\s+External\s+Resources', body, re.MULTILINE))
    
    # MoCs typically have many links (index/navigation structure)
    if link_count >= 5:
        reasons.append('many_internal_links')
    
    if has_links_section or has_related_mocs or has_external_resources:
        reasons.append('moc_section_structure')
    
    # Determine if MoC based on reasons
    is_moc = len(reasons) > 0
    
    return is_moc, reasons


def identify_mocs(vault_path: str, output_dir: str = '.') -> Dict:
    """Identify all MoC and regular notes in the vault."""
    vault_root = Path(vault_path)
    if not vault_root.exists():
        raise ValueError(f"Vault path does not exist: {vault_path}")
    
    print(f"Identifying MoCs in vault: {vault_path}")
    print("Scanning markdown files...")
    
    # Find all markdown files
    md_files = list(vault_root.rglob("*.md"))
    print(f"Found {len(md_files)} markdown files")
    
    moc_notes = []
    regular_notes = []
    
    for i, file_path in enumerate(md_files, 1):
        if i % 100 == 0:
            print(f"  Processed {i}/{len(md_files)} files...")
        
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"  Error reading {file_path}: {e}")
            continue
        
        frontmatter, body = parse_frontmatter(content)
        relative_path = str(file_path.relative_to(vault_root))
        filename = file_path.name
        
        is_moc, reasons = is_moc_note(filename, frontmatter, body)
        
        note_info = {
            'file': relative_path,
            'filename': filename,
            'is_moc': is_moc,
            'reasons': reasons,
            'internal_links_count': len(re.findall(r'\[\[([^\]]+)\]\]', body))
        }
        
        if is_moc:
            moc_notes.append(note_info)
        else:
            regular_notes.append(note_info)
    
    # Save results
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)
    
    moc_list_path = output_dir_path / 'moc_list.json'
    regular_list_path = output_dir_path / 'regular_notes_list.json'
    
    with open(moc_list_path, 'w', encoding='utf-8') as f:
        json.dump(moc_notes, f, indent=2, ensure_ascii=False)
    
    with open(regular_list_path, 'w', encoding='utf-8') as f:
        json.dump(regular_notes, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*70)
    print("MoC IDENTIFICATION RESULTS")
    print("="*70)
    print(f"Total files: {len(md_files)}")
    print(f"MoC files: {len(moc_notes)}")
    print(f"Regular files: {len(regular_notes)}")
    print(f"\nMoC list saved to: {moc_list_path}")
    print(f"Regular notes list saved to: {regular_list_path}")
    print("="*70)
    
    return {
        'moc_notes': moc_notes,
        'regular_notes': regular_notes,
        'moc_list_path': str(moc_list_path),
        'regular_list_path': str(regular_list_path)
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Identify MoC vs regular notes')
    parser.add_argument(
        '--vault-path',
        type=str,
        default=os.getenv('OBSIDIAN_VAULT_PATH', '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel'),
        help='Path to Obsidian vault'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='.',
        help='Output directory for JSON lists'
    )
    
    args = parser.parse_args()
    
    try:
        identify_mocs(args.vault_path, args.output_dir)
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

