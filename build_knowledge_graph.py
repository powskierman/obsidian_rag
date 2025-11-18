"""
Integration script to build knowledge graph from existing ChromaDB chunks
using Claude API and filesystem access
"""

import os
from pathlib import Path
from claude_graph_builder import ClaudeGraphBuilder, ClaudeGraphQuerier
from tqdm import tqdm
import chromadb
import re
from logging_config import setup_logging
import logging

# Set up logging
logger = setup_logging(level=logging.INFO, module_name="build_knowledge_graph")


def smart_chunk_document(content, max_size=1000, overlap=200):
    """
    Split content into overlapping chunks with smart boundaries
    Similar to ChromaDB chunking strategy for better quality
    
    Args:
        content: Text content to chunk
        max_size: Maximum chunk size in characters
        overlap: Number of characters to overlap between chunks
    
    Returns:
        List of chunk strings
    """
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
        
        # Find natural break points (in order of preference)
        break_points = [
            chunk.rfind('\n\n'),      # Paragraph break (best)
            chunk.rfind('\n## '),    # Subsection header
            chunk.rfind('\n# '),     # Section header
            chunk.rfind('. '),        # Sentence end
            chunk.rfind('! '),        # Exclamation
            chunk.rfind('? '),        # Question
            chunk.rfind('\n'),        # Line break
        ]
        
        # Use the best break point that's not too early
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


def load_chromadb_from_disk(chroma_db_path: str) -> list:
    """
    Load all chunks directly from ChromaDB on disk
    
    Args:
        chroma_db_path: Path to chroma_db directory
    """
    try:
        logger.info(f"Loading ChromaDB from: {chroma_db_path}")
        
        # Initialize ChromaDB client with persistent storage
        # Catch ChromaDB panics/errors gracefully (including Rust panics)
        try:
            client = chromadb.PersistentClient(path=chroma_db_path)
        except (Exception, BaseException) as init_error:
            # Catch all exceptions including PanicException from Rust
            error_type = type(init_error).__name__
            error_msg = str(init_error)
            
            # Check for panic-related errors
            if ("panic" in error_msg.lower() or 
                "PanicException" in error_type or
                "range start index" in error_msg.lower() or
                "pyo3_runtime" in error_type):
                logger.warning(f"ChromaDB database appears corrupted or incompatible")
                logger.warning(f"   Error type: {error_type}")
                logger.warning(f"   Error: {error_msg[:200]}")
                logger.warning(f"   Falling back to vault files...")
                return []
            # For other errors, still return empty list to trigger fallback
            logger.warning(f"ChromaDB initialization failed: {error_type}")
            logger.warning(f"   Error: {error_msg[:200]}")
            logger.warning(f"   Falling back to vault files...")
            return []
        
        # Get the collection (assuming default name 'obsidian_vault')
        # Try common collection names
        collection_names = ['obsidian_vault', 'documents', 'knowledge_base', 'vault']
        collection = None
        
        for name in collection_names:
            try:
                collection = client.get_collection(name=name)
                logger.info(f"Found collection: {name}")
                break
            except:
                continue
        
        if not collection:
            # List available collections
            collections = client.list_collections()
            if collections:
                logger.info(f"Available collections: {[c.name for c in collections]}")
                collection = collections[0]
                logger.info(f"Using first collection: {collection.name}")
            else:
                logger.error("No collections found in ChromaDB")
                return []
        
        # Get all documents from collection
        results = collection.get(include=['documents', 'metadatas'])
        
        chunks = []
        for i, (doc, meta) in enumerate(zip(results['documents'], results['metadatas'])):
            chunks.append({
                'text': doc,
                'metadata': {
                    **(meta or {}),
                    'chunk_id': results['ids'][i] if 'ids' in results else f'chunk_{i}'
                }
            })
        
        logger.info(f"Loaded {len(chunks)} chunks from ChromaDB")
        return chunks
        
    except Exception as e:
        logger.error(f"Error loading ChromaDB: {e}")
        logger.error(f"Make sure ChromaDB exists at: {chroma_db_path}")
        return []


def load_vault_files_directly(vault_path: str, max_files: int = None) -> list:
    """
    Load markdown files directly from Obsidian vault
    
    Args:
        vault_path: Path to Obsidian vault
        max_files: Optional limit on number of files to process
    """
    try:
        logger.info(f"Loading vault files from: {vault_path}")
        vault_dir = Path(vault_path)
        
        if not vault_dir.exists():
            logger.error(f"Vault path does not exist: {vault_path}")
            return []
        
        # Find all markdown files
        md_files = list(vault_dir.rglob('*.md'))
        
        if max_files:
            md_files = md_files[:max_files]
        
        logger.info(f"Found {len(md_files)} markdown files")
        
        chunks = []
        for md_file in tqdm(md_files, desc="Reading files"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Remove frontmatter
                content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)
                
                # Skip if too short
                if len(content.strip()) < 100:
                    continue
                
                # Create chunks from file with improved chunking
                # Use smart chunking similar to ChromaDB for better quality
                chunks_from_file = smart_chunk_document(content, max_size=1000, overlap=200)
                
                for i, chunk_text in enumerate(chunks_from_file):
                    chunks.append({
                        'text': chunk_text,
                        'metadata': {
                            'filename': md_file.name,
                            'filepath': str(md_file.relative_to(vault_dir)),
                            'chunk_id': f"{md_file.stem}_{i}",
                            'total_chunks': len(chunks_from_file)
                        }
                    })
                    
            except Exception as e:
                logger.error(f"Error reading {md_file}: {e}")
                continue
        
        logger.info(f"Created {len(chunks)} chunks from vault files")
        return chunks
        
    except Exception as e:
        logger.error(f"Error loading vault files: {e}")
        return []


def get_chunks_from_filesystem(
    chroma_db_path: str = None,
    vault_path: str = None,
    test_mode: bool = True,
    n_test_chunks: int = 50
) -> list:
    """
    Get chunks from filesystem - tries ChromaDB first, then vault files
    
    Args:
        chroma_db_path: Path to ChromaDB directory
        vault_path: Path to Obsidian vault
        test_mode: If True, limit to n_test_chunks
        n_test_chunks: Number of chunks for testing
    """
    chunks = []
    
    # Try ChromaDB first if path provided
    if chroma_db_path:
        try:
            chunks = load_chromadb_from_disk(chroma_db_path)
        except (Exception, BaseException) as e:
            # Catch all exceptions including Rust PanicException
            error_type = type(e).__name__
            error_msg = str(e)
            logger.warning(f"ChromaDB loading failed: {error_type}")
            logger.warning(f"   Error: {error_msg[:200]}")
            logger.warning(f"   Falling back to vault files...")
            chunks = []
    
    # Fallback to vault files if no ChromaDB chunks
    if not chunks and vault_path:
        logger.info(f"Loading chunks directly from vault files...")
        max_files = 10 if test_mode else None
        chunks = load_vault_files_directly(vault_path, max_files)
    
    # Limit for test mode
    if test_mode and len(chunks) > n_test_chunks:
        logger.info(f"Test mode: limiting to {n_test_chunks} chunks")
        chunks = chunks[:n_test_chunks]
    
    return chunks


def build_graph_from_vault(
    api_key: str,
    test_mode: bool = True,
    n_test_chunks: int = 50,
    chroma_db_path: str = None,
    vault_path: str = None
):
    """
    Main function to build knowledge graph from your vault
    
    Args:
        api_key: Anthropic API key
        test_mode: If True, only process n_test_chunks for testing
        n_test_chunks: Number of chunks to process in test mode
        chroma_db_path: Path to ChromaDB directory (optional)
        vault_path: Path to Obsidian vault (optional)
    """
    
    logger.info("=" * 70)
    logger.info("Claude-Powered Knowledge Graph Builder for Obsidian Vault")
    logger.info("=" * 70)
    
    # Initialize builder
    builder = ClaudeGraphBuilder(api_key=api_key)
    
    # Fetch chunks from filesystem
    if test_mode:
        logger.info(f"\nTEST MODE: Processing up to {n_test_chunks} chunks...")
    else:
        logger.info("\nPRODUCTION MODE: Processing ALL chunks (~7,113)...")
        logger.warning("This will take several hours and cost ~$20-30 in API usage")
        confirm = input("Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            logger.info("Aborted.")
            return
    
    chunks = get_chunks_from_filesystem(
        chroma_db_path=chroma_db_path,
        vault_path=vault_path,
        test_mode=test_mode,
        n_test_chunks=n_test_chunks
    )
    
    if not chunks:
        logger.error("No chunks found.")
        logger.info("\nPlease provide either:")
        logger.info("  - ChromaDB path: Path to your chroma_db directory")
        logger.info("  - Vault path: Path to your Obsidian vault")
        return
    
    logger.info(f"Found {len(chunks)} chunks to process")
    
    # Build graph
    logger.info("\nBuilding knowledge graph...")
    logger.info("This uses Claude to extract entities and relationships from each chunk.")
    logger.info("Progress will be saved every 10 chunks.\n")
    
    builder.build_graph_from_chunks(chunks, batch_size=10)
    
    # Save final graph
    from pathlib import Path
    graph_data_dir = Path("graph_data")
    graph_data_dir.mkdir(exist_ok=True)
    output_file = str(graph_data_dir / ("knowledge_graph_test.pkl" if test_mode else "knowledge_graph_full.pkl"))
    builder.save_graph(output_file)
    
    # Export to JSON for visualization
    json_file = str(graph_data_dir / ("knowledge_graph_test.json" if test_mode else "knowledge_graph_full.json"))
    builder.export_graph_json(json_file)
    
    # Print statistics
    logger.info("\n" + "=" * 70)
    logger.info("GRAPH STATISTICS")
    logger.info("=" * 70)
    logger.info(f"Total Chunks Processed: {builder.extraction_stats['chunks_processed']}")
    logger.info(f"Total Entities Extracted: {builder.extraction_stats['entities_extracted']}")
    logger.info(f"Total Relationships Extracted: {builder.extraction_stats['relationships_extracted']}")
    logger.info(f"Errors: {builder.extraction_stats['errors']}")
    logger.info(f"Unique Entities (Nodes): {builder.graph.number_of_nodes()}")
    logger.info(f"Unique Relationships (Edges): {builder.graph.number_of_edges()}")
    
    # Show top entities
    querier = ClaudeGraphQuerier(builder, api_key)
    stats = querier.get_graph_stats()
    
    logger.info("\nTOP 10 MOST CONNECTED ENTITIES:")
    for entity in stats['top_entities']:
        logger.info(f"  • {entity['entity']}: {entity['connections']} connections")
    
    logger.info(f"\nGraph saved to: {output_file}")
    logger.info(f"JSON export saved to: {json_file}")
    
    return builder


def test_graph_queries(graph_file: str, api_key: str):
    """
    Test querying the built graph
    """
    logger.info("\n" + "=" * 70)
    logger.info("TESTING GRAPH QUERIES")
    logger.info("=" * 70)
    
    # Load graph
    builder = ClaudeGraphBuilder(api_key)
    builder.load_graph(graph_file)
    
    querier = ClaudeGraphQuerier(builder, api_key)
    
    # Test queries
    test_queries = [
        "What treatments are mentioned in my notes?",
        "How are my technical projects related to my medical journey?",
        "What entities are most central in my knowledge base?",
    ]
    
    for query in test_queries:
        logger.info(f"\nQuery: {query}")
        logger.info("-" * 70)
        answer = querier.query_with_claude(query)
        logger.info(answer)
        logger.info("")


def resume_graph_building(
    api_key: str,
    existing_graph_file: str = None,
    chroma_db_path: str = None,
    vault_path: str = None,
    skip_chromadb: bool = False
):
    """
    Resume building graph from where it left off
    
    Args:
        api_key: Anthropic API key
        existing_graph_file: Path to existing graph file to resume from (defaults to graph_data/knowledge_graph_full.pkl)
        chroma_db_path: Path to ChromaDB directory
        vault_path: Path to Obsidian vault
    """
    logger.info("=" * 70)
    logger.info("RESUME GRAPH BUILDING")
    logger.info("=" * 70)
    
    # Set default graph file if not provided
    if existing_graph_file is None:
        graph_data_dir = Path("graph_data")
        existing_graph_file = str(graph_data_dir / "knowledge_graph_full.pkl")
    elif not Path(existing_graph_file).is_absolute() and not existing_graph_file.startswith("graph_data/"):
        # Try graph_data directory first
        graph_data_path = Path("graph_data") / Path(existing_graph_file).name
        if graph_data_path.exists():
            existing_graph_file = str(graph_data_path)
    
    # Load existing graph
    builder = ClaudeGraphBuilder(api_key=api_key)
    
    if not Path(existing_graph_file).exists():
        logger.error(f"Graph file not found: {existing_graph_file}")
        return
    
    logger.info(f"\nLoading existing graph from: {existing_graph_file}")
    builder.load_graph(existing_graph_file)
    
    chunks_processed = builder.extraction_stats.get('chunks_processed', 0)
    logger.info(f"Loaded graph with {builder.graph.number_of_nodes()} entities and {builder.graph.number_of_edges()} relationships")
    logger.info(f"Already processed: {chunks_processed} chunks")
    
    # Get all chunks (will fallback to vault files if ChromaDB fails)
    logger.info(f"\nLoading chunks...")
    
    # Skip ChromaDB if explicitly requested or if we know it's corrupted
    if skip_chromadb:
        logger.info(f"Skipping ChromaDB (using vault files directly)")
        chroma_db_path = None
    
    try:
        chunks = get_chunks_from_filesystem(
            chroma_db_path=chroma_db_path if not skip_chromadb else None,
            vault_path=vault_path,
            test_mode=False,
            n_test_chunks=None
        )
    except Exception as e:
        logger.warning(f"Error loading chunks: {e}")
        logger.warning(f"   Trying vault files directly...")
        if vault_path:
            chunks = load_vault_files_directly(vault_path, max_files=None)
        else:
            chunks = []
    
    if not chunks:
        logger.error("No chunks found. Please provide either chroma_db_path or vault_path.")
        return
    
    total_chunks = len(chunks)
    remaining = total_chunks - chunks_processed
    
    if remaining <= 0:
        logger.info("All chunks already processed!")
        return
    
    logger.info(f"\nRemaining chunks: {remaining:,} out of {total_chunks:,}")
    logger.info(f"Estimated cost: ~${remaining * 0.0014:.2f} (Haiku 4.5)")
    logger.info(f"Estimated time: ~{remaining // 60} minutes")
    
    confirm = input("\nContinue? (yes/no): ")
    if confirm.lower() != 'yes':
        logger.info("Aborted.")
        return
    
    # Skip already processed chunks
    remaining_chunks = chunks[chunks_processed:]
    logger.info(f"\nResuming graph building from chunk {chunks_processed + 1}...")
    logger.info("Progress will be saved every 10 chunks.\n")
    
    # Process remaining chunks with offset
    total = len(remaining_chunks)
    batch_size = 10
    
    for i, chunk in enumerate(remaining_chunks):
        current_chunk_num = chunks_processed + i + 1
        logger.info(f"Processing chunk {current_chunk_num}/{len(chunks)}...")
        
        graph_data = builder.extract_graph_from_chunk(
            chunk['text'],
            chunk['metadata']
        )
        
        builder.add_to_graph(graph_data)
        
        # Save progress every batch_size chunks
        if (i + 1) % batch_size == 0:
            checkpoint_path = Path("graph_data") / f"graph_checkpoint_{current_chunk_num}.pkl"
            builder.save_graph(str(checkpoint_path))
            logger.info(f"Checkpoint saved at {current_chunk_num} chunks")
    
    logger.info("\nGraph building complete!")
    
    # Save final graph
    builder.save_graph(existing_graph_file)
    
    # Export to JSON
    json_file = existing_graph_file.replace('.pkl', '.json')
    builder.export_graph_json(json_file)
    
    # Print final statistics
    logger.info("\n" + "=" * 70)
    logger.info("FINAL GRAPH STATISTICS")
    logger.info("=" * 70)
    logger.info(f"Total Chunks Processed: {builder.extraction_stats['chunks_processed']}")
    logger.info(f"Total Entities Extracted: {builder.extraction_stats['entities_extracted']}")
    logger.info(f"Total Relationships Extracted: {builder.extraction_stats['relationships_extracted']}")
    logger.info(f"Errors: {builder.extraction_stats['errors']}")
    logger.info(f"Unique Entities (Nodes): {builder.graph.number_of_nodes()}")
    logger.info(f"Unique Relationships (Edges): {builder.graph.number_of_edges()}")
    
    # Show top entities
    querier = ClaudeGraphQuerier(builder, api_key)
    stats = querier.get_graph_stats()
    
    logger.info("\nTOP 10 MOST CONNECTED ENTITIES:")
    for entity in stats['top_entities'][:10]:
        logger.info(f"  • {entity['entity']}: {entity['connections']} connections")
    
    logger.info(f"\nGraph saved to: {existing_graph_file}")
    logger.info(f"JSON export saved to: {json_file}")


def interactive_graph_query(graph_file: str, api_key: str):
    """
    Interactive query interface for the knowledge graph
    """
    logger.info("\n" + "=" * 70)
    logger.info("INTERACTIVE GRAPH QUERY")
    logger.info("=" * 70)
    logger.info("Commands:")
    logger.info("  - Type a question to query the graph")
    logger.info("  - Type 'stats' to see graph statistics")
    logger.info("  - Type 'entity <name>' to explore an entity")
    logger.info("  - Type 'path <entity1> to <entity2>' to find connections")
    logger.info("  - Type 'quit' to exit")
    logger.info("=" * 70)
    
    # Load graph
    builder = ClaudeGraphBuilder(api_key)
    builder.load_graph(graph_file)
    querier = ClaudeGraphQuerier(builder, api_key)
    
    while True:
        user_input = input("\n🔍 Your query: ").strip()
        
        if not user_input:
            continue
        
        if user_input.lower() == 'quit':
            logger.info("Goodbye!")
            break
        
        if user_input.lower() == 'stats':
            stats = querier.get_graph_stats()
            logger.info(f"\nGraph Statistics:")
            logger.info(f"  Nodes: {stats['total_nodes']}")
            logger.info(f"  Edges: {stats['total_edges']}")
            logger.info(f"  Density: {stats['density']:.4f}")
            logger.info(f"  Connected: {stats['is_connected']}")
            logger.info(f"\nTop Entities:")
            for entity in stats['top_entities'][:5]:
                logger.info(f"  • {entity['entity']}: {entity['connections']} connections")
            continue
        
        if user_input.lower().startswith('entity '):
            entity_name = user_input[7:].strip().strip('"\'')
            neighborhood = querier.get_entity_neighborhood(entity_name)
            if not neighborhood.get('found', True):
                # Try to suggest similar entities
                entity_lower = entity_name.lower()
                suggestions = [n for n in querier.graph.nodes() if entity_lower in n.lower() or n.lower() in entity_lower][:5]
                logger.warning(f"Entity '{entity_name}' not found in graph")
                if suggestions:
                    logger.info(f"   Did you mean one of these?")
                    for sug in suggestions:
                        logger.info(f"     • {sug}")
            else:
                logger.info(f"\nEntity: {neighborhood['entity']}")
                logger.info(f"   Type: {neighborhood['properties'].get('entity_type', 'Unknown')}")
                
                if neighborhood['outgoing']:
                    logger.info(f"\n   Outgoing Relationships:")
                    for rel in neighborhood['outgoing'][:10]:
                        logger.info(f"     → {rel['relationship']} → {rel['target']}")
                
                if neighborhood['incoming']:
                    logger.info(f"\n   Incoming Relationships:")
                    for rel in neighborhood['incoming'][:10]:
                        logger.info(f"     ← {rel['relationship']} ← {rel['source']}")
            continue
        
        if 'to' in user_input.lower() and user_input.lower().startswith('path '):
            # Parse path query
            parts = user_input[5:].split(' to ')
            if len(parts) == 2:
                source = parts[0].strip()
                target = parts[1].strip()
                paths = querier.find_paths(source, target)
                if paths:
                    logger.info(f"\nFound {len(paths)} path(s):")
                    for i, path in enumerate(paths[:5], 1):
                        logger.info(f"   {i}. {' → '.join(path)}")
                else:
                    logger.warning(f"No path found between '{source}' and '{target}'")
                continue
        
        # Regular query
        logger.info("\nThinking...")
        answer = querier.query_with_claude(user_input)
        logger.info(f"\nAnswer:\n{answer}")


if __name__ == "__main__":
    import sys
    
    # Get API key from environment or prompt
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = input("Enter your Anthropic API key: ").strip()
        if not api_key:
            logger.error("API key required")
            sys.exit(1)
    
    # Get paths
    logger.info("\n" + "=" * 70)
    logger.info("CONFIGURATION")
    logger.info("=" * 70)
    
    # Default paths (with environment variable fallbacks)
    default_chroma_path = os.getenv('CHROMA_DB_PATH', "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/chroma_db")
    default_vault_path = os.getenv('OBSIDIAN_VAULT_PATH', "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel")
    
    logger.info(f"\nDefault ChromaDB path: {default_chroma_path}")
    logger.info(f"Default Vault path: {default_vault_path}")
    
    chroma_path = input("\nChromaDB path (or press Enter for default): ").strip()
    if not chroma_path:
        chroma_path = default_chroma_path
    
    vault_path = input("Vault path (or press Enter for default): ").strip()
    if not vault_path:
        vault_path = default_vault_path
    
    # Verify paths exist
    if not Path(chroma_path).exists() and not Path(vault_path).exists():
        logger.error("\nNeither path exists. Please check your paths.")
        logger.error(f"   ChromaDB: {chroma_path}")
        logger.error(f"   Vault: {vault_path}")
        sys.exit(1)
    
    logger.info("\nPaths configured")
    if Path(chroma_path).exists():
        logger.info(f"   Using ChromaDB: {chroma_path}")
    if Path(vault_path).exists():
        logger.info(f"   Using Vault: {vault_path}")
    
    logger.info("\nChoose an option:")
    logger.info("1. Build graph (TEST MODE - 50 chunks)")
    logger.info("2. Build graph (FULL - all chunks)")
    logger.info("3. Resume building (continue from existing graph)")
    logger.info("4. Test queries on existing graph")
    logger.info("5. Interactive query mode")
    
    choice = input("\nYour choice (1-5): ").strip()
    
    if choice == "1":
        build_graph_from_vault(
            api_key, 
            test_mode=True, 
            n_test_chunks=50,
            chroma_db_path=chroma_path if Path(chroma_path).exists() else None,
            vault_path=vault_path if Path(vault_path).exists() else None
        )
    
    elif choice == "2":
        build_graph_from_vault(
            api_key, 
            test_mode=False,
            chroma_db_path=chroma_path if Path(chroma_path).exists() else None,
            vault_path=vault_path if Path(vault_path).exists() else None
        )
    
    elif choice == "3":
        graph_file = input("Enter graph file path (or press Enter for 'graph_data/knowledge_graph_full.pkl'): ").strip()
        if not graph_file:
            graph_file = None  # Will use default in resume_graph_building
        resume_graph_building(
            api_key,
            existing_graph_file=graph_file,
            chroma_db_path=chroma_path if Path(chroma_path).exists() else None,
            vault_path=vault_path if Path(vault_path).exists() else None
        )
    
    elif choice == "4":
        graph_file = input("Enter graph file path (or press Enter for 'graph_data/knowledge_graph_test.pkl'): ").strip()
        if not graph_file:
            graph_file = str(Path("graph_data") / "knowledge_graph_test.pkl")
        elif not Path(graph_file).is_absolute() and not graph_file.startswith("graph_data/"):
            # Try graph_data directory
            graph_data_path = Path("graph_data") / Path(graph_file).name
            if graph_data_path.exists():
                graph_file = str(graph_data_path)
        test_graph_queries(graph_file, api_key)
    
    elif choice == "5":
        graph_file = input("Enter graph file path (or press Enter for 'graph_data/knowledge_graph_test.pkl'): ").strip()
        if not graph_file:
            graph_file = str(Path("graph_data") / "knowledge_graph_test.pkl")
        elif not Path(graph_file).is_absolute() and not graph_file.startswith("graph_data/"):
            # Try graph_data directory
            graph_data_path = Path("graph_data") / Path(graph_file).name
            if graph_data_path.exists():
                graph_file = str(graph_data_path)
        interactive_graph_query(graph_file, api_key)
    
    else:
        logger.error("Invalid choice")
