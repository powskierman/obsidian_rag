#!/usr/bin/env python3
"""
Obsidian Vault Scanner with File Watching
Monitors vault for changes and auto-indexes new/modified files
"""

import json
import hashlib
import os
from pathlib import Path
import requests
from datetime import datetime
import time
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import argparse

VAULT_PATH = "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
EMBEDDING_URL = "http://localhost:8000"
STATE_PATH = Path("./data/index_state.json")
ADMIN_TOKEN = os.getenv("EMBEDDING_CLEAR_TOKEN") or os.getenv("WATCHER_ADMIN_TOKEN")

def init_stats():
    return {
        "indexed_files": 0,
        "indexed_chunks": 0,
        "indexed_new": 0,
        "indexed_updated": 0,
        "skipped_unchanged": 0,
        "skipped_empty": 0,
        "skipped_missing": 0,
        "errors": 0,
        "error_files": [],
        "created_events": 0,
        "modified_events": 0,
        "deleted_events": 0,
        "deleted_from_index": 0,
        "deleted_from_vector": 0,
        "delete_errors": 0
    }

def load_index_state():
    """Load persisted index state to enable incremental indexing."""
    if not STATE_PATH.exists():
        return {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}

def save_index_state(state):
    """Persist index state safely to disk."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = STATE_PATH.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
    temp_path.replace(STATE_PATH)

def get_content_hash(content):
    """Hash content to detect changes."""
    return hashlib.md5(content.encode("utf-8")).hexdigest()

def record_error(stats, rel_path, message):
    if stats is None:
        return
    stats["errors"] += 1
    stats["error_files"].append({"file": rel_path, "error": message})

def delete_from_vector(rel_path, stats=None):
    if not ADMIN_TOKEN:
        print(f"Note: vector delete skipped (no admin token): {rel_path}")
        return False
    try:
        response = requests.post(
            f"{EMBEDDING_URL}/delete_by_filepath",
            json={"filepath": rel_path},
            headers={"X-Admin-Token": ADMIN_TOKEN},
            timeout=30
        )
        if response.status_code == 200:
            if stats is not None:
                stats["deleted_from_vector"] += 1
            return True
        record_error(stats, rel_path, f"delete_by_filepath: {response.status_code}")
        if stats is not None:
            stats["delete_errors"] += 1
    except Exception as e:
        record_error(stats, rel_path, f"delete_by_filepath: {e}")
        if stats is not None:
            stats["delete_errors"] += 1
    return False

def print_summary(stats, label):
    if stats is None:
        return
    print(f"\n{label}")
    print(f"   Indexed files: {stats['indexed_files']} (new: {stats['indexed_new']}, updated: {stats['indexed_updated']})")
    print(f"   Indexed chunks: {stats['indexed_chunks']}")
    print(f"   Skipped unchanged: {stats['skipped_unchanged']}")
    print(f"   Skipped empty: {stats['skipped_empty']}")
    print(f"   Skipped missing: {stats['skipped_missing']}")
    print(f"   Events - created: {stats['created_events']}, modified: {stats['modified_events']}, deleted: {stats['deleted_events']}")
    print(f"   Deleted from index: {stats['deleted_from_index']} | Deleted from vector: {stats['deleted_from_vector']}")
    print(f"   Errors: {stats['errors']} (delete errors: {stats['delete_errors']})")
    if stats["error_files"]:
        print("   Error files:")
        for entry in stats["error_files"]:
            print(f"   - {entry['file']}: {entry['error']}")

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

def process_file(filepath, index_state=None, force_reindex=False, stats=None):
    """Process a single file and add to index"""
    try:
        filepath = Path(filepath)
        if not filepath.exists():
            print(f"File missing, skipping: {filepath}")
            if stats is not None:
                stats["skipped_missing"] += 1
            return 0
        rel_path = str(filepath.relative_to(VAULT_PATH))
        stat = filepath.stat()
        signature = {
            "mtime": stat.st_mtime,
            "size": stat.st_size
        }
        existing = index_state.get(rel_path) if index_state is not None else None

        if index_state is not None and not force_reindex:
            if existing and existing.get("mtime") == signature["mtime"] and existing.get("size") == signature["size"]:
                print(f"Skipping unchanged: {rel_path}")
                if stats is not None:
                    stats["skipped_unchanged"] += 1
                return 0
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        metadata, content = extract_metadata(content)

        if not content.strip():
            print(f"Warning: skipping empty note: {rel_path}")
            if stats is not None:
                stats["skipped_empty"] += 1
            if index_state is not None:
                index_state[rel_path] = {**signature, "hash": get_content_hash(content)}
                save_index_state(index_state)
            return 0
        
        signature["hash"] = get_content_hash(content)
        if index_state is not None and not force_reindex and existing:
            if existing.get("hash") == signature["hash"]:
                if existing.get("mtime") != signature["mtime"] or existing.get("size") != signature["size"]:
                    index_state[rel_path] = signature
                    save_index_state(index_state)
                print(f"Skipping unchanged content: {rel_path}")
                if stats is not None:
                    stats["skipped_unchanged"] += 1
                return 0
        
        metadata.update({
            'filepath': rel_path,
            'filename': filepath.name,
            'modified': datetime.fromtimestamp(signature["mtime"]).isoformat(),
            'source': 'obsidian'
        })
        
        chunks = smart_chunk_document(content)
        
        if not chunks:
            return 0
        
        print(f"📝 Processing: {rel_path} ({len(chunks)} chunks)")
        
        success_count = 0
        chunk_errors = 0
        last_chunk_error = None
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            doc_id = f"{rel_path}_chunk_{i}"
            
            try:
                response = requests.post(
                    f"{EMBEDDING_URL}/upsert",
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
                    chunk_errors += 1
                    last_chunk_error = f"chunk {i}: {response.status_code}"
            
            except Exception as e:
                print(f"  ❌ Error chunk {i}: {e}")
                chunk_errors += 1
                last_chunk_error = f"chunk {i}: {e}"
        
        if index_state is not None and success_count == len(chunks):
            index_state[rel_path] = signature
            save_index_state(index_state)
        if stats is not None:
            if success_count > 0:
                stats["indexed_chunks"] += success_count
                stats["indexed_files"] += 1
                if existing is None:
                    stats["indexed_new"] += 1
                else:
                    stats["indexed_updated"] += 1
            if chunk_errors > 0:
                record_error(stats, rel_path, f"{chunk_errors} chunks failed (last: {last_chunk_error})")
        return success_count
    
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        record_error(stats, str(filepath), str(e))
        return 0

class VaultHandler(FileSystemEventHandler):
    """Handle file system events"""
    
    def __init__(self, stats=None):
        self.last_modified = {}
        self.cooldown = 2  # seconds between processing same file
        self.index_state = load_index_state()
        self.stats = stats or init_stats()
    
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
        self.stats["modified_events"] += 1
        print(f"\n🔄 File changed: {filepath.name}")
        process_file(filepath, self.index_state, stats=self.stats)
    
    def on_created(self, event):
        """Handle new file creation"""
        if event.is_directory:
            return
        
        filepath = Path(event.src_path)
        if not should_process(filepath):
            return
        
        print(f"\n✨ New file: {filepath.name}")
        self.last_modified[filepath] = time.time()
        self.stats["created_events"] += 1
        time.sleep(0.5)  # Wait for file to be fully written
        process_file(filepath, self.index_state, stats=self.stats)

    def on_deleted(self, event):
        """Handle file deletion"""
        if event.is_directory:
            return

        filepath = Path(event.src_path)
        if not should_process(filepath):
            return

        try:
            rel_path = str(filepath.relative_to(VAULT_PATH))
        except ValueError:
            return
        self.stats["deleted_events"] += 1
        print(f"\nFile deleted: {rel_path}")

        if rel_path in self.index_state:
            del self.index_state[rel_path]
            save_index_state(self.index_state)
            self.stats["deleted_from_index"] += 1

        delete_from_vector(rel_path, stats=self.stats)

def initial_scan(args=None, stats=None):
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
    
    choice = getattr(args, 'choice', None)
    
    if not choice:
        # Scan options
        print("\nOptions:")
        print("  1. Quick scan (skip, start watching only)")
        print("  2. Full re-index (all files)")
        print("  3. Smart scan (only new/modified files)")
        
        choice = input("\nChoice (1/2/3): ").strip()
    
    index_state = load_index_state()
    stats = stats or init_stats()

    if choice == "2":
        print("\n🔄 Starting full re-index...\n")
        processed = 0
        skipped = 0
        total_chunks = 0
        
        for i, filepath in enumerate(markdown_files, 1):
            if should_process(filepath):
                chunks = process_file(filepath, index_state, force_reindex=True, stats=stats)
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
        print("\n🔄 Smart scan for changes (incremental)...\n")
        # Get current DB state
        stats = requests.get(f'{EMBEDDING_URL}/stats').json()
        print(f"Current DB: {stats['total_documents']} documents")
        print("Scanning for new/modified files...")
        
        processed = 0
        for filepath in markdown_files:
            if should_process(filepath):
                chunks = process_file(filepath, index_state, stats=stats)
                if chunks > 0:
                    processed += 1
        
        print(f"\n✅ Processed {processed} changed files\n")
    print_summary(stats, "Initial scan")
    
    return True

def watch_vault(stats=None):
    """Start file watcher"""
    print("👁️  Starting file watcher...")
    print("    Monitoring for changes in your vault")
    print("    Press Ctrl+C to stop\n")
    
    event_handler = VaultHandler(stats)
    observer = Observer()
    observer.schedule(event_handler, VAULT_PATH, recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping file watcher...")
        print_summary(event_handler.stats, "Watcher summary")
        observer.stop()
    
    observer.join()
    print("✅ File watcher stopped")

def main():
    parser = argparse.ArgumentParser(description="Obsidian Vault Scanner with File Watching")
    parser.add_argument("--non-interactive", action="store_true", help="Run without user input (defaults to quick scan)")
    parser.add_argument("--choice", choices=["1", "2", "3"], help="Pre-select initial scan choice")
    
    args = parser.parse_args()
    
    if args.non_interactive and not args.choice:
        args.choice = "1"  # Default to quick scan in non-interactive mode
        
    stats = init_stats()
    if initial_scan(args, stats):
        watch_vault(stats)

if __name__ == "__main__":
    main()
