#!/usr/bin/env python3
"""
Rollback Changes - Restore vault from backup and revert all changes if issues detected.

Restore from backup:
- Restore from backup
- Revert link updates
- Restore original file locations
"""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict


def load_backup_manifest(backup_path: str) -> Dict:
    """Load backup manifest."""
    backup_dir = Path(backup_path)
    manifest_path = backup_dir / 'backup_manifest.json'
    
    if not manifest_path.exists():
        raise ValueError(f"Backup manifest not found: {manifest_path}")
    
    with open(manifest_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def restore_from_backup(backup_path: str, vault_path: str, dry_run: bool = True) -> Dict:
    """Restore vault from backup."""
    backup_dir = Path(backup_path)
    vault_root = Path(vault_path)
    
    if not backup_dir.exists():
        raise ValueError(f"Backup directory does not exist: {backup_path}")
    
    if not vault_root.exists():
        raise ValueError(f"Vault path does not exist: {vault_path}")
    
    # Load manifest
    manifest = load_backup_manifest(backup_path)
    
    print(f"Restoring vault from backup")
    print(f"Backup: {backup_path}")
    print(f"Target: {vault_path}")
    print(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
    print()
    
    restored_files = []
    failed_files = []
    
    # Restore each file from manifest
    for i, file_path_str in enumerate(manifest.get('files', []), 1):
        if i % 100 == 0:
            print(f"  Restored {i}/{len(manifest['files'])} files...")
        
        backup_file = backup_dir / file_path_str
        target_file = vault_root / file_path_str
        
        if not backup_file.exists():
            failed_files.append({
                'file': file_path_str,
                'error': 'Backup file does not exist'
            })
            continue
        
        try:
            if not dry_run:
                # Create target directory
                target_file.parent.mkdir(parents=True, exist_ok=True)
                # Copy file
                shutil.copy2(backup_file, target_file)
            
            restored_files.append(file_path_str)
        except Exception as e:
            failed_files.append({
                'file': file_path_str,
                'error': str(e)
            })
    
    print("\n" + "="*70)
    print("ROLLBACK SUMMARY")
    print("="*70)
    if dry_run:
        print(f"Would restore: {len(restored_files)}")
    else:
        print(f"Restored: {len(restored_files)}")
    print(f"Failed: {len(failed_files)}")
    print("="*70)
    
    if failed_files:
        print("\n⚠️  Some files failed to restore:")
        for failure in failed_files[:10]:
            print(f"  - {failure['file']}: {failure['error']}")
        if len(failed_files) > 10:
            print(f"  ... and {len(failed_files) - 10} more")
    
    return {
        'dry_run': dry_run,
        'backup_path': backup_path,
        'vault_path': vault_path,
        'restored_files': len(restored_files),
        'failed_files': len(failed_files),
        'restored': restored_files,
        'failures': failed_files
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Rollback vault from backup')
    parser.add_argument(
        '--backup-path',
        type=str,
        required=True,
        help='Path to backup directory'
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
        help='Execute rollback (default is dry-run)'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='Output path for rollback results JSON'
    )
    
    args = parser.parse_args()
    
    try:
        results = restore_from_backup(
            args.backup_path,
            args.vault_path,
            dry_run=not args.execute
        )
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"\nRollback results saved to: {args.output}")
        
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

