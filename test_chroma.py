import chromadb
import sys
import os

db_path = "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/chroma_db"
if not os.path.exists(db_path):
    print(f"Path not found: {db_path}")
    sys.exit(1)

client = chromadb.PersistentClient(path=db_path)
print("Collections:")
for collection in client.list_collections():
    print(f"- {collection.name}")
    try:
        col = client.get_collection(collection.name)
        count = col.count()
        print(f"  Documents: {count}")
    except Exception as e:
        print(f"  Error reading doc count: {e}")
