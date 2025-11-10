#!/usr/bin/env python3
"""
Analyze Data Loss - More sophisticated analysis to distinguish between expected changes and real data loss.
"""

import json
import re
from pathlib import Path
import difflib


def is_expected_removal(line: str) -> bool:
    """Check if a removed line is an expected change (tag, link, empty backlink, etc.)."""
    line = line.strip()
    
    # Empty lines
    if not line:
        return True
    
    # Just a link
    if re.match(r'^-\s*\[\[.*\]\]\s*$', line):
        return True
    
    # Just a tag (single word, lowercase, common tags)
    if re.match(r'^-\s*(ai|meeting|question|reference|idea|main|tech|obsidian|moc)\s*$', line, re.IGNORECASE):
        return True
    
    # Empty backlink
    if 'backlink' in line.lower() and ('[[]]' in line or "''" in line or '""' in line):
        return True
    
    # Date field with link
    if re.match(r'^date:\s*\[\[.*\]\]', line, re.IGNORECASE):
        return True
    
    return False


def analyze_file(backup_path: Path, current_path: Path) -> dict:
    """Analyze a file for real data loss."""
    if not backup_path.exists() or not current_path.exists():
        return None
    
    backup_content = backup_path.read_text(encoding='utf-8')
    current_content = current_path.read_text(encoding='utf-8')
    
    backup_lines = backup_content.split('\n')
    current_lines = current_content.split('\n')
    
    diff = list(difflib.unified_diff(backup_lines, current_lines, lineterm='', n=0))
    
    # Separate expected vs unexpected removals
    expected_removals = []
    unexpected_removals = []
    
    for line in diff:
        if line.startswith('-') and not line.startswith('---'):
            line_content = line[1:]  # Remove '-' prefix
            if is_expected_removal(line_content):
                expected_removals.append(line_content.strip())
            else:
                # Check if it's substantial content (more than just formatting)
                stripped = line_content.strip()
                if len(stripped) > 15:  # Substantial content
                    unexpected_removals.append(stripped)
    
    return {
        'file': str(current_path),
        'expected_removals': len(expected_removals),
        'unexpected_removals': len(unexpected_removals),
        'unexpected_samples': unexpected_removals[:5]  # First 5 samples
    }


def main():
    """Main analysis."""
    import os
    vault_root = Path(os.getenv('OBSIDIAN_VAULT_PATH', '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel'))
    
    # Load verification results
    with open('data_loss_verification.json', 'r') as f:
        verification = json.load(f)
    
    print("Analyzing files for REAL data loss (excluding expected changes)...")
    print("="*70)
    
    real_data_loss = []
    
    for issue in verification.get('issues', [])[:100]:  # Check first 100
        file_path = Path(issue['file'])
        backup_path = file_path.parent / (file_path.name + '.backup')
        
        analysis = analyze_file(backup_path, file_path)
        if analysis and analysis['unexpected_removals'] > 0:
            real_data_loss.append(analysis)
    
    print(f"\nFiles with potential REAL data loss: {len(real_data_loss)}")
    print("="*70)
    
    if real_data_loss:
        print("\n⚠️  Files with unexpected content removals:")
        for item in real_data_loss[:20]:  # Show first 20
            print(f"\n{item['file']}:")
            print(f"  Expected removals (tags/links): {item['expected_removals']}")
            print(f"  Unexpected removals: {item['unexpected_removals']}")
            if item['unexpected_samples']:
                print("  Sample unexpected removals:")
                for sample in item['unexpected_samples']:
                    print(f"    - {sample[:100]}")
    else:
        print("\n✅ No real data loss detected!")
        print("All changes appear to be expected (tag removal, broken link removal, etc.)")
    
    # Save results
    with open('real_data_loss_analysis.json', 'w') as f:
        json.dump(real_data_loss, f, indent=2, ensure_ascii=False)
    
    print(f"\nDetailed analysis saved to: real_data_loss_analysis.json")


if __name__ == '__main__':
    main()

