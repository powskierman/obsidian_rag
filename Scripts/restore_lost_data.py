#!/usr/bin/env python3
"""
Restore Lost Data - Restore files that lost actual content (not just tags/links).
"""

import json
from pathlib import Path
import shutil


def restore_file(file_path: Path, dry_run: bool = True) -> dict:
    """Restore a file from its backup."""
    backup_path = file_path.parent / (file_path.name + '.backup')
    
    if not backup_path.exists():
        return {
            'file': str(file_path),
            'status': 'no_backup',
            'message': 'No backup file found'
        }
    
    if not file_path.exists():
        return {
            'file': str(file_path),
            'status': 'missing',
            'message': 'Current file does not exist'
        }
    
    try:
        if not dry_run:
            # Create a safety backup of current file
            safety_backup = file_path.parent / (file_path.name + '.before_restore')
            shutil.copy2(file_path, safety_backup)
            
            # Restore from backup
            shutil.copy2(backup_path, file_path)
            
            return {
                'file': str(file_path),
                'status': 'restored',
                'safety_backup': str(safety_backup)
            }
        else:
            return {
                'file': str(file_path),
                'status': 'would_restore'
            }
    except Exception as e:
        return {
            'file': str(file_path),
            'status': 'error',
            'error': str(e)
        }


def main():
    """Main restoration process."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Restore files with data loss')
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Execute restoration (default is dry-run)'
    )
    parser.add_argument(
        '--analysis-file',
        type=str,
        default='real_data_loss_analysis.json',
        help='Path to data loss analysis JSON file'
    )
    
    args = parser.parse_args()
    
    # Load analysis
    with open(args.analysis_file, 'r') as f:
        files_with_loss = json.load(f)
    
    print(f"Restoring {len(files_with_loss)} files with data loss")
    print(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    print("="*70)
    
    results = []
    for item in files_with_loss:
        file_path = Path(item['file'])
        result = restore_file(file_path, dry_run=not args.execute)
        results.append(result)
        
        if result['status'] in ['restored', 'would_restore']:
            print(f"✅ {file_path.name}")
        elif result['status'] == 'no_backup':
            print(f"⚠️  {file_path.name} - No backup found")
        else:
            print(f"❌ {file_path.name} - {result.get('message', result.get('error', 'Unknown error'))}")
    
    restored = sum(1 for r in results if r['status'] == 'restored')
    would_restore = sum(1 for r in results if r['status'] == 'would_restore')
    
    print("\n" + "="*70)
    print("RESTORATION SUMMARY")
    print("="*70)
    if args.execute:
        print(f"Restored: {restored}")
    else:
        print(f"Would restore: {would_restore}")
    print("="*70)
    
    # Save results
    output_file = Path('restoration_results.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {output_file}")
    
    if args.execute and restored > 0:
        print("\n✅ Files restored from backup!")
        print("⚠️  Note: Current versions saved as .before_restore files")
        print("   Review restored files and merge any needed changes manually")


if __name__ == '__main__':
    main()

