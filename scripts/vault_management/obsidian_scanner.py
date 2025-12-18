import os
import hashlib
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import requests
import time
from datetime import datetime

class ObsidianVaultScanner:
    def __init__(self, vault_path, embedding_service_url="http://localhost:8000"):
        self.vault_path = Path(vault_path)
        self.embedding_service_url = embedding_service_url
        self.processed_files = {}  # {filepath: hash}
        
    def get_file_hash(self, filepath):
        """Get MD5 hash of file to detect changes"""
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def should_process(self, filepath):
        """Check if file should be processed"""
        # Convert to Path if string
        filepath = Path(filepath)
        
        # Skip hidden files, templates, and attachments
        parts = filepath.parts
        if any(part.startswith('.') or part.startswith('_') for part in parts):
            return False
        if filepath.suffix not in ['.md']:
            return False
        return True
    
    def extract_metadata(self, content):
        """Extract YAML frontmatter metadata"""
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
                    # Remove frontmatter from content
                    content = content[end+3:].strip()
            except:
                pass
        return metadata, content
    
    def chunk_document(self, content, chunk_size=1000, overlap=200):
        """Split document into overlapping chunks"""
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + chunk_size
            chunk = content[start:end]
            
            # Try to break at paragraph or sentence
            if end < len(content):
                last_break = max(
                    chunk.rfind('\n\n'),
                    chunk.rfind('. '),
                    chunk.rfind('! '),
                    chunk.rfind('? ')
                )
                if last_break > chunk_size * 0.5:  # At least 50% through
                    chunk = chunk[:last_break]
                    end = start + last_break
            
            chunks.append(chunk.strip())
            start = end - overlap
            
        return chunks
    
    def process_file(self, filepath):
        """Process a single markdown file"""
        try:
            # Convert to Path object
            filepath = Path(filepath)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract metadata
            metadata, content = self.extract_metadata(content)
            
            # Add file info to metadata
            rel_path = str(filepath.relative_to(self.vault_path))
            metadata.update({
                'filepath': rel_path,
                'filename': filepath.name,
                'modified': datetime.fromtimestamp(
                    os.path.getmtime(filepath)
                ).isoformat()
            })
            
            # Chunk the document
            chunks = self.chunk_document(content)
            
            print(f"Processing: {rel_path} ({len(chunks)} chunks)")
            
            # Send each chunk to embedding service
            for i, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                    
                doc_id = f"{rel_path}_chunk_{i}"
                
                response = requests.post(
                    f"{self.embedding_service_url}/add",
                    json={
                        'id': doc_id,
                        'text': chunk,
                        'metadata': {
                            **metadata,
                            'chunk_id': i,
                            'total_chunks': len(chunks)
                        }
                    },
                    timeout=10
                )
                
                if response.status_code != 200:
                    print(f"Error processing {doc_id}: {response.text}")
            
            # Store file hash
            self.processed_files[str(filepath)] = self.get_file_hash(str(filepath))
            
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
    
    def scan_vault(self):
        """Scan entire vault and process all markdown files"""
        print(f"Scanning vault: {self.vault_path}")
        markdown_files = list(self.vault_path.rglob("*.md"))
        print(f"Found {len(markdown_files)} markdown files")
        
        processed_count = 0
        skipped_count = 0
        
        for filepath in markdown_files:
            if self.should_process(filepath):
                # Check if file changed
                current_hash = self.get_file_hash(str(filepath))
                if str(filepath) not in self.processed_files or \
                   self.processed_files[str(filepath)] != current_hash:
                    self.process_file(filepath)
                    processed_count += 1
                else:
                    skipped_count += 1
            else:
                skipped_count += 1
        
        print(f"\n✅ Vault scan complete!")
        print(f"   Processed: {processed_count} files")
        print(f"   Skipped: {skipped_count} files")

class ObsidianWatchHandler(FileSystemEventHandler):
    """Watch for changes in Obsidian vault"""
    def __init__(self, scanner):
        self.scanner = scanner
    
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            if self.scanner.should_process(event.src_path):
                print(f"File modified: {event.src_path}")
                time.sleep(0.5)  # Wait for write to complete
                self.scanner.process_file(event.src_path)
    
    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.md'):
            if self.scanner.should_process(event.src_path):
                print(f"File created: {event.src_path}")
                time.sleep(0.5)
                self.scanner.process_file(event.src_path)

def main():
    # Your Obsidian vault path
    vault_path = "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
    
    # Check if embedding service is running
    try:
        requests.get('http://localhost:8000/health', timeout=2)
    except:
        print("❌ Error: Embedding service not running!")
        print("   Please start it first: python embedding_service.py")
        return
    
    scanner = ObsidianVaultScanner(vault_path)
    
    print("\n🚀 Starting Obsidian Vault Scanner")
    print("=" * 60)
    
    # Initial scan
    scanner.scan_vault()
    
    # Set up file watcher
    print("\n👀 Setting up file watcher...")
    event_handler = ObsidianWatchHandler(scanner)
    observer = Observer()
    observer.schedule(event_handler, vault_path, recursive=True)
    observer.start()
    
    print(f"\n✅ Watching vault for changes... (Press Ctrl+C to stop)")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping watcher...")
        observer.stop()
    observer.join()
    print("👋 Goodbye!")

if __name__ == "__main__":
    main()