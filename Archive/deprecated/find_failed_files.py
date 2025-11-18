#!/usr/bin/env python3
"""
Quick utility to find files that might have failed indexing
"""
import os
from pathlib import Path

def check_file_indexable(filepath):
    """Check if a file has indexable content"""
    filepath = Path(filepath)
    
    # Check if file exists and is readable
    if not filepath.exists():
        return False, "File doesn't exist"
    
    # Check size
    try:
        size = filepath.stat().st_size
        if size == 0:
            return False, "Empty file"
    except:
        return False, "Can't read file stats"
    
    # Try to read content
    content = None
    for encoding in ['utf-8', 'utf-8-sig', 'latin1']:
        try:
            with open(filepath, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue
    
    if content is None:
        return False, "Can't decode file"
    
    if not content or not content.strip():
        return False, "Empty content"
    
    # Check if has frontmatter only
    if content.startswith('---'):
        try:
            end = content.find('---', 3)
            if end != -1:
                body = content[end+3:].strip()
                if len(body) < 50:
                    return False, f"Only frontmatter (body: {len(body)} chars)"
        except:
            pass
    
    if len(content.strip()) < 50:
        return False, f"Content too short ({len(content.strip())} chars)"
    
    return True, "OK"

if __name__ == "__main__":
    import sys
    
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
    if not vault_path and len(sys.argv) > 1:
        vault_path = sys.argv[1]
    
    # Try default path if not provided
    if not vault_path:
        default_path = "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
        if Path(default_path).exists():
            vault_path = default_path
            print(f"Using default vault path: {vault_path}")
        else:
            print("Usage: python find_failed_files.py <vault_path>")
            print("Or set OBSIDIAN_VAULT_PATH environment variable")
            sys.exit(1)
    
    if not Path(vault_path).exists():
        print(f"❌ Vault path does not exist: {vault_path}")
        sys.exit(1)
    
    vault = Path(vault_path)
    md_files = list(vault.rglob("*.md"))
    
    print(f"🔍 Checking {len(md_files)} markdown files...")
    print()
    
    failed = []
    for filepath in md_files:
        # Skip hidden/template files
        parts = filepath.parts
        if any(part.startswith('.') or part.startswith('_') for part in parts):
            continue
        if any(skip in str(filepath) for skip in ['.obsidian', '.trash', 'Templates', 'Excalidraw']):
            continue
        
        is_ok, reason = check_file_indexable(filepath)
        if not is_ok:
            rel_path = str(filepath.relative_to(vault))
            failed.append((rel_path, reason))
    
    if failed:
        print(f"⚠️  Found {len(failed)} files that might not be indexable:")
        print()
        for filepath, reason in failed[:25]:  # Show first 25
            print(f"  • {filepath}")
            print(f"    Reason: {reason}")
        if len(failed) > 25:
            print(f"\n  ... and {len(failed) - 25} more")
    else:
        print("✅ All files appear indexable!")
