#!/usr/bin/env python3
"""
Apply Tags - Merge suggested tags with existing tags and update frontmatter.

Apply tags to frontmatter:
- Merge with existing tags
- Remove duplicates
- Sort alphabetically
- Format as YAML list
- Dry-run mode with preview
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List
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
        # Ensure frontmatter is a dict, not a string or other type
        if frontmatter is None:
            frontmatter = {}
        elif not isinstance(frontmatter, dict):
            # If YAML parsed to a non-dict (e.g., string), treat as no frontmatter
            return None, content
        return frontmatter, body
    except yaml.YAMLError:
        return None, content


def apply_tags_to_note(file_path: Path, vault_root: Path, tags_to_add: List[str], backlink: str | None = None, dry_run: bool = True) -> Dict:
    """Apply tags to a note file."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'error',
            'error': str(e)
        }
    
    frontmatter, body = parse_frontmatter(content)
    
    # Get existing tags
    existing_tags = []
    if frontmatter:
        tags_raw = frontmatter.get('tags', [])
        if isinstance(tags_raw, list):
            existing_tags = [str(t) for t in tags_raw]
        elif tags_raw:
            existing_tags = [str(tags_raw)]
    
    # Merge tags (preserve existing, add new, remove duplicates)
    all_tags = existing_tags + tags_to_add
    # Normalize to lowercase for comparison, but preserve original case
    seen = set()
    merged_tags = []
    for tag in all_tags:
        tag_lower = tag.lower()
        if tag_lower not in seen:
            seen.add(tag_lower)
            merged_tags.append(tag)
    
    # Sort alphabetically (case-insensitive)
    merged_tags.sort(key=str.lower)
    
    # Initialize backlink variables
    backlink_added = False
    backlink_formatted = None
    
    # Check if tags actually changed
    existing_normalized = [t.lower() for t in existing_tags]
    merged_normalized = [t.lower() for t in merged_tags]
    tags_changed = set(existing_normalized) != set(merged_normalized)
    
    # Handle backlink if provided
    if backlink:
        # Format backlink as "[[MoC Name]]"
        if not backlink.startswith('[['):
            backlink_formatted = f"[[{backlink}]]"
        else:
            backlink_formatted = backlink
    
    # Check if backlink changed (will be set in new_frontmatter if needed)
    backlink_changed = False
    if backlink:
        existing_backlink = frontmatter.get('Backlink', '') if frontmatter else ''
        existing_backlink_clean = str(existing_backlink).strip().strip('"').strip("'")
        if existing_backlink_clean != backlink_formatted:
            backlink_changed = True
    
    if not tags_changed and not backlink_changed:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'no_change',
            'existing_tags': existing_tags,
            'final_tags': merged_tags
        }
    
    # Build new frontmatter
    new_frontmatter = frontmatter.copy() if frontmatter else {}
    new_frontmatter['tags'] = merged_tags
    
    # Add backlink if changed
    if backlink_changed:
        new_frontmatter['Backlink'] = backlink_formatted
        backlink_added = True
    
    # Build new content
    frontmatter_yaml = yaml.dump(new_frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    new_content = f"---\n{frontmatter_yaml}---\n{body}\n"
    
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
            'existing_tags': existing_tags,
            'added_tags': [t for t in merged_tags if t.lower() not in [e.lower() for e in existing_tags]],
            'final_tags': merged_tags,
            'backlink_added': backlink_added,
            'backlink': backlink_formatted if backlink else None,
            'backup': str(backup_path.relative_to(vault_root))
        }
    else:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'would_update',
            'existing_tags': existing_tags,
            'added_tags': [t for t in merged_tags if t.lower() not in [e.lower() for e in existing_tags]],
            'final_tags': merged_tags,
            'backlink_added': backlink_added,
            'backlink': backlink_formatted if backlink else None
        }


def apply_tags_from_suggestions(
    tag_suggestions_path: str,
    vault_path: str,
    dry_run: bool = True
) -> Dict:
    """Apply tags from tag suggestions JSON file."""
    vault_root = Path(vault_path)
    
    # Load tag suggestions
    with open(tag_suggestions_path, 'r', encoding='utf-8') as f:
        suggestions = json.load(f)
    
    print(f"Applying tags to {len(suggestions)} notes")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print()
    
    results = []
    for i, suggestion in enumerate(suggestions, 1):
        if i % 50 == 0:
            print(f"  Processed {i}/{len(suggestions)} notes...")
        
        file_path = vault_root / suggestion['file']
        if not file_path.exists():
            print(f"  [{i}/{len(suggestions)}] File not found: {suggestion['file']}")
            continue
        
        tags_to_add = suggestion.get('suggested_tags', [])
        backlink = suggestion.get('suggested_backlink')
        
        # Apply even if no tags, if there's a backlink
        if not tags_to_add and not backlink:
            continue
        
        result = apply_tags_to_note(file_path, vault_root, tags_to_add, backlink, dry_run)
        results.append(result)
    
    # Summary
    updated = sum(1 for r in results if r.get('status') == 'updated')
    would_update = sum(1 for r in results if r.get('status') == 'would_update')
    no_change = sum(1 for r in results if r.get('status') == 'no_change')
    errors = sum(1 for r in results if r.get('status') == 'error')
    
    total_tags_added = sum(len(r.get('added_tags', [])) for r in results)
    total_backlinks_added = sum(1 for r in results if r.get('backlink_added', False))
    
    print("\n" + "="*70)
    print("TAG & BACKLINK APPLICATION SUMMARY")
    print("="*70)
    if dry_run:
        print(f"Would update: {would_update}")
    else:
        print(f"Updated: {updated}")
    print(f"No change needed: {no_change}")
    print(f"Errors: {errors}")
    print(f"Total tags to add: {total_tags_added}")
    print(f"Total backlinks to add: {total_backlinks_added}")
    print("="*70)
    
    return {
        'dry_run': dry_run,
        'total': len(results),
        'updated': updated if not dry_run else 0,
        'would_update': would_update if dry_run else 0,
        'no_change': no_change,
        'errors': errors,
        'total_tags_added': total_tags_added,
        'results': results
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Apply tags to notes from suggestions')
    parser.add_argument(
        '--tag-suggestions',
        type=str,
        default='tag_suggestions.json',
        help='Path to tag suggestions JSON file'
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
        help='Output path for results JSON'
    )
    
    args = parser.parse_args()
    
    try:
        results = apply_tags_from_suggestions(
            args.tag_suggestions,
            args.vault_path,
            dry_run=not args.execute
        )
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\nResults saved to: {args.output}")
        
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

