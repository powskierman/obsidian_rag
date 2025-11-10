#!/usr/bin/env python3
"""
Verify No Data Loss - Compare backup files with current files to ensure no content was lost.

This script:
- Compares backup files with current files
- Identifies any content that was removed beyond broken links
- Reports potential data loss
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple
import difflib


def normalize_content(content: str) -> str:
    """Normalize content for comparison (remove whitespace differences)."""
    # Remove trailing whitespace from lines
    lines = [line.rstrip() for line in content.split('\n')]
    return '\n'.join(lines)


def extract_links_from_content(content: str) -> List[str]:
    """Extract all internal links [[Note Name]] from content."""
    link_pattern = r'\[\[([^\]]+)\]\]'
    matches = re.findall(link_pattern, content)
    links = []
    for match in matches:
        link_name = match.split('|')[0].strip()
        links.append(link_name)
    return links


def compare_files(backup_path: Path, current_path: Path) -> Dict:
    """Compare backup and current file to detect data loss."""
    if not backup_path.exists():
        return {
            'status': 'no_backup',
            'file': str(current_path),
            'message': 'No backup file found'
        }
    
    if not current_path.exists():
        return {
            'status': 'missing',
            'file': str(current_path),
            'message': 'Current file does not exist'
        }
    
    try:
        backup_content = backup_path.read_text(encoding='utf-8')
        current_content = current_path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            'status': 'error',
            'file': str(current_path),
            'error': str(e)
        }
    
    # Normalize for comparison
    backup_norm = normalize_content(backup_content)
    current_norm = normalize_content(current_content)
    
    # Extract links from both
    backup_links = extract_links_from_content(backup_content)
    current_links = extract_links_from_content(current_content)
    
    # Find removed links
    removed_links = set(backup_links) - set(current_links)
    
    # Check if files are identical (after normalization)
    if backup_norm == current_norm:
        return {
            'status': 'identical',
            'file': str(current_path),
            'removed_links': list(removed_links)
        }
    
    # Calculate content difference
    backup_lines = backup_norm.split('\n')
    current_lines = current_norm.split('\n')
    
    # Use difflib to find differences
    diff = list(difflib.unified_diff(
        backup_lines,
        current_lines,
        fromfile=str(backup_path),
        tofile=str(current_path),
        lineterm='',
        n=0  # No context lines
    ))
    
    # Count removed and added lines
    removed_lines = [line for line in diff if line.startswith('-') and not line.startswith('---')]
    added_lines = [line for line in diff if line.startswith('+') and not line.startswith('+++')]
    
    # Check for significant content loss (more than just link removal)
    # A removed line is significant if it's not just a link or empty
    significant_removals = []
    for line in removed_lines:
        line_content = line[1:].strip()  # Remove '-' prefix
        # Skip if it's just a link, empty, or whitespace
        if not line_content or line_content.startswith('[[') and line_content.endswith(']]'):
            continue
        # Skip if it's just a list item with a link
        if re.match(r'^-\s*\[\[.*\]\]\s*$', line_content):
            continue
        significant_removals.append(line_content)
    
    # Check if content was lost beyond link removal
    has_data_loss = len(significant_removals) > 0
    
    return {
        'status': 'different',
        'file': str(current_path),
        'removed_links': list(removed_links),
        'removed_lines_count': len(removed_lines),
        'added_lines_count': len(added_lines),
        'significant_removals': significant_removals[:10],  # First 10 significant removals
        'has_data_loss': has_data_loss,
        'backup_size': len(backup_content),
        'current_size': len(current_content),
        'size_diff': len(current_content) - len(backup_content)
    }


def find_backup_files(vault_root: Path) -> Dict[Path, Path]:
    """Find all backup files and map them to current files."""
    backup_map = {}
    
    for backup_file in vault_root.rglob("*.backup"):
        # Get corresponding current file (remove .backup extension)
        current_file = backup_file.parent / backup_file.stem
        
        # Only include .md files
        if current_file.suffix == '.md':
            backup_map[current_file] = backup_file
    
    return backup_map


def verify_all_notes(vault_path: str) -> Dict:
    """Verify all notes for data loss."""
    vault_root = Path(vault_path)
    
    print("Finding backup files...")
    backup_map = find_backup_files(vault_root)
    print(f"Found {len(backup_map)} backup files\n")
    
    if not backup_map:
        return {
            'status': 'no_backups',
            'message': 'No backup files found'
        }
    
    print("Comparing files...")
    results = []
    issues = []
    
    for i, (current_file, backup_file) in enumerate(backup_map.items(), 1):
        if i % 50 == 0:
            print(f"  Processed {i}/{len(backup_map)} files...")
        
        result = compare_files(backup_file, current_file)
        results.append(result)
        
        if result.get('has_data_loss'):
            issues.append(result)
    
    # Summary
    identical = sum(1 for r in results if r.get('status') == 'identical')
    different = sum(1 for r in results if r.get('status') == 'different')
    data_loss = sum(1 for r in results if r.get('has_data_loss', False))
    
    print("\n" + "="*70)
    print("DATA LOSS VERIFICATION SUMMARY")
    print("="*70)
    print(f"Total files compared: {len(results)}")
    print(f"Identical: {identical}")
    print(f"Different (expected - links removed): {different}")
    print(f"⚠️  Potential data loss: {data_loss}")
    print("="*70)
    
    if issues:
        print("\n⚠️  FILES WITH POTENTIAL DATA LOSS:")
        print("-"*70)
        for issue in issues[:20]:  # Show first 20
            print(f"\n{issue['file']}:")
            print(f"  Removed links: {len(issue.get('removed_links', []))}")
            print(f"  Size difference: {issue.get('size_diff', 0)} bytes")
            print(f"  Significant removals: {len(issue.get('significant_removals', []))}")
            if issue.get('significant_removals'):
                print("  Sample removed content:")
                for removal in issue['significant_removals'][:3]:
                    print(f"    - {removal[:80]}...")
    
    return {
        'total_files': len(results),
        'identical': identical,
        'different': different,
        'data_loss_count': data_loss,
        'issues': issues,
        'results': results
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify no data was lost during broken link removal')
    parser.add_argument(
        '--vault-path',
        type=str,
        default=os.getenv('OBSIDIAN_VAULT_PATH', '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel'),
        help='Path to Obsidian vault'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='data_loss_verification.json',
        help='Output path for verification results JSON'
    )
    
    args = parser.parse_args()
    
    try:
        results = verify_all_notes(args.vault_path)
        
        # Save results
        import json
        output_file = Path(args.output)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\nResults saved to: {args.output}")
        
        if results.get('data_loss_count', 0) > 0:
            print("\n⚠️  WARNING: Potential data loss detected!")
            print("Review the files listed above carefully.")
            return 1
        else:
            print("\n✅ No data loss detected - only broken links were removed.")
            return 0
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())

