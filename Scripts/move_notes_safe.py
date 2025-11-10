#!/usr/bin/env python3
"""
Move Notes Safe - Move notes to suggested folders while updating all internal links.

When moving notes:
- Update all internal links ([[Note Name]]) in moved file
- Update all references to moved file in other notes
- Preserve relative links
- Update absolute paths if needed
- Create link mapping: link_updates.json
- Dry-run mode with link impact report
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set
import shutil


def find_all_markdown_files(vault_root: Path) -> List[Path]:
    """Find all markdown files in vault."""
    return list(vault_root.rglob("*.md"))


def extract_internal_links(content: str) -> List[str]:
    """Extract all internal links from content."""
    pattern = r'\[\[([^\]]+)\]\]'
    return re.findall(pattern, content)


def update_links_in_file(file_path: Path, link_mapping: Dict[str, str], dry_run: bool = True) -> int:
    """Update links in a file based on link mapping. Returns number of updates."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception:
        return 0
    
    updates = 0
    new_content = content
    
    # Update each link in the mapping
    for old_link, new_link in link_mapping.items():
        # Pattern to match [[old_link]] or [[old_link|display]]
        pattern = rf'\[\[{re.escape(old_link)}(\|[^\]]+)?\]\]'
        matches = re.findall(pattern, new_content)
        if matches:
            for match in matches:
                display_text = match if match else ''
                replacement = f"[[{new_link}{display_text}]]"
                new_content = re.sub(
                    rf'\[\[{re.escape(old_link)}{re.escape(display_text)}\]\]',
                    replacement,
                    new_content
                )
                updates += 1
    
    # Write updated content if not dry run
    if updates > 0 and not dry_run:
        file_path.write_text(new_content, encoding='utf-8')
    
    return updates


def create_link_mapping(moved_files: Dict[Path, Path], vault_root: Path) -> Dict[str, str]:
    """
    Create mapping of old link names to new link names based on file moves.
    
    Returns dict mapping: old_link_name -> new_link_name
    """
    link_mapping = {}
    
    for old_path, new_path in moved_files.items():
        # Get note name (filename without extension)
        old_name = old_path.stem
        new_name = new_path.stem
        
        # If name changed, add to mapping
        if old_name != new_name:
            link_mapping[old_name] = new_name
        
        # Also handle relative paths in links
        old_relative = str(old_path.relative_to(vault_root).with_suffix(''))
        new_relative = str(new_path.relative_to(vault_root).with_suffix(''))
        
        if old_relative != new_relative:
            # Convert to link format (replace / with /, handle spaces)
            old_link = old_relative.replace('/', '/')
            new_link = new_relative.replace('/', '/')
            link_mapping[old_link] = new_link
    
    return link_mapping


def move_note_with_link_preservation(
    source_path: Path,
    target_path: Path,
    vault_root: Path,
    all_files: List[Path],
    dry_run: bool = True
) -> Dict:
    """Move a note and update all references to it."""
    if not source_path.exists():
        return {
            'file': str(source_path.relative_to(vault_root)),
            'status': 'error',
            'error': 'Source file does not exist'
        }
    
    # Create target directory
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read source content to extract links
    try:
        source_content = source_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'file': str(source_path.relative_to(vault_root)),
            'status': 'error',
            'error': f'Failed to read source: {e}'
        }
    
    # Extract internal links from source
    source_links = extract_internal_links(source_content)
    
    # Move file
    if not dry_run:
        try:
            shutil.move(str(source_path), str(target_path))
        except Exception as e:
            return {
                'file': str(source_path.relative_to(vault_root)),
                'status': 'error',
                'error': f'Failed to move file: {e}'
            }
    
    # Create link mapping for this move
    link_mapping = create_link_mapping({source_path: target_path}, vault_root)
    
    # Update links in moved file
    moved_file_updates = 0
    if not dry_run:
        moved_file_updates = update_links_in_file(target_path, link_mapping, dry_run=False)
    else:
        # In dry run, just count what would be updated
        moved_file_updates = len([l for l in source_links if l in link_mapping])
    
    # Update references in other files
    other_file_updates = 0
    old_name = source_path.stem
    new_name = target_path.stem
    
    for other_file in all_files:
        if other_file == source_path:
            continue
        
        try:
            other_content = other_file.read_text(encoding='utf-8')
        except Exception:
            continue
        
        # Check if this file references the moved file
        if old_name in other_content or str(source_path.relative_to(vault_root)) in other_content:
            updates = update_links_in_file(other_file, link_mapping, dry_run=dry_run)
            other_file_updates += updates
    
    return {
        'file': str(source_path.relative_to(vault_root)),
        'target': str(target_path.relative_to(vault_root)),
        'status': 'moved' if not dry_run else 'would_move',
        'moved_file_link_updates': moved_file_updates,
        'other_files_link_updates': other_file_updates,
        'total_link_updates': moved_file_updates + other_file_updates
    }


def move_notes_from_suggestions(
    folder_suggestions_path: str,
    vault_path: str,
    dry_run: bool = True
) -> Dict:
    """Move notes based on folder suggestions."""
    vault_root = Path(vault_path)
    
    # Load folder suggestions
    with open(folder_suggestions_path, 'r', encoding='utf-8') as f:
        suggestions = json.load(f)
    
    # Filter to only notes that need moving
    moves_needed = [s for s in suggestions if s.get('folder_change_needed', False)]
    
    print(f"Moving {len(moves_needed)} notes")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print()
    
    # Get all markdown files for link updates
    all_files = find_all_markdown_files(vault_root)
    
    results = []
    link_updates_log = []
    
    for i, suggestion in enumerate(moves_needed, 1):
        if i % 10 == 0:
            print(f"  Processed {i}/{len(moves_needed)} moves...")
        
        source_path = vault_root / suggestion['file']
        target_folder = vault_root / suggestion['suggested_folder']
        target_path = target_folder / source_path.name
        
        if not source_path.exists():
            print(f"  [{i}/{len(moves_needed)}] Source not found: {suggestion['file']}")
            continue
        
        result = move_note_with_link_preservation(
            source_path,
            target_path,
            vault_root,
            all_files,
            dry_run=dry_run
        )
        results.append(result)
        
        if result.get('total_link_updates', 0) > 0:
            link_updates_log.append({
                'file': result['file'],
                'target': result.get('target', ''),
                'link_updates': result['total_link_updates']
            })
    
    # Save link updates log
    if link_updates_log:
        log_path = Path('link_updates.json')
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(link_updates_log, f, indent=2, ensure_ascii=False)
        print(f"\nLink updates log saved to: {log_path}")
    
    # Summary
    moved = sum(1 for r in results if r.get('status') == 'moved')
    would_move = sum(1 for r in results if r.get('status') == 'would_move')
    errors = sum(1 for r in results if r.get('status') == 'error')
    total_link_updates = sum(r.get('total_link_updates', 0) for r in results)
    
    print("\n" + "="*70)
    print("MOVE NOTES SUMMARY")
    print("="*70)
    if dry_run:
        print(f"Would move: {would_move}")
    else:
        print(f"Moved: {moved}")
    print(f"Errors: {errors}")
    print(f"Total link updates: {total_link_updates}")
    print("="*70)
    
    return {
        'dry_run': dry_run,
        'total': len(results),
        'moved': moved if not dry_run else 0,
        'would_move': would_move if dry_run else 0,
        'errors': errors,
        'total_link_updates': total_link_updates,
        'results': results
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Move notes to suggested folders with link preservation')
    parser.add_argument(
        '--folder-suggestions',
        type=str,
        default='folder_suggestions.json',
        help='Path to folder suggestions JSON file'
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
        help='Execute moves (default is dry-run)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output path for results JSON'
    )
    
    args = parser.parse_args()
    
    try:
        results = move_notes_from_suggestions(
            args.folder_suggestions,
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

