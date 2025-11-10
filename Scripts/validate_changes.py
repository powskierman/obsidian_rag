#!/usr/bin/env python3
"""
Validate Changes - Verify template structure, tags, links, and file accessibility after changes.

After each batch:
- Verify template structure
- Verify tags are valid
- Verify links still work
- Verify files are accessible
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
    except yaml.YAMLError as e:
        return {'_yaml_error': str(e)}, content


def validate_template_structure(frontmatter: Dict | None, body: str, is_moc: bool) -> List[str]:
    """Validate template structure. Returns list of issues."""
    issues = []
    
    if not frontmatter:
        issues.append('Missing frontmatter')
        return issues
    
    if '_yaml_error' in frontmatter:
        issues.append(f'YAML syntax error: {frontmatter["_yaml_error"]}')
        return issues
    
    # Check required fields
    if 'created' not in frontmatter:
        issues.append('Missing "created" field')
    
    if is_moc:
        # MoC template checks
        if 'tags' not in frontmatter:
            issues.append('Missing "tags" field')
        else:
            tags = frontmatter.get('tags', [])
            if isinstance(tags, list) and 'MoC' not in [str(t).lower() for t in tags]:
                issues.append('MoC note missing "MoC" tag')
        
        # Check for MoC sections
        if not re.search(r'^##\s+Links', body, re.MULTILINE):
            issues.append('Missing "## Links" section')
        if not re.search(r'^##\s+Notes', body, re.MULTILINE):
            issues.append('Missing "## Notes" section')
    else:
        # New Note template checks
        if not re.search(r'^###\s+Main\s+Idea', body, re.MULTILINE | re.IGNORECASE):
            issues.append('Missing "### Main Idea" section')
        if not re.search(r'^###\s+Notes', body, re.MULTILINE | re.IGNORECASE):
            issues.append('Missing "### Notes" section')
    
    return issues


def validate_tags(frontmatter: Dict | None) -> List[str]:
    """Validate tags. Returns list of issues."""
    issues = []
    
    if not frontmatter:
        return issues
    
    tags = frontmatter.get('tags', [])
    if tags:
        if not isinstance(tags, list):
            issues.append('Tags should be a list')
        else:
            # Check for empty tags
            if any(not str(tag).strip() for tag in tags):
                issues.append('Empty tag found')
            # Check for duplicate tags (case-insensitive)
            tag_lower = [str(t).lower() for t in tags]
            if len(tag_lower) != len(set(tag_lower)):
                issues.append('Duplicate tags found')
    
    return issues


def validate_links(file_path: Path, vault_root: Path) -> List[str]:
    """Validate internal links. Returns list of issues."""
    issues = []
    
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception:
        issues.append('Cannot read file')
        return issues
    
    # Extract internal links
    internal_links = re.findall(r'\[\[([^\]]+)\]\]', content)
    
    for link in internal_links:
        # Check if linked file exists
        # Try different possible paths
        possible_paths = [
            vault_root / f"{link}.md",
            vault_root / link / "index.md",
        ]
        
        # Also try with folder structure
        if '/' in link:
            possible_paths.append(vault_root / f"{link}.md")
        
        found = False
        for path in possible_paths:
            if path.exists():
                found = True
                break
        
        if not found:
            issues.append(f'Broken link: [[{link}]]')
    
    return issues


def validate_file_accessibility(file_path: Path) -> List[str]:
    """Validate file is accessible. Returns list of issues."""
    issues = []
    
    if not file_path.exists():
        issues.append('File does not exist')
        return issues
    
    if not file_path.is_file():
        issues.append('Path is not a file')
        return issues
    
    try:
        content = file_path.read_text(encoding='utf-8')
        if not content:
            issues.append('File is empty')
    except Exception as e:
        issues.append(f'Cannot read file: {e}')
    
    return issues


def validate_note(file_path: Path, vault_root: Path, is_moc: bool) -> Dict:
    """Validate a single note."""
    issues = {
        'template': [],
        'tags': [],
        'links': [],
        'accessibility': []
    }
    
    # Validate accessibility
    issues['accessibility'] = validate_file_accessibility(file_path)
    if issues['accessibility']:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'error',
            'issues': issues
        }
    
    # Read content
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'error',
            'error': str(e),
            'issues': issues
        }
    
    # Parse frontmatter
    frontmatter, body = parse_frontmatter(content)
    
    # Validate template structure
    issues['template'] = validate_template_structure(frontmatter, body, is_moc)
    
    # Validate tags
    issues['tags'] = validate_tags(frontmatter)
    
    # Validate links
    issues['links'] = validate_links(file_path, vault_root)
    
    # Determine status
    total_issues = sum(len(v) for v in issues.values())
    if total_issues == 0:
        status = 'valid'
    elif issues['accessibility']:
        status = 'error'
    else:
        status = 'issues'
    
    return {
        'file': str(file_path.relative_to(vault_root)),
        'status': status,
        'issues': issues,
        'total_issues': total_issues
    }


def validate_changes(
    notes_list_path: str,
    vault_path: str,
    is_moc_list: bool = False
) -> Dict:
    """Validate changes for all notes."""
    vault_root = Path(vault_path)
    
    # Load notes list
    with open(notes_list_path, 'r', encoding='utf-8') as f:
        notes_list = json.load(f)
    
    print(f"Validating {len(notes_list)} notes")
    print()
    
    results = []
    for i, note_info in enumerate(notes_list, 1):
        if i % 50 == 0:
            print(f"  Validated {i}/{len(notes_list)} notes...")
        
        file_path = vault_root / note_info['file']
        if not file_path.exists():
            continue
        
        # Determine if MoC
        is_moc = note_info.get('is_moc', False) if 'is_moc' in note_info else is_moc_list
        
        result = validate_note(file_path, vault_root, is_moc)
        results.append(result)
    
    # Summary
    valid = sum(1 for r in results if r.get('status') == 'valid')
    issues = sum(1 for r in results if r.get('status') == 'issues')
    errors = sum(1 for r in results if r.get('status') == 'error')
    
    total_template_issues = sum(len(r.get('issues', {}).get('template', [])) for r in results)
    total_tag_issues = sum(len(r.get('issues', {}).get('tags', [])) for r in results)
    total_link_issues = sum(len(r.get('issues', {}).get('links', [])) for r in results)
    
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    print(f"Total notes: {len(results)}")
    print(f"Valid: {valid}")
    print(f"With issues: {issues}")
    print(f"Errors: {errors}")
    print(f"\nIssue breakdown:")
    print(f"  Template issues: {total_template_issues}")
    print(f"  Tag issues: {total_tag_issues}")
    print(f"  Link issues: {total_link_issues}")
    print("="*70)
    
    return {
        'total': len(results),
        'valid': valid,
        'issues': issues,
        'errors': errors,
        'template_issues': total_template_issues,
        'tag_issues': total_tag_issues,
        'link_issues': total_link_issues,
        'results': results
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate vault changes')
    parser.add_argument(
        '--notes-list',
        type=str,
        required=True,
        help='Path to notes list JSON file'
    )
    parser.add_argument(
        '--vault-path',
        type=str,
        default=os.getenv('OBSIDIAN_VAULT_PATH', '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel'),
        help='Path to Obsidian vault'
    )
    parser.add_argument(
        '--is-moc-list',
        action='store_true',
        help='Treat all notes in list as MoCs'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output path for validation results JSON'
    )
    
    args = parser.parse_args()
    
    try:
        results = validate_changes(
            args.notes_list,
            args.vault_path,
            args.is_moc_list
        )
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\nValidation results saved to: {args.output}")
        
        sys.exit(0 if results['errors'] == 0 else 1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

