"""
Integration script to build knowledge graph from existing ChromaDB chunks
using Claude API and filesystem access
"""

import os
from pathlib import Path
from claude_graph_builder import ClaudeGraphBuilder, ClaudeGraphQuerier
import json
from tqdm import tqdm
import chromadb
import re


def load_chromadb_from_disk(chroma_db_path: str) -> list:
    """
    Load all chunks directly from ChromaDB on disk
    
    Args:
        chroma_db_path: Path to chroma_db directory
    """
    try:
        print(f"Loading ChromaDB from: {chroma_db_path}")
        
        # Initialize ChromaDB client with persistent storage
        client = chromadb.PersistentClient(path=chroma_db_path)
        
        # Get the collection (assuming default name 'obsidian_vault')
        # Try common collection names
        collection_names = ['obsidian_vault', 'documents', 'knowledge_base', 'vault']
        collection = None
        
        for name in collection_names:
            try:
                collection = client.get_collection(name=name)
                print(f"✅ Found collection: {name}")
                break
            except:
                continue
        
        if not collection:
            # List available collections
            collections = client.list_collections()
            if collections:
                print(f"Available collections: {[c.name for c in collections]}")
                collection = collections[0]
                print(f"Using first collection: {collection.name}")
            else:
                print("❌ No collections found in ChromaDB")
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
        
        print(f"✅ Loaded {len(chunks)} chunks from ChromaDB")
        return chunks
        
    except Exception as e:
        print(f"❌ Error loading ChromaDB: {e}")
        print(f"Make sure ChromaDB exists at: {chroma_db_path}")
        return []


def load_vault_files_directly(vault_path: str, max_files: int = None) -> list:
    """
    Load markdown files directly from Obsidian vault
    
    Args:
        vault_path: Path to Obsidian vault
        max_files: Optional limit on number of files to process
    """
    try:
        print(f"Loading vault files from: {vault_path}")
        vault_dir = Path(vault_path)
        
        if not vault_dir.exists():
            print(f"❌ Vault path does not exist: {vault_path}")
            return []
        
        # Find all markdown files
        md_files = list(vault_dir.rglob('*.md'))
        
        if max_files:
            md_files = md_files[:max_files]
        
        print(f"Found {len(md_files)} markdown files")
        
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
                
                # Create chunks from file (simple chunking by paragraphs)
                paragraphs = content.split('\n\n')
                current_chunk = ""
                
                for para in paragraphs:
                    if len(current_chunk) + len(para) < 1000:
                        current_chunk += para + "\n\n"
                    else:
                        if current_chunk.strip():
                            chunks.append({
                                'text': current_chunk.strip(),
                                'metadata': {
                                    'filename': md_file.name,
                                    'filepath': str(md_file.relative_to(vault_dir)),
                                    'chunk_id': f"{md_file.stem}_{len(chunks)}"
                                }
                            })
                        current_chunk = para + "\n\n"
                
                # Add remaining chunk
                if current_chunk.strip():
                    chunks.append({
                        'text': current_chunk.strip(),
                        'metadata': {
                            'filename': md_file.name,
                            'filepath': str(md_file.relative_to(vault_dir)),
                            'chunk_id': f"{md_file.stem}_{len(chunks)}"
                        }
                    })
                    
            except Exception as e:
                print(f"Error reading {md_file}: {e}")
                continue
        
        print(f"✅ Created {len(chunks)} chunks from vault files")
        return chunks
        
    except Exception as e:
        print(f"❌ Error loading vault files: {e}")
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
        chunks = load_chromadb_from_disk(chroma_db_path)
    
    # Fallback to vault files if no ChromaDB chunks
    if not chunks and vault_path:
        max_files = 10 if test_mode else None
        chunks = load_vault_files_directly(vault_path, max_files)
    
    # Limit for test mode
    if test_mode and len(chunks) > n_test_chunks:
        print(f"Test mode: limiting to {n_test_chunks} chunks")
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
    
    print("=" * 70)
    print("Claude-Powered Knowledge Graph Builder for Obsidian Vault")
    print("=" * 70)
    
    # Initialize builder
    builder = ClaudeGraphBuilder(api_key=api_key)
    
    # Fetch chunks from filesystem
    if test_mode:
        print(f"\n📊 TEST MODE: Processing up to {n_test_chunks} chunks...")
    else:
        print("\n📊 PRODUCTION MODE: Processing ALL chunks (~7,113)...")
        print("⚠️  This will take several hours and cost ~$20-30 in API usage")
        confirm = input("Continue? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
    
    chunks = get_chunks_from_filesystem(
        chroma_db_path=chroma_db_path,
        vault_path=vault_path,
        test_mode=test_mode,
        n_test_chunks=n_test_chunks
    )
    
    if not chunks:
        print("❌ No chunks found.")
        print("\nPlease provide either:")
        print("  - ChromaDB path: Path to your chroma_db directory")
        print("  - Vault path: Path to your Obsidian vault")
        return
    
    print(f"✅ Found {len(chunks)} chunks to process")
    
    # Build graph
    print("\n🏗️  Building knowledge graph...")
    print("This uses Claude to extract entities and relationships from each chunk.")
    print("Progress will be saved every 10 chunks.\n")
    
    builder.build_graph_from_chunks(chunks, batch_size=10)
    
    # Save final graph
    output_file = "knowledge_graph_test.pkl" if test_mode else "knowledge_graph_full.pkl"
    builder.save_graph(output_file)
    
    # Export to JSON for visualization
    json_file = "knowledge_graph_test.json" if test_mode else "knowledge_graph_full.json"
    builder.export_graph_json(json_file)
    
    # Print statistics
    print("\n" + "=" * 70)
    print("📊 GRAPH STATISTICS")
    print("=" * 70)
    print(f"Total Chunks Processed: {builder.extraction_stats['chunks_processed']}")
    print(f"Total Entities Extracted: {builder.extraction_stats['entities_extracted']}")
    print(f"Total Relationships Extracted: {builder.extraction_stats['relationships_extracted']}")
    print(f"Errors: {builder.extraction_stats['errors']}")
    print(f"Unique Entities (Nodes): {builder.graph.number_of_nodes()}")
    print(f"Unique Relationships (Edges): {builder.graph.number_of_edges()}")
    
    # Show top entities
    querier = ClaudeGraphQuerier(builder, api_key)
    stats = querier.get_graph_stats()
    
    print("\n🌟 TOP 10 MOST CONNECTED ENTITIES:")
    for entity in stats['top_entities']:
        print(f"  • {entity['entity']}: {entity['connections']} connections")
    
    print(f"\n✅ Graph saved to: {output_file}")
    print(f"✅ JSON export saved to: {json_file}")
    
    return builder


def test_graph_queries(graph_file: str, api_key: str):
    """
    Test querying the built graph
    """
    print("\n" + "=" * 70)
    print("🧪 TESTING GRAPH QUERIES")
    print("=" * 70)
    
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
        print(f"\n❓ Query: {query}")
        print("-" * 70)
        answer = querier.query_with_claude(query)
        print(answer)
        print()


def interactive_graph_query(graph_file: str, api_key: str):
    """
    Interactive query interface for the knowledge graph
    """
    print("\n" + "=" * 70)
    print("💬 INTERACTIVE GRAPH QUERY")
    print("=" * 70)
    print("Commands:")
    print("  - Type a question to query the graph")
    print("  - Type 'stats' to see graph statistics")
    print("  - Type 'entity <name>' to explore an entity")
    print("  - Type 'path <entity1> to <entity2>' to find connections")
    print("  - Type 'quit' to exit")
    print("=" * 70)
    
    # Load graph
    builder = ClaudeGraphBuilder(api_key)
    builder.load_graph(graph_file)
    querier = ClaudeGraphQuerier(builder, api_key)
    
    while True:
        user_input = input("\n🔍 Your query: ").strip()
        
        if not user_input:
            continue
        
        if user_input.lower() == 'quit':
            print("Goodbye!")
            break
        
        if user_input.lower() == 'stats':
            stats = querier.get_graph_stats()
            print(f"\nGraph Statistics:")
            print(f"  Nodes: {stats['total_nodes']}")
            print(f"  Edges: {stats['total_edges']}")
            print(f"  Density: {stats['density']:.4f}")
            print(f"  Connected: {stats['is_connected']}")
            print(f"\nTop Entities:")
            for entity in stats['top_entities'][:5]:
                print(f"  • {entity['entity']}: {entity['connections']} connections")
            continue
        
        if user_input.lower().startswith('entity '):
            entity_name = user_input[7:].strip()
            neighborhood = querier.get_entity_neighborhood(entity_name)
            if not neighborhood.get('found', True):
                print(f"❌ Entity '{entity_name}' not found in graph")
            else:
                print(f"\n📍 Entity: {neighborhood['entity']}")
                print(f"   Type: {neighborhood['properties'].get('entity_type', 'Unknown')}")
                
                if neighborhood['outgoing']:
                    print(f"\n   Outgoing Relationships:")
                    for rel in neighborhood['outgoing'][:10]:
                        print(f"     → {rel['relationship']} → {rel['target']}")
                
                if neighborhood['incoming']:
                    print(f"\n   Incoming Relationships:")
                    for rel in neighborhood['incoming'][:10]:
                        print(f"     ← {rel['relationship']} ← {rel['source']}")
            continue
        
        if 'to' in user_input.lower() and user_input.lower().startswith('path '):
            # Parse path query
            parts = user_input[5:].split(' to ')
            if len(parts) == 2:
                source = parts[0].strip()
                target = parts[1].strip()
                paths = querier.find_paths(source, target)
                if paths:
                    print(f"\n🛤️  Found {len(paths)} path(s):")
                    for i, path in enumerate(paths[:5], 1):
                        print(f"   {i}. {' → '.join(path)}")
                else:
                    print(f"❌ No path found between '{source}' and '{target}'")
                continue
        
        # Regular query
        print("\n🤔 Thinking...")
        answer = querier.query_with_claude(user_input)
        print(f"\n💡 Answer:\n{answer}")


if __name__ == "__main__":
    import sys
    
    # Get API key from environment or prompt
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = input("Enter your Anthropic API key: ").strip()
        if not api_key:
            print("❌ API key required")
            sys.exit(1)
    
    # Get paths
    print("\n" + "=" * 70)
    print("CONFIGURATION")
    print("=" * 70)
    
    # Default paths
    default_chroma_path = "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/chroma_db"
    default_vault_path = "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
    
    print(f"\nDefault ChromaDB path: {default_chroma_path}")
    print(f"Default Vault path: {default_vault_path}")
    
    chroma_path = input("\nChromaDB path (or press Enter for default): ").strip()
    if not chroma_path:
        chroma_path = default_chroma_path
    
    vault_path = input("Vault path (or press Enter for default): ").strip()
    if not vault_path:
        vault_path = default_vault_path
    
    # Verify paths exist
    if not Path(chroma_path).exists() and not Path(vault_path).exists():
        print("\n❌ Neither path exists. Please check your paths.")
        print(f"   ChromaDB: {chroma_path}")
        print(f"   Vault: {vault_path}")
        sys.exit(1)
    
    print("\n✅ Paths configured")
    if Path(chroma_path).exists():
        print(f"   Using ChromaDB: {chroma_path}")
    if Path(vault_path).exists():
        print(f"   Using Vault: {vault_path}")
    
    print("\nChoose an option:")
    print("1. Build graph (TEST MODE - 50 chunks)")
    print("2. Build graph (FULL - all chunks)")
    print("3. Test queries on existing graph")
    print("4. Interactive query mode")
    
    choice = input("\nYour choice (1-4): ").strip()
    
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
        graph_file = input("Enter graph file path (or press Enter for 'knowledge_graph_test.pkl'): ").strip()
        if not graph_file:
            graph_file = "knowledge_graph_test.pkl"
        test_graph_queries(graph_file, api_key)
    
    elif choice == "4":
        graph_file = input("Enter graph file path (or press Enter for 'knowledge_graph_test.pkl'): ").strip()
        if not graph_file:
            graph_file = "knowledge_graph_test.pkl"
        interactive_graph_query(graph_file, api_key)
    
    else:
        print("Invalid choice")
