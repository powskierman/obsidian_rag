#!/usr/bin/env python3
"""
Attempt to recover data from old ChromaDB backup
This script tries to export chunks from the old database before schema migration
"""

import sys
from pathlib import Path
import json

def try_recover_chromadb(backup_path, output_file="recovered_chunks.json"):
    """Try to recover chunks from old ChromaDB"""
    print(f"🔍 Attempting to recover from: {backup_path}")
    print()
    
    # Try different ChromaDB versions/approaches
    recovery_methods = [
        ("Direct ChromaDB access", try_direct_access),
        ("SQLite extraction", try_sqlite_extraction),
    ]
    
    for method_name, method_func in recovery_methods:
        print(f"Trying: {method_name}...")
        try:
            chunks = method_func(backup_path)
            if chunks:
                print(f"✅ Success! Recovered {len(chunks)} chunks")
                save_chunks(chunks, output_file)
                return chunks
        except Exception as e:
            print(f"❌ {method_name} failed: {e}")
            continue
    
    print("❌ Could not recover data from backup")
    return None

def try_direct_access(backup_path):
    """Try to access ChromaDB directly"""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=backup_path)
        collections = client.list_collections()
        
        if not collections:
            return None
        
        collection = collections[0]
        results = collection.get(include=['documents', 'metadatas'])
        
        chunks = []
        for i, (doc, meta) in enumerate(zip(
            results['documents'],
            results.get('metadatas', [{}] * len(results['documents']))
        )):
            chunks.append({
                'id': results.get('ids', [f'chunk_{i}'])[i],
                'text': doc,
                'metadata': meta
            })
        
        return chunks
    except Exception as e:
        raise Exception(f"Direct access failed: {e}")

def try_sqlite_extraction(backup_path):
    """Try to extract data directly from SQLite"""
    try:
        import sqlite3
        sqlite_path = Path(backup_path) / "chroma.sqlite3"
        
        if not sqlite_path.exists():
            raise Exception("SQLite file not found")
        
        conn = sqlite3.connect(str(sqlite_path))
        cursor = conn.cursor()
        
        # Try to read from embeddings table
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"   Found tables: {tables}")
        except:
            pass
        
        # This is complex and may not work due to schema changes
        raise Exception("SQLite extraction not implemented (schema too different)")
        
    except Exception as e:
        raise Exception(f"SQLite extraction failed: {e}")

def save_chunks(chunks, output_file):
    """Save recovered chunks to JSON"""
    with open(output_file, 'w') as f:
        json.dump(chunks, f, indent=2)
    print(f"💾 Saved to: {output_file}")
    print(f"   You can use this to re-index via the embedding service")

if __name__ == "__main__":
    backup_path = sys.argv[1] if len(sys.argv) > 1 else "chroma_db_backup_20251107_112029"
    
    if not Path(backup_path).exists():
        print(f"❌ Backup path not found: {backup_path}")
        print()
        print("Available backups:")
        import glob
        for backup in glob.glob("chroma_db_backup_*"):
            print(f"  - {backup}")
        sys.exit(1)
    
    try_recover_chromadb(backup_path)

