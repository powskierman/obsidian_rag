#!/usr/bin/env python3
"""
Obsidian Vault Scanner with File Watching
Monitors vault for changes and auto-indexes new/modified files
"""

import os
from pathlib import Path
import requests
from datetime import datetime
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import re

VAULT_PATH = "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
EMBEDDING_URL = "http://localhost:8000"

def should_process(filepath):
    """Check if file should be processed"""
    filepath = Path(filepath)
    parts = filepath.parts
    
    # Skip hidden files and templates
    if any(part.startswith('.') or part.startswith('_') for part in parts):
        return False
    
    # Only process markdown files
    if filepath.suffix != '.md':
        return False
    
    return True

def extract_metadata(content):
    """Extract YAML frontmatter and clean content"""
    metadata = {}
    
    if content.startswith('---'):
        try:
            end = content.find('---', 3)
            if end != -1:
                frontmatter = content[3:end]
                for line in frontmatter.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip()] = value.strip()
                content = content[end+3:].strip()
        except:
            pass
    
    return metadata, content

def smart_chunk_document(content, max_size=1000, overlap=200):
    """Chunk document by semantic boundaries (headers, paragraphs)"""
    chunks = []
    
    # Split by headers first (## or ###)
    sections = re.split(r'\n(?=#{2,3} )', content)
    
    for section in sections:
        if len(section) <= max_size:
            if section.strip():
                chunks.append(section.strip())
        else:
            # Split long sections by paragraphs
            paragraphs = section.split('\n\n')
            current_chunk = ""
            
            for para in paragraphs:
                if len(current_chunk) + len(para) <= max_size:
                    current_chunk += para + "\n\n"
                else:
                    if current_chunk.strip():
                        chunks.append(current_chunk.strip())
                    current_chunk = para + "\n\n"
            
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
    
    return chunks if chunks else [content[:max_size]]

def process_file(filepath):
    """Process a single file and add to index"""
    try:
        filepath = Path(filepath)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        metadata, content = extract_metadata(content)
        
        rel_path = str(filepath.relative_to(VAULT_PATH))
        
        metadata.update({
            'filepath': rel_path,
            'filename': filepath.name,
            'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat(),
            'source': 'obsidian'
        })
        
        chunks = smart_chunk_document(content)
        
        if not chunks:
            return 0
        
        print(f"📝 Processing: {rel_path} ({len(chunks)} chunks)")
        
        success_count = 0
        for i, chunk in enumerate(chunks):
            doc_id = f"{rel_path}_chunk_{i}"
            
            try:
                response = requests.post(
                    f"{EMBEDDING_URL}/add",
                    json={
                        'id': doc_id,
                        'text': chunk,
                        'metadata': {
                            **metadata,
                            'chunk_id': i,
                            'total_chunks': len(chunks)
                        }
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    success_count += 1
                else:
                    print(f"  ❌ Error chunk {i}: {response.status_code}")
            
            except Exception as e:
                print(f"  ❌ Error chunk {i}: {e}")
        
        return success_count
    
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        return 0

class VaultHandler(FileSystemEventHandler):
    """Handle file system events"""
    
    def __init__(self):
        self.last_modified = {}
        self.cooldown = 2  # seconds between processing same file
    
    def on_modified(self, event):
        """Handle file modification"""
        if event.is_directory:
            return
        
        filepath = Path(event.src_path)
        if not should_process(filepath):
            return
        
        # Debounce - avoid processing same file multiple times rapidly
        now = time.time()
        if filepath in self.last_modified:
            if now - self.last_modified[filepath] < self.cooldown:
                return
        
        self.last_modified[filepath] = now
        print(f"\n🔄 File changed: {filepath.name}")
        process_file(filepath)
    
    def on_created(self, event):
        """Handle new file creation"""
        if event.is_directory:
            return
        
        filepath = Path(event.src_path)
        if not should_process(filepath):
            return
        
        print(f"\n✨ New file: {filepath.name}")
        time.sleep(0.5)  # Wait for file to be fully written
        process_file(filepath)

def initial_scan():
    """Perform initial vault scan"""
    print("🚀 Obsidian Vault Scanner with File Watching")
    print("=" * 60)
    
    # Check embedding service
    try:
        requests.get(f'{EMBEDDING_URL}/health', timeout=5)
        print("✅ Embedding service is running\n")
    except:
        print("❌ Embedding service not running!")
        print("   Start it: python embedding_service.py")
        return False
    
    vault_path = Path(VAULT_PATH)
    print(f"Vault: {vault_path}\n")
    
    markdown_files = list(vault_path.rglob("*.md"))
    print(f"Found {len(markdown_files)} markdown files")
    
    # Scan options
    print("\nOptions:")
    print("  1. Quick scan (skip, start watching only)")
    print("  2. Full re-index (all files)")
    print("  3. Smart scan (only new/modified files)")
    
    choice = input("\nChoice (1/2/3): ").strip()
    
    if choice == "2":
        print("\n🔄 Starting full re-index...\n")
        processed = 0
        skipped = 0
        total_chunks = 0
        
        for i, filepath in enumerate(markdown_files, 1):
            if should_process(filepath):
                chunks = process_file(filepath)
                if chunks > 0:
                    processed += 1
                    total_chunks += chunks
                else:
                    skipped += 1
            else:
                skipped += 1
            
            if i % 50 == 0:
                print(f"\n--- Progress: {i}/{len(markdown_files)} files ---")
                stats = requests.get(f'{EMBEDDING_URL}/stats').json()
                print(f"    Documents in DB: {stats['total_documents']}\n")
        
        print("\n" + "=" * 60)
        print("✅ Full scan complete!")
        print(f"   Processed: {processed} files")
        print(f"   Skipped: {skipped} files")
        print(f"   Total chunks: {total_chunks}")
        stats = requests.get(f'{EMBEDDING_URL}/stats').json()
        print(f"   Documents in DB: {stats['total_documents']}")
        print("=" * 60 + "\n")
    
    elif choice == "3":
        print("\n🔄 Smart scan for changes...\n")
        # Get current DB state
        stats = requests.get(f'{EMBEDDING_URL}/stats').json()
        print(f"Current DB: {stats['total_documents']} documents")
        print("Scanning for new/modified files...")
        
        # Simple approach: check modification time
        # In production, would compare with stored hashes
        processed = 0
        for filepath in markdown_files:
            if should_process(filepath):
                # Check if recently modified (last 7 days)
                mtime = os.path.getmtime(filepath)
                if time.time() - mtime < 7 * 24 * 3600:
                    chunks = process_file(filepath)
                    if chunks > 0:
                        processed += 1
        
        print(f"\n✅ Processed {processed} recent files\n")
    
    return True

def watch_vault():
    """Start file watcher"""
    print("👁️  Starting file watcher...")
    print("    Monitoring for changes in your vault")
    print("    Press Ctrl+C to stop\n")
    
    event_handler = VaultHandler()
    observer = Observer()
    observer.schedule(event_handler, VAULT_PATH, recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping file watcher...")
        observer.stop()
    
    observer.join()
    print("✅ File watcher stopped")

def main():
    if initial_scan():
        watch_vault()

if __name__ == "__main__":
    main()
