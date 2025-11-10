#!/usr/bin/env python3
"""
Retry failed chunks from knowledge graph building

This script:
1. Loads your existing graph
2. Identifies chunks that failed during initial processing
3. Retries them with improved error handling
4. Merges successful results back into the graph
"""

import os
import sys
import logging
from pathlib import Path
from claude_graph_builder import ClaudeGraphBuilder
from build_knowledge_graph import get_chunks_from_filesystem, load_chromadb_from_disk, load_vault_files_directly

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_latest_checkpoint(graph_data_dir: Path = None) -> str:
    """
    Find the latest checkpoint file, or return None if none exists
    
    Returns:
        Path to latest checkpoint file, or None
    """
    if graph_data_dir is None:
        graph_data_dir = Path("graph_data")
    
    if not graph_data_dir.exists():
        return None
    
    # Find all checkpoint files
    checkpoints = list(graph_data_dir.glob("graph_checkpoint_*.pkl"))
    
    if not checkpoints:
        return None
    
    # Sort numerically by extracting the chunk number
    def get_chunk_number(checkpoint_path):
        try:
            # Extract number from filename like "graph_checkpoint_3426.pkl"
            name = checkpoint_path.stem  # "graph_checkpoint_3426"
            number_str = name.replace("graph_checkpoint_", "")
            return int(number_str)
        except (ValueError, AttributeError):
            return 0
    
    # Sort by chunk number (numerically, not alphabetically)
    checkpoints_sorted = sorted(checkpoints, key=get_chunk_number)
    
    # Prefer most recently modified checkpoint (most reliable indicator of latest work)
    # This handles the case where an older run had higher chunk numbers
    checkpoints_by_time = sorted(checkpoints, key=lambda p: p.stat().st_mtime, reverse=True)
    latest_by_time = checkpoints_by_time[0]
    latest_by_number = checkpoints_sorted[-1]
    
    # Always prefer the most recently modified checkpoint
    # This is the most reliable way to find where you left off
    return str(latest_by_time)


def retry_failed_chunks(
    api_key: str,
    existing_graph_file: str = None,
    chroma_db_path: str = None,
    vault_path: str = None,
    use_sonnet: bool = False,
    max_retries: int = 3
):
    """
    Retry chunks that failed during graph building
    
    Args:
        api_key: Anthropic API key
        existing_graph_file: Path to existing graph
        chroma_db_path: Path to ChromaDB (optional)
        vault_path: Path to vault (optional)
        use_sonnet: Use Claude Sonnet for retries (more reliable, more expensive)
        max_retries: Max retry attempts per chunk
    """
    logger.info("=" * 70)
    logger.info("RETRY FAILED CHUNKS - Improved Error Handling")
    logger.info("=" * 70)
    
    # Auto-detect graph file if not specified
    if existing_graph_file is None:
        graph_data_dir = Path("graph_data")
        
        # First, try to find latest checkpoint
        latest_checkpoint = find_latest_checkpoint(graph_data_dir)
        main_graph = graph_data_dir / "knowledge_graph_full.pkl"
        
        if latest_checkpoint and Path(latest_checkpoint).exists():
            # Check if checkpoint is newer than main graph
            checkpoint_time = Path(latest_checkpoint).stat().st_mtime
            if main_graph.exists():
                main_graph_time = main_graph.stat().st_mtime
                if checkpoint_time > main_graph_time:
                    existing_graph_file = latest_checkpoint
                    logger.info(f"Found newer checkpoint: {latest_checkpoint}")
                else:
                    existing_graph_file = str(main_graph)
                    logger.info(f"Using main graph file: {existing_graph_file}")
            else:
                existing_graph_file = latest_checkpoint
                logger.info(f"Found checkpoint: {latest_checkpoint}")
        elif main_graph.exists():
            existing_graph_file = str(main_graph)
            logger.info(f"Using main graph file: {existing_graph_file}")
        else:
            logger.error("No graph file found!")
            logger.error(f"Looking for:")
            logger.error(f"  - {graph_data_dir / 'knowledge_graph_full.pkl'}")
            logger.error(f"  - {graph_data_dir / 'graph_checkpoint_*.pkl'}")
            return
    
    # Initialize builder with retry support
    builder = ClaudeGraphBuilder(
        api_key=api_key,
        model="claude-sonnet-4-5-20250929" if use_sonnet else "claude-haiku-4-5",
        max_retries=max_retries
    )
    
    # Load existing graph
    graph_path = Path(existing_graph_file)
    if not graph_path.exists():
        logger.error(f"Graph file not found: {existing_graph_file}")
        return
    
    logger.info(f"Loading existing graph from: {existing_graph_file}")
    builder.load_graph(str(graph_path))
    
    initial_nodes = builder.graph.number_of_nodes()
    initial_edges = builder.graph.number_of_edges()
    initial_processed = builder.extraction_stats.get('chunks_processed', 0)
    initial_errors = builder.extraction_stats.get('errors', 0)
    processed_chunks_count = len(builder.processed_chunks)
    
    logger.info(f"Loaded graph:")
    logger.info(f"  Nodes: {initial_nodes:,}")
    logger.info(f"  Edges: {initial_edges:,}")
    logger.info(f"  Previously processed: {initial_processed:,} chunks (from stats)")
    logger.info(f"  Processed chunk hashes: {processed_chunks_count:,} (from processed_chunks set)")
    logger.info(f"  Previous errors: {initial_errors:,}")
    
    # Warn if there's a mismatch between stats and processed_chunks set
    if initial_processed > 0 and processed_chunks_count == 0:
        logger.warning(f"Stats show {initial_processed:,} chunks processed, but processed_chunks set is empty!")
        logger.warning(f"This graph file might be from an older version that didn't save processed_chunks.")
        logger.warning(f"The script will use file-based detection instead.")
    elif initial_processed > processed_chunks_count * 1.5:
        logger.warning(f"Stats show {initial_processed:,} chunks processed, but only {processed_chunks_count:,} hashes saved.")
        logger.warning(f"This might indicate some checkpoints didn't save processed_chunks properly.")
        logger.warning(f"The script will use multiple detection methods to identify processed chunks.")
    
    # Get all chunks
    logger.info("Loading all chunks...")
    if chroma_db_path:
        try:
            chunks = load_chromadb_from_disk(chroma_db_path)
        except Exception as e:
            logger.warning(f"ChromaDB failed: {e}")
            chunks = []
    else:
        chunks = []
    
    if not chunks and vault_path:
        default_vault = os.getenv('OBSIDIAN_VAULT_PATH', "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel")
        if Path(default_vault).exists():
            vault_path = default_vault
    
    if not chunks and vault_path:
        logger.info(f"Loading from vault: {vault_path}")
        chunks = load_vault_files_directly(vault_path, max_files=None)
    
    if not chunks:
        logger.error("No chunks found. Please provide chroma_db_path or vault_path.")
        return
    
    total_chunks = len(chunks)
    logger.info(f"Found {total_chunks:,} total chunks")
    
    # Identify chunks that likely failed or weren't processed
    # Strategy: Check if chunk's content is already represented in the graph
    chunks_to_retry = []
    chunks_skipped = 0
    
    logger.info("Analyzing chunks to identify which need retry...")
    
    # Build a comprehensive set of source files and chunk identifiers already in the graph
    graph_sources = set()
    graph_chunk_ids = set()  # Track chunk IDs that are in the graph
    graph_file_chunk_counts = {}  # Count chunks per file in graph
    
    for node, data in builder.graph.nodes(data=True):
        sources = data.get('sources', [])
        if isinstance(sources, list):
            for source in sources:
                if isinstance(source, dict):
                    filename = source.get('filename', '')
                    chunk_id = source.get('chunk_id', '')
                    graph_sources.add(filename)
                    if filename and chunk_id:
                        # Create a file:chunk_id identifier
                        file_chunk_id = f"{filename}::{chunk_id}"
                        graph_chunk_ids.add(file_chunk_id)
                        # Count chunks per file
                        graph_file_chunk_counts[filename] = graph_file_chunk_counts.get(filename, 0) + 1
                else:
                    graph_sources.add(str(source))
    
    logger.info(f"Found {len(graph_sources)} unique source files in existing graph")
    logger.info(f"Found {len(graph_chunk_ids)} chunk identifiers in graph")
    logger.info(f"Found {len(builder.processed_chunks)} processed chunk hashes")
    
    # Also check processed_chunks count from stats
    stats_processed = builder.extraction_stats.get('chunks_processed', 0)
    logger.info(f"Stats show {stats_processed:,} chunks processed")
    
    # Build a mapping of filename -> set of chunk hashes for that file
    # This helps us identify if a file has been substantially processed
    file_to_hashes = {}
    for chunk in chunks:
        filename = chunk['metadata'].get('filename', '')
        if filename:
            if filename not in file_to_hashes:
                file_to_hashes[filename] = []
            file_to_hashes[filename].append(builder._get_chunk_hash(chunk['text'], chunk['metadata']))
    
    for i, chunk in enumerate(chunks):
        if (i + 1) % 100 == 0:
            logger.debug(f"Analyzed {i+1}/{total_chunks} chunks...")
        
        chunk_filename = chunk['metadata'].get('filename', '')
        chunk_id = chunk['metadata'].get('chunk_id', '')
        chunk_hash = builder._get_chunk_hash(chunk['text'], chunk['metadata'])
        
        # Method 1: Check if exact hash is in processed_chunks
        if chunk_hash in builder.processed_chunks:
            chunks_skipped += 1
            continue
        
        # Method 2: Check if this file:chunk_id combination is in graph
        if chunk_filename and chunk_id:
            file_chunk_id = f"{chunk_filename}::{chunk_id}"
            if file_chunk_id in graph_chunk_ids:
                chunks_skipped += 1
                continue
        
        # Method 3: If file is in graph and has substantial representation,
        # check if this specific chunk's content appears to be processed
        # by looking for entities that might have been extracted from it
        if chunk_filename in graph_sources:
            # File is in graph - check if it's well-represented
            file_chunk_count_in_graph = graph_file_chunk_counts.get(chunk_filename, 0)
            file_total_chunks = len([c for c in chunks if c['metadata'].get('filename') == chunk_filename])
            
            # If file has substantial representation (e.g., >50% of chunks processed),
            # and this chunk's hash pattern suggests it might be processed,
            # be more conservative and skip it
            if file_total_chunks > 0:
                representation_ratio = file_chunk_count_in_graph / file_total_chunks
                # If >70% of file is represented, and this chunk's hash suggests it might be processed,
                # skip it (it was likely processed but hash format changed slightly)
                if representation_ratio > 0.7:
                    # Additional check: see if any similar hashes exist for this file
                    file_hashes = file_to_hashes.get(chunk_filename, [])
                    # Check if there are many processed hashes for this file
                    processed_for_file = sum(1 for h in file_hashes if h in builder.processed_chunks)
                    if processed_for_file / len(file_hashes) > 0.7:
                        chunks_skipped += 1
                        continue
        
        # If we get here, chunk needs processing
        chunks_to_retry.append(chunk)
    
    logger.info("Analysis complete!")
    logger.info(f"Chunks to retry: {len(chunks_to_retry):,}")
    logger.info(f"Chunks skipped (already processed): {chunks_skipped:,}")
    
    if not chunks_to_retry:
        logger.info("All chunks appear to have been processed!")
        logger.info("If you want to retry failed chunks, they should be in graph_data/failed_chunks.pkl")
        
        # Check for failed_chunks.pkl
        failed_file = Path("graph_data") / "failed_chunks.pkl"
        if failed_file.exists():
            logger.info(f"Found failed chunks file: {failed_file}")
            retry_file = input("Retry chunks from failed_chunks.pkl? (yes/no): ").strip().lower()
            if retry_file == 'yes':
                builder.retry_failed_chunks(str(failed_file), use_sonnet=use_sonnet)
        return
    
    logger.info("Summary:")
    logger.info(f"  Total chunks found: {total_chunks:,}")
    logger.info(f"  Chunks to retry: {len(chunks_to_retry):,}")
    logger.info(f"  Chunks already processed: {chunks_skipped:,}")
    
    if len(chunks_to_retry) == total_chunks:
        logger.warning("Note: All chunks will be processed.")
        logger.warning("This is normal if:")
        logger.warning("  - Original graph was built from ChromaDB (different chunk format)")
        logger.warning("  - You're now using vault files (different chunk boundaries)")
        logger.warning("  - The graph will merge duplicate entities automatically")
    
    if use_sonnet:
        cost_estimate = len(chunks_to_retry) * 0.003  # Sonnet is ~$0.003 per chunk
        logger.info(f"Estimated cost (Sonnet): ~${cost_estimate:.2f}")
    else:
        cost_estimate = len(chunks_to_retry) * 0.0014  # Haiku is ~$0.0014 per chunk
        logger.info(f"Estimated cost (Haiku): ~${cost_estimate:.2f}")
    
    confirm = input("\nContinue? (yes/no): ").strip().lower()
    if confirm != 'yes':
        logger.info("Aborted.")
        return
    
    # Process chunks with improved error handling
    logger.info(f"Retrying {len(chunks_to_retry)} chunks with improved error handling...")
    builder.build_graph_from_chunks(chunks_to_retry, batch_size=10, skip_processed=False)
    
    # Save updated graph
    logger.info("Saving updated graph...")
    builder.save_graph(str(graph_path))
    
    # Export JSON
    json_file = str(graph_path).replace('.pkl', '.json')
    builder.export_graph_json(json_file)
    
    # Log statistics
    logger.info("=" * 70)
    logger.info("UPDATED GRAPH STATISTICS")
    logger.info("=" * 70)
    logger.info(f"Previous Nodes: {initial_nodes:,}")
    logger.info(f"Current Nodes: {builder.graph.number_of_nodes():,}")
    logger.info(f"Added: {builder.graph.number_of_nodes() - initial_nodes:,} nodes")
    logger.info(f"Previous Edges: {initial_edges:,}")
    logger.info(f"Current Edges: {builder.graph.number_of_edges():,}")
    logger.info(f"Added: {builder.graph.number_of_edges() - initial_edges:,} edges")
    logger.info(f"Total Chunks Processed: {builder.extraction_stats['chunks_processed']:,}")
    logger.info(f"Total Errors: {builder.extraction_stats['errors']:,}")
    logger.info(f"Retries: {builder.extraction_stats['retries']:,}")
    logger.info(f"Successful Retries: {builder.extraction_stats['successful_retries']:,}")
    
    if builder.failed_chunks:
        logger.warning(f"{len(builder.failed_chunks)} chunks still failed")
        logger.warning(f"They are saved in graph_data/failed_chunks.pkl")
        logger.warning(f"You can retry them again with use_sonnet=True for better results")
    
    logger.info(f"Graph updated: {graph_path}")
    logger.info(f"JSON export: {json_file}")


if __name__ == "__main__":
    import sys
    
    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = input("Enter your Anthropic API key: ").strip()
        if not api_key:
            logger.error("API key required")
            sys.exit(1)
    
    # Default paths (with environment variable fallbacks)
    default_chroma = os.getenv('CHROMA_DB_PATH', "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/chroma_db")
    default_vault = os.getenv('OBSIDIAN_VAULT_PATH', "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel")
    
    logger.info("=" * 70)
    logger.info("CONFIGURATION")
    logger.info("=" * 70)
    
    chroma_path = input(f"\nChromaDB path (Enter for default: {default_chroma}): ").strip()
    if not chroma_path:
        chroma_path = default_chroma if Path(default_chroma).exists() else None
    
    vault_path = input(f"Vault path (Enter for default: {default_vault}): ").strip()
    if not vault_path:
        vault_path = default_vault if Path(default_vault).exists() else None
    
    # Show available checkpoints
    graph_data_dir = Path("graph_data")
    checkpoints = list(graph_data_dir.glob("graph_checkpoint_*.pkl"))
    if checkpoints:
        # Use the same logic as find_latest_checkpoint() - sort by modification time
        checkpoints_by_time = sorted(checkpoints, key=lambda p: p.stat().st_mtime, reverse=True)
        latest_checkpoint = checkpoints_by_time[0]
        chunk_num = latest_checkpoint.stem.replace("graph_checkpoint_", "")
        from datetime import datetime
        mtime = datetime.fromtimestamp(latest_checkpoint.stat().st_mtime)
        logger.info(f"Latest checkpoint found: {latest_checkpoint.name} (chunk {chunk_num})")
        logger.info(f"  Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"  This will be used if you press Enter")
    
    # Auto-detect graph file (latest checkpoint or main graph)
    graph_file_input = input("\nGraph file (Enter to auto-detect latest checkpoint): ").strip()
    graph_file = graph_file_input if graph_file_input else None
    
    use_sonnet = input("\nUse Claude Sonnet for better reliability? (yes/no, default: no): ").strip().lower() == 'yes'
    
    retry_failed_chunks(
        api_key=api_key,
        existing_graph_file=graph_file,
        chroma_db_path=chroma_path,
        vault_path=vault_path,
        use_sonnet=use_sonnet,
        max_retries=3
    )

