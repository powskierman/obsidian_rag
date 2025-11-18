#!/usr/bin/env python3
"""
Review Tags - Review and clean up irrelevant tags from notes.

This script:
- Scans all notes for tags
- Identifies potentially irrelevant tags based on content type
- Allows manual review and removal of irrelevant tags
- Supports dry-run and execute modes
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set
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
        if frontmatter is None:
            frontmatter = {}
        elif not isinstance(frontmatter, dict):
            return None, content
        return frontmatter, body
    except yaml.YAMLError:
        return None, content


def detect_content_type(filename: str, content: str, file_path: str = '') -> str:
    """Detect the primary content type of the note."""
    filename_lower = filename.lower()
    content_lower = content.lower()[:500]
    path_lower = file_path.lower() if file_path else ''
    
    # Check file path first - if it's in Recipes folder, it's a recipe
    if '/recipes/' in path_lower or '\\recipes\\' in path_lower:
        return 'recipe'
    
    # Recipe/cooking indicators
    recipe_indicators = ['recipe', 'cook', 'ingredient', 'serving', 'prep time', 'cook time', 'oven', 'bake', 'fry', 'sauté', 'simmer', 'boil', 'cuisine', 'dish', 'meal', 'sauce', 'pasta', 'meat', 'vegetable']
    if any(indicator in filename_lower or indicator in content_lower for indicator in recipe_indicators):
        return 'recipe'
    
    # Medical/health indicators
    medical_indicators = ['treatment', 'diagnosis', 'symptom', 'patient', 'doctor', 'hospital', 'lymphoma', 'cancer', 'therapy', 'medication']
    if any(indicator in filename_lower or indicator in content_lower for indicator in medical_indicators):
        return 'medical'
    
    # Tech/programming indicators
    tech_indicators = ['code', 'programming', 'function', 'class', 'import', 'api', 'github', 'git', 'python', 'swift', 'javascript', 'software', 'development']
    if any(indicator in filename_lower or indicator in content_lower for indicator in tech_indicators):
        return 'tech'
    
    # Hardware/electronics indicators
    hardware_indicators = ['esp32', 'raspberry pi', 'arduino', 'circuit', 'electronics', 'sensor', 'microcontroller', 'gpio', 'pin']
    if any(indicator in filename_lower or indicator in content_lower for indicator in hardware_indicators):
        return 'hardware'
    
    # AI/ML indicators
    ai_indicators = ['machine learning', 'llm', 'gpt', 'claude', 'rag', 'embedding', 'vector', 'neural', 'model', 'training']
    if any(indicator in filename_lower or indicator in content_lower for indicator in ai_indicators):
        return 'ai'
    
    # Tutorial/guide indicators (check after other types to avoid false positives)
    tutorial_indicators = ['tutorial', 'guide', 'how to', 'step by step', 'instructions', 'walkthrough', 'getting started']
    if any(indicator in filename_lower or indicator in content_lower for indicator in tutorial_indicators):
        # Check if it's actually about AI/tech - if so, don't mark as tutorial
        if 'ai' not in content_lower[:200] and 'machine learning' not in content_lower[:200]:
            return 'tutorial'
    
    return 'general'


def identify_irrelevant_tags(content_type: str, tags: List[str], filename: str, content: str, is_reference: bool = False) -> List[str]:
    """Identify tags that are likely irrelevant based on content type."""
    irrelevant = []
    tags_lower = [t.lower() for t in tags]
    content_lower = content.lower()
    filename_lower = filename.lower()
    
    # Generic tags that are almost always irrelevant
    always_irrelevant = ['exploration', 'further', 'ideas', 'notes', 'related', 'questions']
    
    # Redundant tags (if ContentType already indicates this)
    if is_reference:
        # If ContentType is Reference, "reference" and "references" tags are redundant
        always_irrelevant.extend(['reference', 'references'])
    
    # Domain exclusions based on content type
    domain_exclusions = {
        'recipe': ['tech', 'ai', 'hardware', 'medical', 'meeting', 'question', 'reference', 'project', 'idea', 'main', 'home-automation', 'exploration', 'further', 'ideas', 'notes', 'related'],
        'medical': ['tech', 'ai', 'hardware', 'cooking', 'meeting', 'idea', 'main', 'home-automation', 'exploration', 'further', 'ideas', 'notes', 'related'],
        'tech': ['cooking', 'medical', 'recipe', 'idea', 'main', 'meeting', 'question', 'exploration', 'further', 'ideas', 'notes', 'related'],
        'hardware': ['cooking', 'medical', 'recipe', 'idea', 'main', 'meeting', 'question', 'ai', 'exploration', 'further', 'ideas', 'notes', 'related'],
        'ai': ['cooking', 'medical', 'recipe', 'hardware', 'idea', 'main', 'exploration', 'further', 'ideas', 'notes', 'related'],
        'tutorial': ['ai', 'meeting', 'question', 'reference', 'idea', 'main', 'home-automation', 'exploration', 'further', 'ideas', 'notes', 'related'],
        'reference': ['ai', 'meeting', 'question', 'idea', 'main', 'home-automation', 'exploration', 'further', 'ideas', 'notes', 'related', 'questions'],  # Reference docs shouldn't have exploratory tags
        'general': ['idea', 'main', 'ai', 'meeting', 'question', 'tech', 'home-automation', 'exploration', 'further', 'ideas', 'notes', 'related']  # Remove generic and domain tags from general content
    }
    
    excluded_tags = domain_exclusions.get(content_type, [])
    
    for tag in tags:
        tag_lower = tag.lower()
        
        # Check always irrelevant tags first
        if tag_lower in always_irrelevant:
            irrelevant.append(tag)
            continue
        
        # Check if tag is in exclusion list (most comprehensive check)
        if tag_lower in excluded_tags:
            irrelevant.append(tag)
            continue
        
        # Additional check for generic tags that don't match content
        generic_tags = {
            'idea': ['recipe', 'medical', 'tech', 'ai', 'hardware', 'general', 'tutorial'],  # "idea" is too generic everywhere
            'main': ['recipe', 'tech', 'ai', 'hardware', 'medical', 'general', 'tutorial'],  # "main" is too generic - remove from all
            'meeting': ['recipe', 'medical', 'tech', 'hardware', 'tutorial', 'general'],  # Very specific - remove from most
            'question': ['recipe', 'medical', 'tutorial', 'general'],  # Very specific - remove from most
            'reference': ['recipe', 'tutorial'],  # Recipes and tutorials aren't "reference" docs (they're guides/tutorials)
        }
        
        if tag_lower in generic_tags:
            if content_type in generic_tags[tag_lower]:
                irrelevant.append(tag)
                continue
        
        # Check if tag appears in content (if not, might be irrelevant)
        # But be lenient - if it's a domain tag and content type matches, keep it
        if tag_lower not in content_lower and tag_lower not in filename_lower:
            # Domain-specific tags that should be removed if not in content
            domain_tags = ['ai', 'tech', 'home-automation', 'hardware', 'cooking', 'medical']
            if tag_lower in domain_tags:
                # If content type is 'general' and tag doesn't appear in content, it's likely irrelevant
                if content_type == 'general':
                    irrelevant.append(tag)
                    continue
            
            # Only flag as irrelevant if it's a generic tag
            if tag_lower in ['idea', 'main', 'meeting', 'question', 'reference']:
                # Check if content actually mentions these concepts
                if 'idea' not in content_lower and 'main' not in content_lower:
                    if tag_lower in ['idea', 'main']:
                        irrelevant.append(tag)
    
    return irrelevant


def review_tags_for_note(file_path: Path, vault_root: Path, dry_run: bool = True) -> Dict:
    """Review tags for a single note."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'error',
            'error': str(e)
        }
    
    frontmatter, body = parse_frontmatter(content)
    filename = file_path.name
    
    if not frontmatter:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'no_frontmatter',
            'tags': []
        }
    
    # Get existing tags
    existing_tags = []
    tags_raw = frontmatter.get('tags', [])
    if isinstance(tags_raw, list):
        existing_tags = [str(t) for t in tags_raw]
    elif tags_raw:
        existing_tags = [str(tags_raw)]
    
    if not existing_tags:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'no_tags',
            'tags': []
        }
    
    # Check frontmatter for ContentType first
    content_type = None
    is_reference = False
    if frontmatter:
        content_type_from_fm = frontmatter.get('ContentType', '').lower()
        if content_type_from_fm:
            # Map ContentType values to our content types
            content_type_map = {
                'tutorial': 'tutorial',
                'moc': 'moc',
                'recipe': 'recipe',
                'reference': 'reference',
            }
            content_type = content_type_map.get(content_type_from_fm)
            if content_type_from_fm == 'reference':
                is_reference = True
    
    # If not found in frontmatter, detect from content
    if not content_type:
        file_relative = str(file_path.relative_to(vault_root))
        content_type = detect_content_type(filename, body, file_relative)
    
    # Identify irrelevant tags
    irrelevant_tags = identify_irrelevant_tags(content_type, existing_tags, filename, body, is_reference=is_reference)
    
    # Clean tags (remove irrelevant ones)
    cleaned_tags = [t for t in existing_tags if t not in irrelevant_tags]
    
    if not irrelevant_tags:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'no_change',
            'tags': existing_tags,
            'content_type': content_type
        }
    
    # Apply changes
    if not dry_run:
        new_frontmatter = frontmatter.copy()
        new_frontmatter['tags'] = cleaned_tags
        
        # Build new content
        frontmatter_yaml = yaml.dump(new_frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
        new_content = f"---\n{frontmatter_yaml}---\n{body}\n"
        
        # Create backup
        import shutil
        backup_path = file_path.with_suffix('.md.backup')
        shutil.copy2(file_path, backup_path)
        
        # Write new content
        file_path.write_text(new_content, encoding='utf-8')
        
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'updated',
            'tags': existing_tags,
            'cleaned_tags': cleaned_tags,
            'removed_tags': irrelevant_tags,
            'content_type': content_type,
            'backup': str(backup_path.relative_to(vault_root))
        }
    else:
        return {
            'file': str(file_path.relative_to(vault_root)),
            'status': 'would_update',
            'tags': existing_tags,
            'cleaned_tags': cleaned_tags,
            'removed_tags': irrelevant_tags,
            'content_type': content_type
        }


def review_all_tags(
    notes_list_path: str,
    vault_path: str,
    dry_run: bool = True,
    output_path: str = 'tag_review_results.json'
) -> Dict:
    """Review tags for all notes."""
    vault_root = Path(vault_path)
    
    # Load notes list
    with open(notes_list_path, 'r', encoding='utf-8') as f:
        notes_list = json.load(f)
    
    print(f"Reviewing tags for {len(notes_list)} notes")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print()
    
    results = []
    for i, note_info in enumerate(notes_list, 1):
        if i % 50 == 0:
            print(f"  Processed {i}/{len(notes_list)} notes...")
        
        file_path = vault_root / note_info['file']
        if not file_path.exists():
            continue
        
        result = review_tags_for_note(file_path, vault_root, dry_run)
        results.append(result)
    
    # Summary
    updated = sum(1 for r in results if r.get('status') == 'updated')
    would_update = sum(1 for r in results if r.get('status') == 'would_update')
    no_change = sum(1 for r in results if r.get('status') == 'no_change')
    total_removed = sum(len(r.get('removed_tags', [])) for r in results)
    
    print("\n" + "="*70)
    print("TAG REVIEW SUMMARY")
    print("="*70)
    if dry_run:
        print(f"Would update: {would_update}")
    else:
        print(f"Updated: {updated}")
    print(f"No change needed: {no_change}")
    print(f"Total tags to remove: {total_removed}")
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
        'total_tags_removed': total_removed,
        'results': results
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Review and clean up irrelevant tags')
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
        default='tag_review_results.json',
        help='Output path for results JSON'
    )
    
    args = parser.parse_args()
    
    try:
        review_all_tags(
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

