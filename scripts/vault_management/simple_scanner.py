import os
from pathlib import Path
import requests
from datetime import datetime

VAULT_PATH = "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
EMBEDDING_URL = "http://localhost:8000"

def should_process(filepath):
    filepath = Path(filepath)
    parts = filepath.parts
    if any(part.startswith('.') or part.startswith('_') for part in parts):
        return False
    if filepath.suffix != '.md':
        return False
    return True

def extract_metadata(content):
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

def chunk_document(content, chunk_size=1000, overlap=200):
    chunks = []
    start = 0
    while start < len(content):
        end = start + chunk_size
        chunk = content[start:end]
        if end < len(content):
            last_break = max(chunk.rfind('\n\n'), chunk.rfind('. '), chunk.rfind('! '), chunk.rfind('? '))
            if last_break > chunk_size * 0.5:
                chunk = chunk[:last_break]
                end = start + last_break
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks

def process_file(filepath):
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
        chunks = chunk_document(content)
        if not chunks:
            return 0
        print(f"Processing: {rel_path} ({len(chunks)} chunks)")
        success_count = 0
        for i, chunk in enumerate(chunks):
            doc_id = f"{rel_path}_chunk_{i}"
            try:
                response = requests.post(
                    f"{EMBEDDING_URL}/add",
                    json={'id': doc_id, 'text': chunk, 'metadata': {**metadata, 'chunk_id': i, 'total_chunks': len(chunks)}},
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

def main():
    print("🚀 Simple Obsidian Vault Scanner")
    print("=" * 60)
    try:
        requests.get(f'{EMBEDDING_URL}/health', timeout=2)
    except:
        print("❌ Embedding service not running!")
        print("   Start it: python embedding_service.py")
        return
    vault_path = Path(VAULT_PATH)
    print(f"\nScanning: {vault_path}")
    markdown_files = list(vault_path.rglob("*.md"))
    print(f"Found {len(markdown_files)} markdown files\n")
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
    print("✅ Scan complete!")
    print(f"   Processed: {processed} files")
    print(f"   Skipped: {skipped} files")
    print(f"   Total chunks: {total_chunks}")
    stats = requests.get(f'{EMBEDDING_URL}/stats').json()
    print(f"   Documents in DB: {stats['total_documents']}")
    print("=" * 60)

if __name__ == "__main__":
    main()