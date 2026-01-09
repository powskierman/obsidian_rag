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
import re

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

def sanitize_content(content: str) -> str:
    """Normalize and sanitize raw file content before parsing."""
    if not content:
        return ""
    content = content.replace("\ufeff", "")
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    content = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", content)
    return content


def _normalize_metadata_value(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item is not None)
    return str(value)


def extract_metadata(content):
    """Extract YAML frontmatter metadata with validation."""
    metadata = {}
    if not content.startswith('---'):
        return metadata, content

    lines = content.splitlines()
    if not lines or lines[0].strip() != '---':
        return metadata, content

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            end_idx = i
            break

    if end_idx is None:
        return metadata, content

    frontmatter_text = "\n".join(lines[1:end_idx])
    body = "\n".join(lines[end_idx + 1:])

    parsed = None
    try:
        import yaml
        parsed = yaml.safe_load(frontmatter_text) if frontmatter_text.strip() else {}
    except Exception:
        parsed = None

    if isinstance(parsed, dict):
        for key, value in parsed.items():
            norm_value = _normalize_metadata_value(value)
            if norm_value is None or key is None:
                continue
            metadata[str(key).strip()] = norm_value
    else:
        for line in frontmatter_text.split('\n'):
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip().strip('"\'')
                if key and value:
                    metadata[key] = value

    return metadata, body.strip()

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

def process_file(
    filepath,
    embedding_service_url="http://localhost:8000",
    refresh_existing: bool = False,
    admin_token: str | None = None
):
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
        
        # Normalize content before parsing
        content = sanitize_content(content)

        # Extract metadata
        metadata, content = extract_metadata(content)
        
        # Add filepath to metadata (build relative path if possible)
        try:
            # Try to get relative path from vault root
            vault_path = os.environ.get('OBSIDIAN_VAULT_PATH')
            if vault_path:
                rel_path = str(filepath.relative_to(Path(vault_path)))
                metadata['filepath'] = rel_path
                # Add individual folder flags for robust filtering in ChromaDB
                # ChromaDB doesn't support list metadata, so we use dir_<name>: True
                parts = Path(rel_path).parent.parts
                for part in parts:
                    if part:
                        metadata[f'dir_{part}'] = True
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
        
        # Optionally delete existing chunks for this filepath
        if refresh_existing and admin_token:
            try:
                delete_resp = requests.post(
                    f"{embedding_service_url}/delete_by_filepath",
                    json={"filepath": metadata.get("filepath", str(filepath))},
                    headers={"X-Admin-Token": admin_token},
                    timeout=10
                )
                if delete_resp.status_code != 200:
                    print(f"  ⚠️  Failed to clear existing chunks: {delete_resp.status_code}")
            except Exception as e:
                print(f"  ⚠️  Failed to clear existing chunks: {e}")

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
            
            # Prepare metadata string to anchor the chunk
            # This prevents confusion between similar documents (like multiple PET scans)
            source_filename = metadata.get('filename', 'Unknown')
            modified_date = metadata.get('modified', 'Unknown Date')
            if ' ' in modified_date: # Clean up ISO format for readability if possible
                modified_date = modified_date.split('T')[0]
                
            anchored_text = f"[Source: {source_filename}] [Date: {modified_date}]\n{chunk_text}"

            # Prepare request
            payload = {
                'id': chunk_id,
                'text': anchored_text,
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
                        f"{embedding_service_url}/upsert",
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

def index_vault(
    vault_path,
    embedding_service_url="http://localhost:8000",
    limit=None,
    refresh_existing: bool = False,
    admin_token: str | None = None
):
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
    if limit:
        print(f"⚠️ Limit set to {limit} files.")
    
    # Check if service is up
    try:
        response = requests.get(f"{embedding_service_url}/stats")
        if response.status_code == 200:
            stats = response.json()
            initial_count = stats.get('total_documents', 0)
            print(f"📊 Initial DB state: {initial_count} documents")
        else:
            print("⚠️ Embedding service returned error on stats, continuing anyway...")
            initial_count = 0
    except:
        print("⚠️ Embedding service stats unreachable, continuing anyway...")
        initial_count = 0
        
    # Get list of files
    print("🔍 Scanning for markdown files...")
    all_files = []
    for root, dirs, files in os.walk(vault_path):
        for name in files:
            filepath = Path(root) / name
            if should_process(filepath):
                all_files.append(filepath)
    
    total_files = len(all_files)
    print(f"📝 Found {total_files} markdown files to process")
    
    if limit:
        all_files = all_files[:limit]
        print(f"🧪 Testing with only {len(all_files)} files.")

    processed = 0
    added_total = 0
    failed_files = 0
    failed_file_list = []
    
    for filepath in tqdm(all_files, desc="Indexing"):
        added = process_file(
            filepath,
            embedding_service_url,
            refresh_existing=refresh_existing,
            admin_token=admin_token
        )
        if added > 0:
            added_total += added
        else:
            failed_files += 1
            failed_file_list.append(str(filepath))
        processed += 1
    
    print()
    print(f"✅ Indexing complete!")
    print(f"   Files processed: {processed}/{len(all_files)}")
    if failed_files > 0:
        print(f"   Files skipped/failed: {failed_files}")
        print(f"\n   Failed/Skipped files:")
        for failed_file in failed_file_list[:10]:  # Show first 10
            print(f"     • {failed_file}")
        if len(failed_file_list) > 10:
            print(f"     ... and {len(failed_file_list) - 10} more")
    print(f"   Chunks added: {added_total}")
    
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
    import argparse
    
    parser = argparse.ArgumentParser(description="Index Obsidian vault into ChromaDB")
    parser.add_argument("vault_path", nargs="?", help="Path to your Obsidian vault")
    parser.add_argument("--limit", type=int, help="Limit indexing to N files (for testing)")
    parser.add_argument("--url", help="Embedding service URL", default=os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000"))
    parser.add_argument("--clear", action="store_true", help="Clear the embedding collection before indexing")
    parser.add_argument("--clear-token", help="Token for /clear endpoint (EMBEDDING_CLEAR_TOKEN)")
    parser.add_argument("--refresh", action="store_true", help="Delete existing chunks per file before upserting")
    
    args = parser.parse_args()
    
    vault_path = args.vault_path or os.getenv("OBSIDIAN_VAULT_PATH")
    
    if not vault_path:
        # Try to read from docker-compose.yml as a fallback
        # ... (rest of the docker-compose logic simplified for brevity since we now have argparse)
        pass
    
    if not vault_path or not Path(vault_path).exists():
        parser.print_help()
        sys.exit(1)
    
    admin_token = args.clear_token or os.getenv("EMBEDDING_CLEAR_TOKEN")

    if args.clear:
        if not admin_token:
            print("❌ Missing clear token. Set EMBEDDING_CLEAR_TOKEN or pass --clear-token.")
            sys.exit(1)
        try:
            response = requests.post(
                f"{args.url}/clear",
                headers={"X-Admin-Token": admin_token},
                timeout=10
            )
            if response.status_code != 200:
                print(f"❌ Failed to clear collection: {response.status_code} {response.text}")
                sys.exit(1)
            print("🧹 Cleared embedding collection.")
        except Exception as e:
            print(f"❌ Failed to clear collection: {e}")
            sys.exit(1)

    if args.refresh and not admin_token:
        print("❌ Missing admin token. Set EMBEDDING_CLEAR_TOKEN or pass --clear-token.")
        sys.exit(1)

    index_vault(
        vault_path,
        args.url,
        limit=args.limit,
        refresh_existing=args.refresh,
        admin_token=admin_token
    )
