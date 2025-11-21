#!/usr/bin/env python3
"""
Simple script to index Obsidian vault into ChromaDB via embedding service
"""

import os
import hashlib
from pathlib import Path
import requests
import time
from datetime import datetime

# Try to import tqdm for progress bar, fallback to simple iteration
try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    def tqdm(iterable, desc=""):
        return iterable

def get_file_hash(filepath):
    """Get MD5 hash of file to detect changes"""
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def should_process(filepath):
    """Check if file should be processed"""
    filepath = Path(filepath)
    
    # Skip hidden files, templates, and attachments
    parts = filepath.parts
    if any(part.startswith('.') or part.startswith('_') for part in parts):
        return False
    
    # Skip specific Obsidian directories
    obsidian_skip = ['.obsidian', '.trash', 'Templates', 'Excalidraw']
    if any(skip_dir in str(filepath) for skip_dir in obsidian_skip):
        return False
    
    if filepath.suffix.lower() != '.md':
        return False
    
    # Skip empty files
    try:
        if filepath.stat().st_size == 0:
            return False
    except OSError:
        return False
    
    return True

def extract_metadata(content):
    """Extract YAML frontmatter metadata (like the old working version)"""
    metadata = {}
    if content.startswith('---'):
        try:
            end = content.find('---', 3)
            if end != -1:
                frontmatter = content[3:end].strip()
                for line in frontmatter.split('\n'):
                    line = line.strip()
                    if ':' in line and not line.startswith('#'):
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')  # Strip quotes like old version
                        if key and value:
                            metadata[key] = value
                # Remove frontmatter from content
                content = content[end+3:].strip()
        except Exception as e:
            print(f"  ⚠️ Warning: Failed to parse frontmatter: {e}")
    return metadata, content

def smart_chunk_document(content, max_size=1000, overlap=200):
    """Split content into overlapping chunks with smart boundaries (like old working version)"""
    if not content or len(content.strip()) < 50:
        return []
    
    if len(content) <= max_size:
        return [content.strip()]
    
    chunks = []
    start = 0
    
    while start < len(content):
        end = start + max_size
        
        if end >= len(content):
            # Last chunk
            chunk = content[start:].strip()
            if chunk:
                chunks.append(chunk)
            break
        
        chunk = content[start:end]
        
        # Find natural break points (in order of preference, like old version)
        break_points = [
            chunk.rfind('\n\n'),      # Paragraph break
            chunk.rfind('\n# '),      # Header
            chunk.rfind('. '),        # Sentence end
            chunk.rfind('! '),        # Exclamation
            chunk.rfind('? '),        # Question
            chunk.rfind('\n'),        # Line break
        ]
        
        # Use the best break point that's not too early (like old version)
        best_break = -1
        for bp in break_points:
            if bp > max_size * 0.3:  # Don't break too early (30% minimum)
                best_break = bp
                break
        
        if best_break > 0:
            chunk = chunk[:best_break + 1].strip()
            end = start + best_break + 1
        
        if chunk.strip():
            chunks.append(chunk.strip())
        
        # Move start with overlap, ensure progress
        start = max(end - overlap, start + 1)
    
    return chunks if chunks else [content[:max_size].strip()]

def process_file(filepath, embedding_service_url="http://localhost:8000"):
    """Process a single file and add to embedding service"""
    try:
        filepath = Path(filepath)
        
        if not should_process(filepath):
            return 0
        
        # Read file with multiple encoding attempts (like the old working version)
        content = None
        for encoding in ['utf-8', 'utf-8-sig', 'latin1']:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        if content is None:
            print(f"  ❌ Could not decode {filepath}")
            return 0
        
        if not content or not content.strip():
            return 0
        
        # Extract metadata
        metadata, content = extract_metadata(content)
        
        # Add filepath to metadata (build relative path if possible)
        try:
            # Try to get relative path from vault root
            vault_path = os.environ.get('OBSIDIAN_VAULT_PATH')
            if vault_path:
                rel_path = str(filepath.relative_to(Path(vault_path)))
                metadata['filepath'] = rel_path
            else:
                metadata['filepath'] = str(filepath)
        except (ValueError, TypeError):
            metadata['filepath'] = str(filepath)
        
        metadata['filename'] = filepath.name
        
        # Add file stats
        try:
            file_stats = filepath.stat()
            metadata['modified'] = datetime.fromtimestamp(file_stats.st_mtime).isoformat()
            metadata['created'] = datetime.fromtimestamp(file_stats.st_ctime).isoformat()
            metadata['size_bytes'] = file_stats.st_size
        except:
            pass
        
        # Chunk document
        chunks = smart_chunk_document(content)
        if not chunks:
            rel_path = metadata.get('filepath', filepath.name)
            print(f"  ⚠️ No content to index: {rel_path}")
            return 0
        
        # Print progress for each file (like old version)
        rel_path = metadata.get('filepath', filepath.name)
        print(f"Processing: {rel_path} ({len(chunks)} chunks)")
        
        added = 0
        for i, chunk in enumerate(chunks):
            # Skip empty chunks
            if not chunk or not chunk.strip():
                continue
            
            # Create unique ID (using relative path like old version)
            rel_path = metadata.get('filepath', str(filepath))
            chunk_id = f"{rel_path}_chunk_{i}"
            
            # Ensure chunk is a string and not empty
            chunk_text = str(chunk).strip()
            if not chunk_text:
                continue
            
            # Prepare request
            payload = {
                'id': chunk_id,
                'text': chunk_text,
                'metadata': {
                    **metadata,
                    'chunk_id': i,
                    'total_chunks': len(chunks),
                    'chunk_length': len(chunk_text)
                }
            }
            
            # Validate payload before sending
            if not payload.get('id') or not payload.get('text'):
                continue
            
            # Send to embedding service with retry logic (like the old working version)
            for attempt in range(3):
                try:
                    response = requests.post(
                        f"{embedding_service_url}/add",
                        json=payload,
                        timeout=30
                    )
                    if response.status_code == 200:
                        added += 1
                        break
                    else:
                        if attempt == 2:  # Last attempt
                            print(f"  ⚠️  Failed to add chunk {i}: {response.status_code}")
                except requests.exceptions.Timeout:
                    if attempt == 2:
                        print(f"  ⏱️  Timeout adding chunk {i} (final attempt)")
                except requests.exceptions.RequestException as e:
                    if attempt == 2:
                        print(f"  ❌ Network error chunk {i}: {e}")
                except Exception as e:
                    if attempt == 2:
                        print(f"  ❌ Error adding chunk {i}: {e}")
                
                if attempt < 2:  # Don't sleep after last attempt
                    time.sleep(1)  # 1 second delay between retries
        
        return added
    
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        return 0

def index_vault(vault_path, embedding_service_url="http://localhost:8000"):
    """Index entire Obsidian vault"""
    vault_path = Path(vault_path)
    
    if not vault_path.exists():
        print(f"❌ Vault path does not exist: {vault_path}")
        return
    
    print(f"📚 Indexing vault: {vault_path}")
    print(f"🔗 Embedding service: {embedding_service_url}")
    print()
    
    # Check if service is available
    try:
        response = requests.get(f"{embedding_service_url}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Embedding service not healthy")
            return
    except Exception as e:
        print(f"❌ Cannot connect to embedding service: {e}")
        print(f"   Make sure the service is running: docker-compose up -d")
        return
    
    # Find all markdown files
    md_files = list(vault_path.rglob("*.md"))
    print(f"📄 Found {len(md_files)} markdown files")
    print()
    
    # Process files
    total_chunks = 0
    processed_files = 0
    failed_files = 0
    failed_file_list = []  # Track which files failed
    
    # Get initial count
    try:
        initial_response = requests.get(f"{embedding_service_url}/stats", timeout=5)
        if initial_response.status_code == 200:
            initial_stats = initial_response.json()
            initial_count = initial_stats.get('total_documents', 0)
            print(f"📊 Starting with {initial_count} documents in database")
            print()
    except:
        initial_count = 0
    
    # Process files sequentially (like the old working version)
    # This avoids threading issues, resource leaks, and system kills
    print("🚀 Processing files sequentially (stable and reliable)")
    print()
    
    for i, filepath in enumerate(md_files, 1):
        chunks = process_file(filepath, embedding_service_url)
        if chunks > 0:
            total_chunks += chunks
            processed_files += 1
        else:
            failed_files += 1
            failed_file_list.append(str(filepath))
        
        # Progress update every 25 files (like the old working version)
        if i % 25 == 0 or i == len(md_files):
            try:
                stats_response = requests.get(f"{embedding_service_url}/stats", timeout=5)
                if stats_response.status_code == 200:
                    current_stats = stats_response.json()
                    current_count = current_stats.get('total_documents', 0)
                    print(f"\n--- Progress: {i}/{len(md_files)} files ---")
                    print(f"    Processed: {processed_files}, Failed/Skipped: {failed_files}")
                    print(f"    Documents in DB: {current_count}")
                    print(f"    Chunks added: {total_chunks}\n")
            except:
                pass
    
    print()
    print(f"✅ Indexing complete!")
    print(f"   Files processed: {processed_files}/{len(md_files)}")
    if failed_files > 0:
        print(f"   Files skipped/failed: {failed_files}")
        print(f"\n   Failed/Skipped files:")
        for failed_file in failed_file_list[:10]:  # Show first 10
            print(f"     • {failed_file}")
        if len(failed_file_list) > 10:
            print(f"     ... and {len(failed_file_list) - 10} more")
    print(f"   Chunks added: {total_chunks}")
    
    # Get final stats
    try:
        response = requests.get(f"{embedding_service_url}/stats", timeout=5)
        if response.status_code == 200:
            stats = response.json()
            final_count = stats.get('total_documents', 0)
            added_count = final_count - initial_count
            print(f"   Total documents in DB: {final_count} (added: {added_count})")
            print(f"   Estimated notes: ~{stats.get('estimated_notes', 0)}")
    except:
        pass

if __name__ == "__main__":
    import sys
    
    # Get vault path from docker-compose.yml or use default
    vault_path = os.getenv("OBSIDIAN_VAULT_PATH")
    
    if not vault_path:
        # Try to read from docker-compose.yml
        docker_compose_path = Path(__file__).parent / "docker-compose.yml"
        if docker_compose_path.exists():
            import re
            with open(docker_compose_path) as f:
                for line in f:
                    if "/app/vault" in line:
                        # Extract host path from volume mount
                        # Format: "- \"/path/to/vault:/app/vault:ro\"" or similar
                        # Look for pattern: quoted path followed by :/app/vault
                        match = re.search(r'["\']([^"\']+):/app/vault', line)
                        if match:
                            vault_path = match.group(1)
                            break
                        # Fallback: split on :/app/vault
                        if ":/app/vault" in line:
                            parts = line.split(":/app/vault")
                            if len(parts) > 0:
                                vault_path = parts[0].strip().strip('"').strip("'").strip("-").strip()
                                # Remove leading dash and spaces if present
                                while vault_path.startswith("-") or vault_path.startswith(" "):
                                    vault_path = vault_path.lstrip("- ").strip()
                                break
    
    if not vault_path or not Path(vault_path).exists():
        if len(sys.argv) > 1:
            vault_path = sys.argv[1]
        else:
            print("❌ Vault path not found")
            print()
            print("Usage:")
            print(f"  python {sys.argv[0]} <vault_path>")
            print()
            print("Or set OBSIDIAN_VAULT_PATH environment variable")
            print("Or configure in docker-compose.yml")
            sys.exit(1)
    
    embedding_service_url = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
    
    index_vault(vault_path, embedding_service_url)

