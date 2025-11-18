#!/usr/bin/env python3
"""
Apply New Note Template - Standardize regular notes using New Note Template.md structure.

For each regular note:
- Read current content
- Extract existing metadata
- Apply New Note template structure while preserving existing content
- Dry-run mode by default
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
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


def extract_section_content(body: str, section_name: str) -> str:
    """Extract content from a specific section."""
    pattern = rf'^###\s+{re.escape(section_name)}\s*\n(.*?)(?=\n###|\Z)'
    match = re.search(pattern, body, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ''


def extract_main_idea(body: str) -> str:
    """Extract or generate main idea from content."""
    # Try to extract from existing section
    main_idea = extract_section_content(body, 'Main Idea')
    if main_idea:
        # Clean up - remove leading dashes/bullets
        main_idea = re.sub(r'^[-*+]\s+', '', main_idea, flags=re.MULTILINE)
        main_idea = main_idea.strip()
        if main_idea:
            return main_idea
    
    # Try to extract first paragraph or heading
    lines = body.strip().split('\n')
    for i, line in enumerate(lines[:10]):  # Check first 10 lines
        line = line.strip()
        if line and not line.startswith('#') and not line.startswith('Date:'):
            # Return first substantial line
            if len(line) > 20:
                # Remove leading dashes/bullets
                line = re.sub(r'^[-*+]\s+', '', line)
                return line.strip()
    
    return ''


def extract_references(body: str) -> List[str]:
    """Extract reference links from content."""
    references = []
    seen_refs = set()
    
    # Extract from References section (try both "Reference" and "References")
    ref_section = extract_section_content(body, 'References')
    if not ref_section:
        ref_section = extract_section_content(body, 'Reference')
    
    if ref_section:
        # Extract links from section
        links = re.findall(r'\[\[([^\]]+)\]\]|\[([^\]]+)\]\(([^\)]+)\)', ref_section)
        for link in links:
            if link[0]:  # Internal link
                ref_str = f"[[{link[0]}]]"
                if ref_str not in seen_refs:
                    seen_refs.add(ref_str)
                    references.append(ref_str)
            elif link[2]:  # External link
                ref_str = f"[{link[1]}]({link[2]})"
                if ref_str not in seen_refs:
                    seen_refs.add(ref_str)
                    references.append(ref_str)
    
    # Also extract external URLs from entire body (but not from already extracted sections)
    # Skip links that are just "[ref]" or similar generic text
    external_links = re.findall(r'\[([^\]]+)\]\(([^\)]+)\)', body)
    for text, url in external_links:
        if url.startswith('http'):
            # Skip generic reference markers like [ref]
            if text.lower() in ['ref', 'reference', 'link', 'url']:
                continue
            ref_str = f"[{text}]({url})"
            if ref_str not in seen_refs:
                seen_refs.add(ref_str)
                references.append(ref_str)
    
    return references


def extract_related_notes(body: str) -> List[str]:
    """Extract related notes (internal links) from content."""
    # Extract from Related Notes section
    related_section = extract_section_content(body, 'Related Notes')
    if related_section:
        links = re.findall(r'\[\[([^\]]+)\]\]', related_section)
        return [f"[[{link}]]" for link in links]
    
    # Extract all internal links from body
    all_links = re.findall(r'\[\[([^\]]+)\]\]', body)
    # Remove duplicates while preserving order
    seen = set()
    unique_links = []
    for link in all_links:
        if link not in seen:
            seen.add(link)
            unique_links.append(f"[[{link}]]")
    
    return unique_links[:10]  # Limit to 10 most relevant


def extract_questions(body: str) -> List[str]:
    """Extract questions from content."""
    questions = []
    
    # Extract from Questions section
    q_section = extract_section_content(body, 'Questions / Ideas for Further Exploration')
    if q_section:
        # Split by lines and filter for questions
        for line in q_section.split('\n'):
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('*')):
                line = line.lstrip('-* ').strip()
                if line.endswith('?'):
                    questions.append(line)
    
    # Also search for question patterns in body
    question_pattern = r'([A-Z][^.!?]*\?)'
    matches = re.findall(question_pattern, body)
    questions.extend(matches[:5])  # Limit to 5
    
    return list(set(questions))  # Remove duplicates


def extract_todos(body: str) -> List[str]:
    """Extract todo items from content."""
    todos = []
    
    # Extract from To-Do section
    todo_section = extract_section_content(body, 'To-Do')
    if todo_section:
        for line in todo_section.split('\n'):
            line = line.strip()
            if line and (line.startswith('-') or line.startswith('*') or line.startswith('[')):
                line = line.lstrip('-*[] ').strip()
                if line:
                    todos.append(line)
    
    # Also search for markdown task list items
    task_pattern = r'- \[[ x]\]\s*(.+)'
    matches = re.findall(task_pattern, body)
    todos.extend(matches)
    
    return list(set(todos))  # Remove duplicates


def determine_content_type(filename: str, body: str) -> str:
    """Determine ContentType based on filename and content."""
    filename_lower = filename.lower()
    
    # Check filename patterns
    if 'moc' in filename_lower:
        return 'MoC'
    if 'project' in filename_lower or 'setup' in filename_lower:
        return 'Project'
    if 'tutorial' in filename_lower or 'guide' in filename_lower:
        return 'Tutorial'
    if 'reference' in filename_lower or 'cheatsheet' in filename_lower:
        return 'Reference'
    if 'meeting' in filename_lower or 'agenda' in filename_lower:
        return 'Meeting'
    if 'question' in filename_lower:
        return 'Question'
    
    # Check content patterns
    if re.search(r'^#\s+.*\s+MoC', body, re.MULTILINE | re.IGNORECASE):
        return 'MoC'
    
    return ''


def extract_backlink_from_content(content: str) -> str:
    """Extract backlink section from content."""
    backlink_pattern = r'###?\s+Backlink\s*\n(.*?)(?=\n##|\Z)'
    match = re.search(backlink_pattern, content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ''


def apply_new_note_template(file_path: Path, vault_root: Path, template_path: Path, dry_run: bool = True) -> Dict:
    """Apply New Note template to a note file."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'error',
            'error': str(e)
        }
    
    # Read template
    try:
        template_content = template_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'error',
            'error': f'Failed to read template: {e}'
        }
    
    # Parse existing content
    frontmatter, body = parse_frontmatter(content)
    
    # Extract existing metadata
    existing_aliases = []
    existing_tags = []
    existing_created = None
    existing_content_type = ''
    existing_backlink = ''
    
    if frontmatter:
        aliases_raw = frontmatter.get('aliases', [])
        if isinstance(aliases_raw, list):
            existing_aliases = [str(a) for a in aliases_raw]
        elif aliases_raw:
            existing_aliases = [str(aliases_raw)]
        
        tags_raw = frontmatter.get('tags', [])
        if isinstance(tags_raw, list):
            existing_tags = [str(t) for t in tags_raw]
        elif tags_raw:
            existing_tags = [str(tags_raw)]
        
        existing_created = frontmatter.get('created')
        existing_content_type = frontmatter.get('ContentType', '')
        existing_backlink = frontmatter.get('Backlink', '')
    
    # Extract backlink from content if not in frontmatter
    if not existing_backlink:
        existing_backlink = extract_backlink_from_content(content)
        # Clean up backlink - remove empty brackets
        if existing_backlink and existing_backlink.strip() in ['[[]]', '[]', '']:
            existing_backlink = ''
    
    # Extract date from body if present (format: "Date: YYYY-MM-DD")
    if not existing_created:
        date_match = re.search(r'^Date:\s*(\d{4}-\d{2}-\d{2})', body, re.MULTILINE | re.IGNORECASE)
        if date_match:
            existing_created = date_match.group(1) + ' 00:00'
    
    # Determine ContentType if not set
    if not existing_content_type:
        existing_content_type = determine_content_type(file_path.name, body)
    
    # Extract structured content
    main_idea = extract_main_idea(body)
    references = extract_references(body)
    related_notes = extract_related_notes(body)
    questions = extract_questions(body)
    todos = extract_todos(body)
    
    # Build new frontmatter
    new_frontmatter = {
        'aliases': existing_aliases if existing_aliases else None,
        'tags': existing_tags if existing_tags else None,
        'created': existing_created or datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M'),
        'ContentType': existing_content_type if existing_content_type else None,
        'Backlink': existing_backlink if existing_backlink else None
    }
    
    # Remove None values
    new_frontmatter = {k: v for k, v in new_frontmatter.items() if v is not None}
    
    # Build new body with New Note structure
    new_body_parts = []
    
    # Main Idea section
    new_body_parts.append('### Main Idea')
    if main_idea:
        new_body_parts.append(f'- {main_idea}')
    else:
        new_body_parts.append('-')
    new_body_parts.append('')
    
    # References section
    new_body_parts.append('### References')
    if references:
        for ref in references[:10]:  # Limit to 10
            new_body_parts.append(f'- {ref}')
    else:
        new_body_parts.append('-')
    new_body_parts.append('')
    
    # Notes section - preserve existing content
    new_body_parts.append('### Notes')
    
    # Preserve original body content, but try to extract structured parts
    body_cleaned = body
    # Remove title if it's an H1 heading (filename is the title)
    body_cleaned = re.sub(r'^#\s+[^\n]+\n', '', body_cleaned, flags=re.MULTILINE)
    # Remove date line if present
    body_cleaned = re.sub(r'^Date:\s*\d{4}-\d{2}-\d{2}\s*\n', '', body_cleaned, flags=re.MULTILINE | re.IGNORECASE)
    # Remove already extracted sections (be careful with Notes section - only remove if it's empty or just a dash)
    body_cleaned = re.sub(r'^###\s+Main\s+Idea.*?(?=\n###|\Z)', '', body_cleaned, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
    body_cleaned = re.sub(r'^###\s+Reference(s)?.*?(?=\n###|\Z)', '', body_cleaned, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
    body_cleaned = re.sub(r'^###\s+Backlink.*?(?=\n###|\Z)', '', body_cleaned, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
    # For Notes section, only remove if it's empty or just contains a dash
    notes_section_match = re.search(r'^###\s+Notes\s*\n(.*?)(?=\n###|\Z)', body_cleaned, re.DOTALL | re.MULTILINE | re.IGNORECASE)
    if notes_section_match:
        notes_content = notes_section_match.group(1).strip()
        # Only remove if it's empty or just a dash
        if notes_content in ['', '-', '*']:
            body_cleaned = re.sub(r'^###\s+Notes\s*\n.*?(?=\n###|\Z)', '', body_cleaned, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
        else:
            # Extract the content but remove the section header
            body_cleaned = re.sub(r'^###\s+Notes\s*\n', '', body_cleaned, flags=re.MULTILINE | re.IGNORECASE)
    body_cleaned = re.sub(r'^###\s+Related\s+Notes.*?(?=\n###|\Z)', '', body_cleaned, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
    body_cleaned = re.sub(r'^###\s+Questions.*?(?=\n###|\Z)', '', body_cleaned, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
    body_cleaned = re.sub(r'^###\s+To-Do.*?(?=\n###|\Z)', '', body_cleaned, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
    body_cleaned = re.sub(r'^###\s+Smart\s+Connections.*?(?=\n###|\Z)', '', body_cleaned, flags=re.DOTALL | re.MULTILINE | re.IGNORECASE)
    
    # Add cleaned body content
    body_cleaned = body_cleaned.strip()
    if body_cleaned:
        # If it starts with a list item or bullet, add it directly
        if body_cleaned.startswith('-') or body_cleaned.startswith('*'):
            new_body_parts.append(body_cleaned)
        else:
            # Otherwise, add as a list item
            new_body_parts.append(f'- {body_cleaned}')
    else:
        new_body_parts.append('-')
    new_body_parts.append('')
    
    # Related Notes section
    new_body_parts.append('### Related Notes')
    if related_notes:
        for note in related_notes[:10]:  # Limit to 10
            new_body_parts.append(f'- {note}')
    else:
        new_body_parts.append('-')
    new_body_parts.append('')
    
    # Questions section
    new_body_parts.append('### Questions / Ideas for Further Exploration')
    if questions:
        for q in questions[:5]:  # Limit to 5
            new_body_parts.append(f'- {q}')
    else:
        new_body_parts.append('-')
    new_body_parts.append('')
    
    # To-Do section
    new_body_parts.append('### To-Do')
    if todos:
        for todo in todos[:10]:  # Limit to 10
            new_body_parts.append(f'- [ ] {todo}')
    else:
        new_body_parts.append('-')
    new_body_parts.append('')
    
    # Smart Connections Insights section
    new_body_parts.append('### Smart Connections Insights')
    new_body_parts.append('-')
    new_body_parts.append('')
    
    # Combine
    new_body = '\n'.join(new_body_parts)
    
    # Build new content
    frontmatter_yaml = yaml.dump(new_frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    new_content = f"---\n{frontmatter_yaml}---\n{new_body}\n"
    
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
            'backup': str(backup_path.relative_to(vault_root))
        }
    else:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'would_update',
            'preview': new_content[:500] + '...' if len(new_content) > 500 else new_content
        }


def apply_new_note_templates(
    regular_notes_list_path: str,
    vault_path: str,
    template_path: str,
    dry_run: bool = True
) -> Dict:
    """Apply New Note template to all regular notes."""
    vault_root = Path(vault_path)
    template_file = Path(template_path)
    
    if not template_file.exists():
        raise ValueError(f"Template file not found: {template_path}")
    
    # Load regular notes list
    with open(regular_notes_list_path, 'r', encoding='utf-8') as f:
        regular_notes = json.load(f)
    
    print(f"Applying New Note template to {len(regular_notes)} files")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print()
    
    results = []
    for i, note_info in enumerate(regular_notes, 1):
        file_path = vault_root / note_info['file']
        if not file_path.exists():
            print(f"  [{i}/{len(regular_notes)}] File not found: {note_info['file']}")
            continue
        
        if i % 50 == 0:
            print(f"  [{i}/{len(regular_notes)}] Processing: {note_info['file']}")
        
        result = apply_new_note_template(file_path, vault_root, template_file, dry_run)
        results.append(result)
    
    # Summary
    updated = sum(1 for r in results if r.get('status') == 'updated')
    would_update = sum(1 for r in results if r.get('status') == 'would_update')
    errors = sum(1 for r in results if r.get('status') == 'error')
    
    print("\n" + "="*70)
    print("NEW NOTE TEMPLATE APPLICATION SUMMARY")
    print("="*70)
    if dry_run:
        print(f"Would update: {would_update}")
    else:
        print(f"Updated: {updated}")
    print(f"Errors: {errors}")
    print("="*70)
    
    return {
        'dry_run': dry_run,
        'total': len(results),
        'updated': updated if not dry_run else 0,
        'would_update': would_update if dry_run else 0,
        'errors': errors,
        'results': results
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Apply New Note template to regular notes')
    parser.add_argument(
        '--regular-notes-list',
        type=str,
        default='regular_notes_list.json',
        help='Path to regular notes list JSON file'
    )
    parser.add_argument(
        '--vault-path',
        type=str,
        default=os.getenv('OBSIDIAN_VAULT_PATH', '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel'),
        help='Path to Obsidian vault'
    )
    parser.add_argument(
        '--template',
        type=str,
        default='/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel/Templates/New Note Template.md',
        help='Path to New Note template file'
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
        results = apply_new_note_templates(
            args.regular_notes_list,
            args.vault_path,
            args.template,
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

