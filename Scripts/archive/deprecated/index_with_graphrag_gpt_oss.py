#!/usr/bin/env python3
"""
Index Obsidian vault with LightRAG (graph-based RAG) using GPT-OSS and Nomic-embed-text

This script:
- Scans your Obsidian vault for markdown files
- Indexes them using LightRAG with GPT-OSS for LLM and Nomic-embed-text for embeddings
- Creates a knowledge graph for enhanced querying
"""

import asyncio
import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from lightrag import LightRAG
from lightrag.utils import EmbeddingFunc

# Import GPT-OSS integration
try:
    from gpt_oss_integration import get_model_func, get_embed_func
except ImportError:
    print("❌ Error: gpt_oss_integration.py not found")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DEFAULT_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel")
DEFAULT_WORKING_DIR = "./lightrag_db"
DEFAULT_GPT_OSS_HOST = os.getenv("GPT_OSS_HOST", "http://localhost:12434/engines/llama.cpp")
# Default to Ollama host instead of GPT-OSS to avoid context shift issues
DEFAULT_OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_LLM_HOST = os.getenv("LLM_HOST", DEFAULT_OLLAMA_HOST)  # Default to Ollama
# Default to Ollama with qwen2.5-coder:14b instead of GPT-OSS to avoid context shift issues
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:14b")
DEFAULT_EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")


def load_vault_notes(vault_path: str) -> List[str]:
    """Load all markdown files from the vault"""
    notes = []
    skipped = 0
    vault_dir = Path(vault_path)
    
    if not vault_dir.exists():
        logger.error(f"❌ Vault path does not exist: {vault_path}")
        return []
    
    logger.info(f"📂 Scanning vault: {vault_path}")
    
    # Exclude patterns
    exclude_patterns = [
        ".obsidian",
        ".git",
        "node_modules",
        ".Trash",
        "Templates",
        "Daily Notes",
    ]
    
    for md_file in vault_dir.rglob("*.md"):
        # Skip excluded directories
        if any(pattern in str(md_file) for pattern in exclude_patterns):
            skipped += 1
            continue
        
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content and len(content) > 10:  # Skip very short files
                    notes.append(content)
        except Exception as e:
            logger.warning(f"⚠️  Could not read {md_file.name}: {e}")
            skipped += 1
    
    logger.info(f"📚 Found {len(notes)} notes to index")
    if skipped > 0:
        logger.info(f"   Skipped {skipped} files")
    
    return notes


async def index_with_lightrag(
    vault_path: str,
    working_dir: str = DEFAULT_WORKING_DIR,
    gpt_oss_host: str = None,  # Will default to Ollama
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    llm_model: str = DEFAULT_LLM_MODEL,
    embed_model: str = DEFAULT_EMBED_MODEL,
    clean_db: bool = False,
    skip_checks: bool = False
):
    """Index vault with LightRAG using GPT-OSS and Nomic-embed-text"""
    
    # Load vault notes
    notes = load_vault_notes(vault_path)
    
    if not notes:
        logger.error("❌ No notes found to index!")
        return
    
    # Clean database if requested
    if clean_db:
        working_dir_path = Path(working_dir)
        if working_dir_path.exists():
            logger.info(f"🗑️  Cleaning database: {working_dir}")
            import shutil
            shutil.rmtree(working_dir_path)
            working_dir_path.mkdir(parents=True, exist_ok=True)
            logger.info("✅ Database cleaned")
    
    # Check services
    if not skip_checks:
        logger.info("🔍 Checking services...")
        
        # Check GPT-OSS
        try:
            import requests
            response = requests.get(f"{gpt_oss_host.replace('/v1/chat/completions', '')}/v1/models", timeout=5)
            if response.status_code == 200:
                logger.info("✅ GPT-OSS is available")
            else:
                logger.warning(f"⚠️  GPT-OSS check failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️  GPT-OSS not reachable: {e}")
        
        # Check Ollama
        try:
            response = requests.get(f"{ollama_host}/api/tags", timeout=5)
            if response.status_code == 200:
                logger.info("✅ Ollama is available")
            else:
                logger.warning(f"⚠️  Ollama check failed: {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️  Ollama not reachable: {e}")
    
    logger.info("")
    logger.info("🚀 Initializing LightRAG with LLM and Nomic-embed-text...")
    
    # Determine if we should use GPT-OSS or Ollama
    # Default to Ollama if gpt_oss_host is not provided or is None
    if gpt_oss_host is None:
        gpt_oss_host = DEFAULT_OLLAMA_HOST
    
    # Only use GPT-OSS if explicitly detected (contains /engines/llama.cpp or port 12434)
    # Otherwise, always use Ollama to avoid context shift issues
    use_gpt_oss = "/engines/llama.cpp" in str(gpt_oss_host) or ":12434" in str(gpt_oss_host)
    
    if use_gpt_oss:
        llm_host = gpt_oss_host
        logger.warning("⚠️  GPT-OSS detected - may encounter 'context shift disabled' errors")
    else:
        llm_host = ollama_host
        logger.info("✅ Using Ollama (default) to avoid GPT-OSS context shift issues")
    
    logger.info(f"   LLM: {llm_model} via {llm_host}")
    logger.info(f"   Embedding: {embed_model} via {ollama_host}")
    logger.info(f"   Working Dir: {working_dir}")
    
    # Get model and embedding functions
    model_func = get_model_func(llm_host)
    if use_gpt_oss:
        logger.info(f"Using GPT-OSS endpoint: {gpt_oss_host}")
    else:
        logger.info(f"Using Ollama endpoint: {ollama_host}")
    
    # Always use Ollama for embeddings (GPT-OSS doesn't provide embeddings)
    # Note: Using custom implementation because LightRAG's ollama_embed requires
    # ollama.AsyncClient which isn't available in the installed ollama package version
    import requests
    import numpy as np
    import asyncio as async_module  # Create local reference for closure
    
    async def embedding_wrapper(texts):
        """Async wrapper for Ollama embeddings using requests API directly"""
        if not texts:
            return np.array([])
        
        embed_url = f"{ollama_host}/api/embeddings"
        current_loop = async_module.get_event_loop()
        
        # Process embeddings in parallel using thread pool executor
        async def embed_single(text):
            """Embed a single text"""
            try:
                # Use the captured loop reference
                response = await current_loop.run_in_executor(
                    None,
                    lambda: requests.post(
                        embed_url,
                        json={"model": embed_model, "prompt": text},
                        timeout=60
                    )
                )
                response.raise_for_status()
                data = response.json()
                return data.get("embedding", [0.0] * 768)
            except Exception as e:
                logger.warning(f"Error embedding text: {e}")
                return [0.0] * 768
        
        # Process all embeddings concurrently
        embeddings = await async_module.gather(*[embed_single(text) for text in texts])
        return np.array(embeddings)
    
    # Initialize LightRAG
    try:
        rag = LightRAG(
            working_dir=working_dir,
            llm_model_func=model_func,
            llm_model_name=llm_model,
            llm_model_kwargs={
                "options": {"num_ctx": 32768},  # Full context for Ollama, reduced for GPT-OSS
                "host": llm_host,
                "max_tokens": 4096 if not use_gpt_oss else 512,  # Larger for Ollama, small for GPT-OSS
            },
            embedding_func=EmbeddingFunc(
                embedding_dim=768,  # Nomic-embed-text uses 768 dimensions
                func=embedding_wrapper
            ),
        )
        
        # Initialize storages with error handling for corrupted databases
        try:
            await rag.initialize_storages()
            
            # Initialize pipeline status (required for LightRAG 1.4.9+)
            from lightrag.kg.shared_storage import initialize_pipeline_status
            await initialize_pipeline_status()
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"❌ Database corruption detected: {e}")
            logger.error("")
            logger.error("   The LightRAG database appears to be corrupted.")
            logger.error("")
            logger.error("   To fix: Run with --clean-db flag to delete and recreate the database")
            logger.error(f"   Example: {sys.argv[0]} --clean-db --yes")
            logger.error("")
            raise
        
        logger.info("✅ LightRAG initialized")
        logger.info("")
        logger.info("📥 Inserting notes into knowledge graph...")
        logger.info("💡 This will take a while - be patient!")
        logger.info("")
        
        # Process in batches
        batch_size = 50
        total_batches = (len(notes) + batch_size - 1) // batch_size
        
        try:
            for i in range(0, len(notes), batch_size):
                batch = notes[i:i+batch_size]
                batch_num = i // batch_size + 1
                
                logger.info(f"📊 Processing batch {batch_num}/{total_batches} ({len(batch)} notes)...")
                
                try:
                    await rag.ainsert(batch)
                    logger.info(f"✅ Batch {batch_num} complete")
                except KeyboardInterrupt:
                    logger.warning("")
                    logger.warning("⚠️  Interrupted during batch processing")
                    raise
                except Exception as e:
                    logger.error(f"❌ Error in batch {batch_num}: {e}")
                    logger.info("Continuing with next batch...")
                
                logger.info("")
        except KeyboardInterrupt:
            logger.warning("")
            logger.warning("⚠️  Interrupted by user - cleaning up...")
            # Give tasks a moment to finish
            await async_module.sleep(0.5)
            raise
        
        logger.info("")
        logger.info("╔════════════════════════════════════════════════════════════╗")
        logger.info("║                  ✅ Indexing Complete!                      ║")
        logger.info("╚════════════════════════════════════════════════════════════╝")
        logger.info("")
        logger.info(f"📊 Indexed {len(notes)} notes")
        logger.info(f"💾 Database: {working_dir}")
        logger.info("")
        
    except Exception as e:
        logger.error(f"❌ Indexing error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Index Obsidian vault with LightRAG (graph-based RAG) using GPT-OSS and Nomic-embed-text"
    )
    parser.add_argument(
        "--vault-path",
        type=str,
        default=DEFAULT_VAULT_PATH,
        help=f"Path to Obsidian vault (default: {DEFAULT_VAULT_PATH})"
    )
    parser.add_argument(
        "--working-dir",
        type=str,
        default=DEFAULT_WORKING_DIR,
        help=f"LightRAG working directory (default: {DEFAULT_WORKING_DIR})"
    )
    parser.add_argument(
        "--gpt-oss-host",
        type=str,
        default=DEFAULT_OLLAMA_HOST,  # Default to Ollama instead of GPT-OSS
        help=f"LLM endpoint - use Ollama (http://localhost:11434) or GPT-OSS (http://localhost:12434/engines/llama.cpp) (default: {DEFAULT_OLLAMA_HOST})"
    )
    parser.add_argument(
        "--ollama-host",
        type=str,
        default=DEFAULT_OLLAMA_HOST,
        help=f"Ollama endpoint (default: {DEFAULT_OLLAMA_HOST})"
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default=DEFAULT_LLM_MODEL,
        help=f"LLM model name (default: {DEFAULT_LLM_MODEL})"
    )
    parser.add_argument(
        "--embed-model",
        type=str,
        default=DEFAULT_EMBED_MODEL,
        help=f"Embedding model name (default: {DEFAULT_EMBED_MODEL})"
    )
    parser.add_argument(
        "--clean-db",
        action="store_true",
        help="Delete and recreate the database directory"
    )
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Skip service availability checks"
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt"
    )
    
    args = parser.parse_args()
    
    # Show configuration
    print("")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║   LightRAG (Graph-based RAG) Indexing                      ║")
    print("║   Using LLM & Nomic-embed-text                             ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("")
    # Determine which LLM provider to use
    use_gpt_oss = "/engines/llama.cpp" in args.gpt_oss_host or ":12434" in args.gpt_oss_host
    llm_host = args.gpt_oss_host if use_gpt_oss else args.ollama_host
    
    print(f"📂 Vault: {args.vault_path}")
    print(f"💾 Database: {args.working_dir}")
    print(f"🤖 LLM: {args.llm_model} via {llm_host} ({'GPT-OSS' if use_gpt_oss else 'Ollama'})")
    print(f"🔢 Embedding: {args.embed_model} via {args.ollama_host}")
    print("")
    
    if args.clean_db:
        print("⚠️  WARNING: Database will be deleted and recreated!")
        print("")
    
    # Confirmation
    if not args.yes:
        try:
            response = input("Continue? (y/n): ")
            if response.lower() != 'y':
                print("❌ Cancelled")
                sys.exit(0)
        except (EOFError, KeyboardInterrupt):
            print("❌ Cancelled")
            sys.exit(0)
    
    print("")
    
    # Run indexing
    try:
        # Determine LLM host - default to Ollama to avoid GPT-OSS context shift issues
        use_gpt_oss = "/engines/llama.cpp" in args.gpt_oss_host or ":12434" in args.gpt_oss_host
        
        # If user didn't explicitly set GPT-OSS host, use Ollama
        if not use_gpt_oss:
            llm_host = args.ollama_host
            logger.info("Using Ollama (default) to avoid GPT-OSS context shift issues")
        else:
            llm_host = args.gpt_oss_host
            logger.warning("Using GPT-OSS - may encounter 'context shift disabled' errors")
        
        # Run with proper cleanup - use asyncio.run which handles event loop properly
        try:
            asyncio.run(
                index_with_lightrag(
                    vault_path=args.vault_path,
                    working_dir=args.working_dir,
                    gpt_oss_host=llm_host,  # Pass the determined host
                    ollama_host=args.ollama_host,
                    llm_model=args.llm_model,
                    embed_model=args.embed_model,
                    clean_db=args.clean_db,
                    skip_checks=args.skip_checks
                )
            )
        except KeyboardInterrupt:
            logger.warning("")
            logger.warning("⚠️  Interrupted by user")
            sys.exit(130)  # Standard exit code for SIGINT
                
    except KeyboardInterrupt:
        logger.error("")
        logger.error("❌ Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error("")
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

