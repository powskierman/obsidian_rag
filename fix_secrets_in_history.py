#!/usr/bin/env python3
"""
Fix API keys in git history by replacing them with placeholders
"""
import subprocess
import re
import tempfile
import os

def fix_file_in_commit(commit_hash, filepath):
    """Replace API keys in a file from a specific commit"""
    try:
        # Get file content from commit
        result = subprocess.run(
            ['git', 'show', f'{commit_hash}:{filepath}'],
            capture_output=True, text=True, check=True
        )
        content = result.stdout
        
        # Replace API keys
        content = re.sub(
            r'sk-ant-api03-[A-Za-z0-9_-]+',
            'your-api-key-here',
            content
        )
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.tmp') as f:
            f.write(content)
            temp_path = f.name
        
        return temp_path, content
    except subprocess.CalledProcessError:
        return None, None

if __name__ == '__main__':
    commit_hash = '32c1ad3'
    files = ['.env.claude', 'Documentation/QUICK_FIX_CLAUDE_USING_OLD_SERVER.md']
    
    for filepath in files:
        temp_path, content = fix_file_in_commit(commit_hash, filepath)
        if temp_path:
            print(f"Fixed {filepath}")
            print(f"Content preview: {content[:200]}...")
        else:
            print(f"File {filepath} not found in commit")

