#!/usr/bin/env python3
"""
Improved Obsidian Vault Scanner
Enhanced version with better error handling and configurability
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import argparse

try:
    import requests
except ImportError:
    print("❌ Missing requests library. Install with: pip install requests")
    sys.exit(1)

# Default configuration
DEFAULT_VAULT_PATH = "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
EMBEDDING_URL = "http://localhost:8000"

def should_process(filepath):
    """Determine if a file should be processed"""
    filepath = Path(filepath)
    parts = filepath.parts

    # Skip hidden files and directories
    if any(part.startswith('.') for part in parts):
        return False

    # Skip template directories
    if any(part.startswith('_') for part in parts):
        return False

    # Skip specific Obsidian directories
    obsidian_skip = ['.obsidian', '.trash', 'Templates', 'Excalidraw']
    if any(skip_dir in str(filepath) for skip_dir in obsidian_skip):
        return False

    # Only process markdown files
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
    """Extract YAML frontmatter and return metadata + clean content"""
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
                        value = value.strip().strip('"\'')
                        if key and value:
                            metadata[key] = value
                content = content[end+3:].strip()
        except Exception as e:
            print(f"  ⚠️ Warning: Failed to parse frontmatter: {e}")

    return metadata, content

def chunk_document(content, chunk_size=1000, overlap=200):
    """Split content into overlapping chunks with smart boundaries"""
    if not content or len(content.strip()) < 50:
        return []

    chunks = []
    start = 0

    while start < len(content):
        end = start + chunk_size

        if end >= len(content):
            # Last chunk
            chunk = content[start:].strip()
            if chunk:
                chunks.append(chunk)
            break

        chunk = content[start:end]

        # Find natural break points (in order of preference)
        break_points = [
            chunk.rfind('\n\n'),      # Paragraph break
            chunk.rfind('\n# '),      # Header
            chunk.rfind('. '),        # Sentence end
            chunk.rfind('! '),        # Exclamation
            chunk.rfind('? '),        # Question
            chunk.rfind('\n'),        # Line break
        ]

        # Use the best break point that's not too early
        best_break = -1
        for bp in break_points:
            if bp > chunk_size * 0.3:  # Don't break too early
                best_break = bp
                break

        if best_break > 0:
            chunk = chunk[:best_break + 1].strip()
            end = start + best_break + 1

        if chunk.strip():
            chunks.append(chunk.strip())

        start = max(end - overlap, start + 1)  # Ensure progress

    return chunks

def check_document_exists(doc_id):
    """Check if document already exists in database"""
    try:
        # This is a simple check - could be improved with a dedicated endpoint
        response = requests.get(f"{EMBEDDING_URL}/stats", timeout=5)
        return False  # For now, always re-index (could improve this)
    except:
        return False

def process_file(filepath, vault_path, force_reindex=False):
    """Process a single markdown file"""
    try:
        filepath = Path(filepath)

        # Read file with multiple encoding attempts
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

        # Extract metadata and clean content
        metadata, clean_content = extract_metadata(content)

        # Build relative path
        try:
            rel_path = str(filepath.relative_to(vault_path))
        except ValueError:
            rel_path = filepath.name

        # Add file metadata
        file_stats = filepath.stat()
        metadata.update({
            'filepath': rel_path,
            'filename': filepath.name,
            'modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
            'created': datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
            'size_bytes': file_stats.st_size,
            'source': 'obsidian'
        })

        # Chunk the document
        chunks = chunk_document(clean_content)
        if not chunks:
            print(f"  ⚠️ No content to index: {rel_path}")
            return 0

        print(f"Processing: {rel_path} ({len(chunks)} chunks)")

        success_count = 0
        for i, chunk in enumerate(chunks):
            doc_id = f"{rel_path}_chunk_{i}"

            # Skip if exists (unless force reindex)
            if not force_reindex and check_document_exists(doc_id):
                success_count += 1
                continue

            chunk_metadata = {
                **metadata,
                'chunk_id': i,
                'total_chunks': len(chunks),
                'chunk_length': len(chunk)
            }

            # Retry logic for network requests
            for attempt in range(3):
                try:
                    response = requests.post(
                        f"{EMBEDDING_URL}/add",
                        json={
                            'id': doc_id,
                            'text': chunk,
                            'metadata': chunk_metadata
                        },
                        timeout=30
                    )

                    if response.status_code == 200:
                        success_count += 1
                        break
                    else:
                        print(f"  ❌ Error chunk {i} (attempt {attempt+1}): {response.status_code}")
                        if attempt == 2:  # Last attempt
                            print(f"     Response: {response.text[:100]}")

                except requests.exceptions.Timeout:
                    print(f"  ⏱️ Timeout chunk {i} (attempt {attempt+1})")
                except requests.exceptions.RequestException as e:
                    print(f"  ❌ Network error chunk {i} (attempt {attempt+1}): {e}")

                if attempt < 2:  # Don't sleep after last attempt
                    import time
                    time.sleep(1)

        return success_count

    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        return 0

def main():
    """Main scanning function"""
    parser = argparse.ArgumentParser(description='Index Obsidian vault for vector search')
    parser.add_argument('--vault-path', default=DEFAULT_VAULT_PATH,
                       help='Path to Obsidian vault')
    parser.add_argument('--force-reindex', action='store_true',
                       help='Re-index all files even if they exist')
    parser.add_argument('--limit', type=int,
                       help='Limit number of files to process (for testing)')

    args = parser.parse_args()

    print("🚀 Enhanced Obsidian Vault Scanner")
    print("=" * 60)

    # Check embedding service
    try:
        response = requests.get(f'{EMBEDDING_URL}/health', timeout=5)
        if response.status_code != 200:
            print("❌ Embedding service not healthy!")
            return
        print("✅ Embedding service is running")
    except requests.exceptions.RequestException:
        print("❌ Embedding service not running!")
        print("   Start it with: docker-compose up -d")
        return

    # Validate vault path
    vault_path = Path(args.vault_path)
    if not vault_path.exists():
        print(f"❌ Vault path does not exist: {vault_path}")
        return

    print(f"\nScanning: {vault_path}")

    # Find all markdown files
    markdown_files = list(vault_path.rglob("*.md"))
    processable_files = [f for f in markdown_files if should_process(f)]

    print(f"Found {len(markdown_files)} total .md files")
    print(f"Will process {len(processable_files)} files (after filtering)")

    if args.limit:
        processable_files = processable_files[:args.limit]
        print(f"Limited to first {args.limit} files")

    # Get initial stats
    try:
        stats = requests.get(f'{EMBEDDING_URL}/stats').json()
        print(f"Current documents in DB: {stats.get('total_documents', 0)}")
    except:
        print("Could not get initial DB stats")

    print("\n" + "=" * 60)

    # Process files
    processed = 0
    skipped = 0
    total_chunks = 0

    for i, filepath in enumerate(processable_files, 1):
        chunks = process_file(filepath, vault_path, args.force_reindex)
        if chunks > 0:
            processed += 1
            total_chunks += chunks
        else:
            skipped += 1

        # Progress update
        if i % 25 == 0 or i == len(processable_files):
            try:
                stats = requests.get(f'{EMBEDDING_URL}/stats').json()
                db_docs = stats.get('total_documents', 0)
                print(f"\n--- Progress: {i}/{len(processable_files)} files ---")
                print(f"    Processed: {processed}, Skipped: {skipped}")
                print(f"    Documents in DB: {db_docs}")
                print(f"    Chunks added: {total_chunks}\n")
            except:
                pass

    # Final summary
    print("\n" + "=" * 60)
    print("✅ Scan complete!")
    print(f"   Files processed: {processed}")
    print(f"   Files skipped: {skipped}")
    print(f"   Total chunks added: {total_chunks}")

    try:
        stats = requests.get(f'{EMBEDDING_URL}/stats').json()
        print(f"   Total documents in DB: {stats.get('total_documents', 0)}")
        print(f"   Estimated notes: ~{stats.get('estimated_notes', 0)}")
    except:
        print("   Could not get final DB stats")

    print("=" * 60)

if __name__ == "__main__":
    main()