import hashlib
import os
import json

DATA_DIR = os.path.expanduser("~/obsidian_rag_local_data/lightrag_db")

FILES_TO_CHECK = [
    "vdb_entities.json",
    "kv_store_full_entities.json",
    "graph_chunk_entity_relation.graphml",
    "kv_store_text_chunks.json"
]

def calculate_checksum(file_path):
    sha256_hash = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            # Read and update hash string value in blocks of 4K
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        return "MISSING"

def main():
    print(f"Verifying data integrity in: {DATA_DIR}")
    results = {}
    
    for filename in FILES_TO_CHECK:
        path = os.path.join(DATA_DIR, filename)
        checksum = calculate_checksum(path)
        size = os.path.getsize(path) if checksum != "MISSING" else 0
        results[filename] = {"checksum": checksum, "size": size}
        print(f"{filename}:")
        print(f"  Size: {size / (1024*1024):.2f} MB")
        print(f"  SHA256: {checksum}")
        print("-" * 40)

    # Save to file for easy transfer/comparison
    output_file = "data_integrity_report.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nReport saved to {output_file}")

if __name__ == "__main__":
    main()
