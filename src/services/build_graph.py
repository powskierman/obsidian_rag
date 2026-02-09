import os
import logging
import argparse
from networkx_graph_builder import GraphBuilder

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

VAULT_PATH = "/app/vault"
# Handle local dev paths if /app/vault doesn't exist
if not os.path.exists(VAULT_PATH):
    # Try finding vault relative to this script or use env var
    VAULT_PATH = os.environ.get("VAULT_PATH", "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/vault_data") # Default fallback

GRAPH_PATH = os.environ.get("GRAPH_PATH", "").strip()
if not GRAPH_PATH:
    data_dir = os.environ.get("OBSIDIAN_RAG_DATA_DIR", "").strip()
    if data_dir:
        GRAPH_PATH = os.path.join(data_dir, "graph_data", "knowledge_graph_full.pkl")
    else:
        GRAPH_PATH = "/app/graph_data/knowledge_graph_full.pkl"

if not os.path.exists(os.path.dirname(GRAPH_PATH)):
    # Fallback for local runs without centralized data directory configured
    GRAPH_PATH = "graph_data/knowledge_graph_full.pkl"

def process_vault():
    """Main function to process vault and build structural graph"""
    parser = argparse.ArgumentParser(description='Build Obsidian Knowledge Graph')
    parser.add_argument('--force-refresh', action='store_true', help='Force rebuild graph from scratch')
    args = parser.parse_args()

    # API key might be needed for other things, but not strict building anymore
    api_key = os.environ.get("OPENROUTER_API_KEY") # Optional for builder now

    logger.info(f"Initializing GraphBuilder...")
    builder = GraphBuilder(api_key=api_key)
    
    # We don't need to load existing graph if we are building structure 
    # because structure is fast to rebuild (seconds vs hours for LLM).
    # But if we want to preserve some expensive attributes (embeddings?), we might load.
    # The requirement said "For an Obsidian → NetworkX index... treat it as a multi-layer graph". 
    # Usually structural graphs are rebuilt from scratch to ensure sync with FS.
    
    logger.info(f"Scanning vault at {VAULT_PATH}...")
    
    try:
        builder.build_structure(VAULT_PATH)
        
        logger.info("Graph construction complete. Saving...")
        builder.save_graph(GRAPH_PATH)
        logger.info(f"Graph successfully saved to {GRAPH_PATH}")
        
    except Exception as e:
        logger.error(f"Failed to build graph: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    process_vault()
