#!/usr/bin/env python3
"""
Simple script to index Obsidian vault into ChromaDB via embedding service
"""

import os
import json
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

REPO_ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_EXTENSIONS = {".md", ".pdf"}

def _service_headers() -> dict:
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    if not api_key:
        return {}
    return {"X-API-Key": api_key}

def get_file_hash(filepath):
    """Get MD5 hash of file to detect changes"""
    hash_obj = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()

def safe_get_file_hash(filepath: Path) -> str | None:
    """Get a file hash, returning None on failure."""
    try:
        return get_file_hash(filepath)
    except Exception as e:
        print(f"  ⚠️  Failed to hash {filepath}: {e}")
        return None

def get_cache_path(vault_path: Path) -> Path:
    """Return the cache file path for incremental indexing."""
    override = os.getenv("INDEX_VAULT_CACHE_PATH")
    if override:
        return Path(override)

    cache_dir = REPO_ROOT / "data" / "indexing"
    vault_hash = hashlib.md5(str(vault_path).encode("utf-8")).hexdigest()[:12]
    return cache_dir / f"index_vault_hashes_{vault_hash}.json"

def load_index_cache(cache_path: Path) -> dict:
    """Load the index cache from disk."""
    if not cache_path.exists():
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"  ⚠️  Failed to read cache {cache_path}: {e}")
        return {}

def save_index_cache(cache_path: Path, cache: dict) -> None:
    """Persist the index cache to disk."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
    temp_path.replace(cache_path)

def get_cache_key(filepath: Path, vault_path: Path) -> str:
    """Return a stable cache key for a file."""
    base_path = Path(os.environ.get("OBSIDIAN_VAULT_PATH", vault_path))
    try:
        return str(filepath.relative_to(base_path))
    except (ValueError, TypeError):
        return str(filepath)

def build_cache_entry(filepath: Path, file_hash: str) -> dict:
    """Build a cache entry for a file."""
    entry = {"hash": file_hash}
    try:
        file_stats = filepath.stat()
        entry["modified"] = datetime.fromtimestamp(file_stats.st_mtime).isoformat()
        entry["size_bytes"] = file_stats.st_size
    except Exception:
        pass
    return entry

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
    
    if filepath.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False
    
    # Skip empty files
    try:
        if filepath.stat().st_size == 0:
            return False
    except OSError:
        return False
    
    return True

def extract_pdf_text(filepath: Path) -> str:
    """Extract text from a PDF file using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        print(f"  ⚠️  pypdf not installed; skipping PDF: {filepath}")
        return ""

    try:
        reader = PdfReader(str(filepath))
    except Exception as e:
        print(f"  ⚠️  Failed to read PDF {filepath}: {e}")
        return ""

    pages_text = []
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            pages_text.append(f"[Page {page_index}]\n{page_text}")

    return "\n\n".join(pages_text).strip()

def clean_pdf_text(text: str) -> str:
    """Clean common PDF extraction artifacts."""
    # Remove repetitive page numbers (e.g., "Page 1 of 10")
    text = re.sub(r'\bPage \d+ of \d+\b', '', text)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE) # Standalone numbers
    return text.strip()


def read_file_content(filepath: Path) -> tuple[str, dict]:
    """Read file content with basic metadata based on file type."""
    suffix = filepath.suffix.lower()
    if suffix == ".pdf":
        content = extract_pdf_text(filepath)
        content = clean_pdf_text(content)
        return content, {"filetype": "pdf"}

    content = None
    for encoding in ["utf-8", "utf-8-sig", "latin1"]:
        try:
            with open(filepath, "r", encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        return "", {"filetype": "markdown", "read_error": "decode"}

    return content, {"filetype": "markdown"}

from src.indexing.frontmatter import extract_frontmatter, sanitize_content

def extract_metadata(content: str) -> tuple[dict, str]:
    """
    Backward-compatible metadata extraction for legacy callers/tests.

    Uses shared frontmatter parser and normalizes list values to comma-separated
    strings to match historical `index_vault.extract_metadata` behavior.
    """
    metadata, body = extract_frontmatter(content)
    normalized = {}
    for key, value in metadata.items():
        if isinstance(value, list):
            normalized[key] = ", ".join(str(item) for item in value)
        else:
            normalized[key] = value
    return normalized, body

def smart_chunk_document(content, max_size=4000, overlap=500):
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
            chunk.rfind('\n- '),      # List item
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
            return 0, "skipped"
        
        # Read file content
        content, base_metadata = read_file_content(filepath)
        if not content:
            if base_metadata.get("read_error") == "decode":
                print(f"  ❌ Could not decode {filepath}")
                return 0, "failed"
            return 0, "skipped"
        
        if not content or not content.strip():
            return 0, "skipped"
        
        # Normalize content before parsing
        content = sanitize_content(content)

        # Extract metadata
        metadata = {}
        if filepath.suffix.lower() == ".md":
            metadata, content = extract_frontmatter(content)

        for key, value in base_metadata.items():
            if key == "read_error":
                continue
            metadata.setdefault(key, value)
        
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
                    headers={**_service_headers(), "X-Admin-Token": admin_token},
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
            return 0, "skipped"
        
        # Print progress for each file (like old version)
        rel_path = metadata.get('filepath', filepath.name)
        print(f"Processing: {rel_path} ({len(chunks)} chunks)")
        
        added = 0
        use_add_endpoint = False
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
            
            context_parts = [f"Source: {source_filename}", f"Date: {modified_date}"]
            
            # Add Tags if present
            tags = metadata.get('tags')
            if tags:
                context_parts.append(f"Tags: {tags}")
            
            # Add Aliases if present
            aliases = metadata.get('aliases')
            if aliases:
                context_parts.append(f"Aliases: {aliases}")

            context_str = "[" + "] [".join(context_parts) + "]"
            anchored_text = f"{context_str}\n{chunk_text}"

            # Prepare metadata for ChromaDB (no lists allowed)
            safe_metadata = {}
            for k, v in metadata.items():
                if isinstance(v, list):
                    safe_metadata[k] = ", ".join(str(x) for x in v)
                else:
                    safe_metadata[k] = v

            # Prepare request
            payload = {
                'id': chunk_id,
                'text': anchored_text,
                'metadata': {
                    **safe_metadata,
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
                    endpoint = "add" if use_add_endpoint else "upsert"
                    response = requests.post(
                        f"{embedding_service_url}/{endpoint}",
                        json=payload,
                        headers=_service_headers(),
                        timeout=30
                    )
                    if response.status_code == 404 and not use_add_endpoint:
                        use_add_endpoint = True
                        response = requests.post(
                            f"{embedding_service_url}/add",
                            json=payload,
                            headers=_service_headers(),
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
        
        if added > 0:
            return added, "indexed"
        return 0, "failed"
    
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        return 0, "failed"

def index_vault(
    vault_path,
    embedding_service_url="http://localhost:8000",
    limit=None,
    refresh_existing: bool = False,
    admin_token: str | None = None,
    incremental: bool = True,
    reset_cache: bool = False,
    cache_path: Path | None = None
):
    """Index entire Obsidian vault"""
    vault_path = Path(vault_path)
    
    if not vault_path.exists():
        print(f"❌ Vault path does not exist: {vault_path}")
        return
    
    print(f"📚 Indexing vault: {vault_path}")
    print(f"🔗 Embedding service: {embedding_service_url}")
    print()

    cache_path = Path(cache_path) if cache_path else get_cache_path(vault_path)
    cache = load_index_cache(cache_path)
    cache_dirty = False
    if reset_cache and cache_path.exists():
        try:
            cache_path.unlink()
            cache = {}
            cache_dirty = True
            print(f"🧹 Cleared incremental cache: {cache_path}")
        except Exception as e:
            print(f"⚠️  Failed to clear cache {cache_path}: {e}")

    if incremental:
        print(f"🧭 Incremental indexing: enabled")
        print(f"🗂️  Cache file: {cache_path}")
        print()
    else:
        print(f"🧭 Incremental indexing: disabled (full reindex)")
        print(f"🗂️  Cache file: {cache_path}")
        print()
    
    # Check if service is available
    try:
        response = requests.get(
            f"{embedding_service_url}/health",
            timeout=5,
            headers=_service_headers()
        )
        if response.status_code != 200:
            print(f"❌ Embedding service not healthy")
            return
    except Exception as e:
        print(f"❌ Cannot connect to embedding service: {e}")
    if limit:
        print(f"⚠️ Limit set to {limit} files.")
    
    # Check if service is up
    try:
        response = requests.get(
            f"{embedding_service_url}/stats",
            headers=_service_headers()
        )
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
    print("🔍 Scanning for markdown and PDF files...")
    all_files = []
    for root, dirs, files in os.walk(vault_path):
        for name in files:
            filepath = Path(root) / name
            if should_process(filepath):
                all_files.append(filepath)
    
    total_files = len(all_files)
    print(f"📝 Found {total_files} markdown/PDF files in vault")

    files_to_process = []
    skipped_unchanged = 0
    current_keys = set()

    if incremental:
        for filepath in all_files:
            cache_key = get_cache_key(filepath, vault_path)
            current_keys.add(cache_key)
            file_hash = safe_get_file_hash(filepath)
            cached = cache.get(cache_key, {})
            if file_hash and cached.get("hash") == file_hash:
                skipped_unchanged += 1
                continue
            files_to_process.append((filepath, cache_key, file_hash))
    else:
        for filepath in all_files:
            cache_key = get_cache_key(filepath, vault_path)
            current_keys.add(cache_key)
            files_to_process.append((filepath, cache_key, None))

    if cache:
        removed_keys = [key for key in cache if key not in current_keys]
        if removed_keys:
            for key in removed_keys:
                cache.pop(key, None)
                if admin_token:
                    try:
                        requests.post(
                            f"{embedding_service_url}/delete_by_filepath",
                            json={"filepath": key},
                            headers={**_service_headers(), "X-Admin-Token": admin_token},
                            timeout=10
                        )
                    except Exception as e:
                        print(f"  ⚠️  Failed to delete stale chunks for {key}: {e}")
            cache_dirty = True
            print(f"🧹 Removed {len(removed_keys)} stale cache entries")

    if incremental:
        print(f"↪️  Skipping {skipped_unchanged} unchanged files")
        print(f"🆕 Files to index: {len(files_to_process)}")

    if limit:
        files_to_process = files_to_process[:limit]
        print(f"🧪 Testing with only {len(files_to_process)} files.")

    processed = 0
    added_total = 0
    failed_files = 0
    failed_file_list = []
    skipped_files = 0
    
    for filepath, cache_key, file_hash in tqdm(files_to_process, desc="Indexing"):
        added, status = process_file(
            filepath,
            embedding_service_url,
            refresh_existing=refresh_existing,
            admin_token=admin_token
        )

        if status == "indexed":
            added_total += added
        elif status == "skipped":
            skipped_files += 1
        else:
            failed_files += 1
            failed_file_list.append(str(filepath))

        if status in {"indexed", "skipped"}:
            if not file_hash:
                file_hash = safe_get_file_hash(filepath)
            if file_hash:
                cache[cache_key] = build_cache_entry(filepath, file_hash)
                cache_dirty = True

        processed += 1
    
    print()
    print(f"✅ Indexing complete!")
    print(f"   Files processed: {processed}/{len(files_to_process)}")
    if skipped_unchanged > 0:
        print(f"   Unchanged files skipped: {skipped_unchanged}")
    if skipped_files > 0:
        print(f"   Files skipped (empty/short): {skipped_files}")
    if failed_files > 0:
        print(f"   Files failed: {failed_files}")
        print(f"\n   Failed files:")
        for failed_file in failed_file_list[:10]:  # Show first 10
            print(f"     • {failed_file}")
        if len(failed_file_list) > 10:
            print(f"     ... and {len(failed_file_list) - 10} more")
    print(f"   Chunks added: {added_total}")
    
    # Get final stats
    try:
        response = requests.get(
            f"{embedding_service_url}/stats",
            timeout=5,
            headers=_service_headers()
        )
        if response.status_code == 200:
            stats = response.json()
            final_count = stats.get('total_documents', 0)
            added_count = final_count - initial_count
            print(f"   Total documents in DB: {final_count} (added: {added_count})")
            print(f"   Estimated notes: ~{stats.get('estimated_notes', 0)}")
    except:
        pass

    if cache_dirty:
        save_index_cache(cache_path, cache)
        print(f"🗂️  Updated incremental cache: {cache_path}")

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
    parser.add_argument("--full", action="store_true", help="Index all files, ignoring the incremental cache")
    parser.add_argument("--reset-cache", action="store_true", help="Reset the incremental cache before indexing")
    parser.add_argument("--cache-path", help="Override incremental cache path (INDEX_VAULT_CACHE_PATH)")
    
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
                headers={**_service_headers(), "X-Admin-Token": admin_token},
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

    cache_path = Path(args.cache_path) if args.cache_path else None
    reset_cache = args.reset_cache or args.clear

    index_vault(
        vault_path,
        args.url,
        limit=args.limit,
        refresh_existing=args.refresh,
        admin_token=admin_token,
        incremental=not args.full,
        reset_cache=reset_cache,
        cache_path=cache_path
    )
