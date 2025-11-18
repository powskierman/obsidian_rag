#!/usr/bin/env python3
"""
Backup Vault - Create timestamped backup of entire vault before making changes.

Before execution:
- Create timestamped backup: vault_backup_YYYYMMDD_HHMMSS/
- Include all markdown files
- Preserve folder structure
- Create backup manifest
"""

import json
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List


def create_backup(vault_path: str, backup_dir: str = '.') -> Dict:
    """Create a timestamped backup of the vault."""
    vault_root = Path(vault_path)
    if not vault_root.exists():
        raise ValueError(f"Vault path does not exist: {vault_path}")
    
    # Create backup directory name with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"vault_backup_{timestamp}"
    backup_path = Path(backup_dir) / backup_name
    
    print(f"Creating backup: {backup_path}")
    print(f"Source: {vault_path}")
    print()
    
    # Create backup directory
    backup_path.mkdir(parents=True, exist_ok=True)
    
    # Find all markdown files
    md_files = list(vault_root.rglob("*.md"))
    print(f"Found {len(md_files)} markdown files")
    
    # Copy files
    copied_files = []
    failed_files = []
    
    for i, source_file in enumerate(md_files, 1):
        if i % 100 == 0:
            print(f"  Copied {i}/{len(md_files)} files...")
        
        # Calculate relative path
        relative_path = source_file.relative_to(vault_root)
        target_file = backup_path / relative_path
        
        # Create target directory
        target_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.copy2(source_file, target_file)
            copied_files.append(str(relative_path))
        except Exception as e:
            failed_files.append({
                'file': str(relative_path),
                'error': str(e)
            })
    
    # Create manifest
    manifest = {
        'backup_date': datetime.now().isoformat(),
        'source_vault': str(vault_path),
        'backup_path': str(backup_path),
        'total_files': len(md_files),
        'copied_files': len(copied_files),
        'failed_files': len(failed_files),
        'files': copied_files,
        'failures': failed_files
    }
    
    manifest_path = backup_path / 'backup_manifest.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print("\n" + "="*70)
    print("BACKUP SUMMARY")
    print("="*70)
    print(f"Backup location: {backup_path}")
    print(f"Total files: {len(md_files)}")
    print(f"Copied: {len(copied_files)}")
    print(f"Failed: {len(failed_files)}")
    print(f"Manifest: {manifest_path}")
    print("="*70)
    
    if failed_files:
        print("\n⚠️  Some files failed to copy:")
        for failure in failed_files[:10]:
            print(f"  - {failure['file']}: {failure['error']}")
        if len(failed_files) > 10:
            print(f"  ... and {len(failed_files) - 10} more")
    
    return {
        'backup_path': str(backup_path),
        'manifest_path': str(manifest_path),
        'total_files': len(md_files),
        'copied_files': len(copied_files),
        'failed_files': len(failed_files),
        'manifest': manifest
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Create backup of Obsidian vault')
    parser.add_argument(
        '--vault-path',
        type=str,
        default=os.getenv('OBSIDIAN_VAULT_PATH', '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel'),
        help='Path to Obsidian vault'
    )
    parser.add_argument(
        '--backup-dir',
        type=str,
        default='.',
        help='Directory to store backup'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output path for backup info JSON'
    )
    
    args = parser.parse_args()
    
    try:
        result = create_backup(args.vault_path, args.backup_dir)
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\nBackup info saved to: {args.output}")
        
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

