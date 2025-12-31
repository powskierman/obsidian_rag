import os
import glob
import logging
from pathlib import Path
from typing import List, Dict
from tqdm import tqdm
from kimi_graph_builder import GraphBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

VAULT_PATH = "/app/vault"
GRAPH_PATH = "/app/graph_data/knowledge_graph_full.pkl"
CHUNK_SIZE = 4000
CHUNK_OVERLAP = 200

def get_markdown_files(vault_path: str) -> List[str]:
    """Recursively find all markdown files in the vault"""
    return glob.glob(os.path.join(vault_path, "**/*.md"), recursive=True)

def simple_chunk_text(text: str, chunk_size: int = 4000, overlap: int = 200) -> List[str]:
    """Simple character-based chunking with overlap"""
    if not text:
        return []
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap
        
    return chunks

import shutil
import argparse

def process_vault():
    """Main function to process vault and build graph"""
    parser = argparse.ArgumentParser(description='Build Obsidian Knowledge Graph')
    parser.add_argument('--force-refresh', action='store_true', help='Force rebuild graph from scratch')
    args = parser.parse_args()

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set")
        return

    # Use a temp path for building to avoid iCloud sync issues
    TEMP_GRAPH_PATH = "/tmp/knowledge_graph_full.pkl"
    FINAL_GRAPH_PATH = "/app/graph_data/knowledge_graph_full.pkl"

    logger.info(f"Initializing GraphBuilder...")
    builder = GraphBuilder(api_key=api_key)
    
    # Handle force refresh
    if args.force_refresh:
        logger.info("Force refresh requested. Ignoring existing graph.")
        if os.path.exists(TEMP_GRAPH_PATH):
            os.remove(TEMP_GRAPH_PATH)
    else:
        # Try to load existing graph to resume work
        # Prefer the one in temp if it exists (interrupted run), otherwise copy from final
        if os.path.exists(TEMP_GRAPH_PATH):
            logger.info(f"Resuming from temp graph at {TEMP_GRAPH_PATH}...")
            builder.load_graph(TEMP_GRAPH_PATH)
        elif os.path.exists(FINAL_GRAPH_PATH):
            logger.info(f"Loading existing graph from {FINAL_GRAPH_PATH}...")
            # Copy to temp to work on it
            shutil.copy2(FINAL_GRAPH_PATH, TEMP_GRAPH_PATH)
            builder.load_graph(TEMP_GRAPH_PATH)
    
    logger.info(f"Scanning vault at {VAULT_PATH}...")
    files = get_markdown_files(VAULT_PATH)
    logger.info(f"Found {len(files)} markdown files")
    
    all_chunks = []
    
    logger.info("Reading and chunking files...")
    for filepath in tqdm(files, desc="Chunking files"):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                
            file_chunks = simple_chunk_text(content, CHUNK_SIZE, CHUNK_OVERLAP)
            
            # Create metadata
            rel_path = os.path.relpath(filepath, VAULT_PATH)
            filename = os.path.basename(filepath)
            
            for i, chunk in enumerate(file_chunks):
                all_chunks.append({
                    'text': chunk,
                    'metadata': {
                        'filename': filename,
                        'filepath': rel_path,
                        'chunk_id': i,
                        'total_chunks': len(file_chunks)
                    }
                })
        except Exception as e:
            logger.error(f"Error processing file {filepath}: {e}")
            continue
            
    logger.info(f"Generated {len(all_chunks)} chunks to process")
    
    # Check what's already processed
    processed_hashes = builder.processed_chunks
    chunks_to_process = []
    
    for chunk in all_chunks:
        chunk_hash = builder._get_chunk_hash(chunk['text'], chunk['metadata'])
        if chunk_hash not in processed_hashes:
            chunks_to_process.append(chunk)
            
    logger.info(f"{len(chunks_to_process)} new chunks to process")
    
    if chunks_to_process:
        logger.info("Starting graph extraction...")
        # Process in batches
        # Update save path logic in GraphBuilder (or we just manually save to TEMP_GRAPH_PATH)
        # The GraphBuilder.build_graph_from_chunks handles saving checkpoints, but we need to ensure
        # it saves to our TEMP_GRAPH_PATH. 
        # Since GraphBuilder hardcodes GRAPH_DATA_DIR in save_graph if path is not provided,
        # we need to be careful. Ideally we patch GraphBuilder or pass a custom saver.
        # But GraphBuilder.save_graph accepts a filepath.
        # We need to make sure build_graph_from_chunks calls save_graph with our desired path.
        # However, build_graph_from_chunks calls: self.save_graph(str(GRAPH_DATA_DIR / f"graph_checkpoint_{i+1}.pkl"))
        # This writes to local dir. We should override this behavior or just let it checkpoint locally in /app/graph_data/
        # Wait, /app/graph_data IS the mounted volume. 
        # Checkpoints WILL write to iCloud if we let them.
        # We need to monkeypatch or modify GraphBuilder to save checkpoints to /tmp.
        
        # Override save path in builder for this session (hacky but works if we don't modify class)
        # Better: iterate manually here instead of calling build_graph_from_chunks
        
        batch_size = 5
        total_batches = (len(chunks_to_process) + batch_size - 1) // batch_size
        
        for i in range(0, len(chunks_to_process), batch_size):
            batch = chunks_to_process[i:i+batch_size]
            builder.build_graph_from_chunks(batch, batch_size=batch_size, skip_processed=False) # skip_processed False because we already filtered
            # Now manually save to temp path
            builder.save_graph(TEMP_GRAPH_PATH)
            logger.info(f"Saved progress to {TEMP_GRAPH_PATH} (Batch {i//batch_size + 1}/{total_batches})")
        
        logger.info("Graph extraction complete. Moving final graph to permanent storage...")
        shutil.copy2(TEMP_GRAPH_PATH, FINAL_GRAPH_PATH)
        logger.info(f"Graph successfully saved to {FINAL_GRAPH_PATH}")
        
    else:
        logger.info("No new chunks to process. Graph is up to date.")


if __name__ == "__main__":
    process_vault()
