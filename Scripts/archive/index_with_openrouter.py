#!/usr/bin/env python3
"""
Index Obsidian vault using OpenRouter API
Supports Claude, GPT-4, and many other models
"""

import os
import sys
import asyncio
from pathlib import Path
from lightrag import LightRAG
from lightrag.utils import EmbeddingFunc
import anthropic
from typing import List

# Configuration
VAULT_PATH = "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
WORKING_DIR = "./lightrag_db"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Model selection - OpenRouter supports many models!
# Claude models (recommended):
#   - anthropic/claude-3.5-haiku (fast, cheap)
#   - anthropic/claude-3-5-sonnet-20241022 (premium quality)
# Other options:
#   - openai/gpt-4o-mini (fast, cheap)
#   - google/gemini-flash-1.5 (very fast, cheap)
#   - meta-llama/llama-3.1-70b-instruct (open source, cheap)
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-haiku")

# Check for API key
if not OPENROUTER_API_KEY:
    print("❌ Error: OPENROUTER_API_KEY not set")
    print("")
    print("Get your API key at: https://openrouter.ai/keys")
    print("Then run:")
    print("  export OPENROUTER_API_KEY='your-key-here'")
    print("")
    print("Optional: Choose model (defaults to Claude 3.5 Haiku):")
    print("  export OPENROUTER_MODEL='anthropic/claude-3.5-haiku'")
    print("")
    sys.exit(1)


# OpenRouter LLM function
async def openrouter_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    """OpenRouter API wrapper for LightRAG"""
    import httpx
    
    # Prepare messages
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    if history_messages:
        messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})
    
    # Call OpenRouter API
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "http://localhost:8501",  # Optional
                "X-Title": "LightRAG Indexer",  # Optional
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": 0.1,
            }
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]


# Local embeddings using sentence-transformers (free!)
_embedding_model = None

async def simple_embedding(texts):
    """Local embedding function using sentence-transformers"""
    global _embedding_model
    
    if _embedding_model is None:
        print("📦 Loading local embedding model (one-time setup)...")
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('sentence-transformers/all-mpnet-base-v2')
        print("✅ Embedding model loaded!")
    
    # Truncate texts to reasonable length
    truncated_texts = [text[:8000] for text in texts]
    
    # Generate embeddings
    embeddings = _embedding_model.encode(truncated_texts, show_progress_bar=False)
    
    return embeddings.tolist()


# Load vault
def load_vault_notes(vault_path: str):
    """Load all markdown files from vault"""
    vault = Path(vault_path)
    
    if not vault.exists():
        print(f"❌ Vault not found: {vault_path}")
        sys.exit(1)
    
    # Find all markdown files
    md_files = list(vault.rglob("*.md"))
    print(f"📚 Found {len(md_files)} markdown files")
    print("")
    
    # Load content
    notes = []
    for md_file in md_files:
        try:
            content = md_file.read_text(encoding='utf-8')
            if content.strip():  # Skip empty files
                notes.append(content)
        except Exception as e:
            print(f"⚠️  Skipped {md_file.name}: {e}")
    
    return notes


async def main():
    """Main indexing function"""
    print("╔════════════════════════════════════════════════════════════╗")
    print("║         Index with OpenRouter (Multi-Model Support)        ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("")
    print("✅ API key found")
    print(f"🤖 Model: {OPENROUTER_MODEL}")
    print(f"📂 Vault: {VAULT_PATH}")
    print(f"💾 Output: {WORKING_DIR}")
    print("")
    
    # Load notes
    print("📥 Loading notes from vault...")
    notes = load_vault_notes(VAULT_PATH)
    print(f"✅ Loaded {len(notes)} notes")
    print("")
    
    # Estimate cost (very rough - depends on model)
    if "haiku" in OPENROUTER_MODEL.lower():
        cost_per_note = 0.0012
    elif "gpt-4o-mini" in OPENROUTER_MODEL.lower():
        cost_per_note = 0.001
    elif "gemini-flash" in OPENROUTER_MODEL.lower():
        cost_per_note = 0.0005
    else:
        cost_per_note = 0.002  # Conservative estimate
    
    estimated_cost = len(notes) * cost_per_note
    estimated_time_min = len(notes) * 2 / 60
    estimated_time_max = len(notes) * 4 / 60
    
    print(f"💰 Estimated cost: ${estimated_cost:.2f}")
    print(f"⏱️  Estimated time: {estimated_time_min:.0f}-{estimated_time_max:.0f} minutes")
    print("")
    
    # Confirm
    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("❌ Cancelled")
        sys.exit(0)
    
    print("")
    print("🚀 Initializing LightRAG with OpenRouter...")
    
    # Initialize LightRAG
    rag = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=openrouter_model_complete,
        llm_model_name=OPENROUTER_MODEL,
        embedding_func=EmbeddingFunc(
            embedding_dim=768,  # all-mpnet-base-v2 uses 768 dimensions
            max_token_size=8192,
            func=simple_embedding
        ),
    )
    
    await rag.initialize_storages()
    
    # Initialize pipeline status (required for LightRAG 1.4.9+)
    from lightrag.kg.shared_storage import initialize_pipeline_status
    await initialize_pipeline_status()
    
    print("📥 Inserting notes into knowledge graph...")
    print("💡 This will take a while - be patient!")
    print("")
    
    # Process in batches
    batch_size = 50
    total_batches = (len(notes) + batch_size - 1) // batch_size
    
    for i in range(0, len(notes), batch_size):
        batch = notes[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        print(f"📊 Processing batch {batch_num}/{total_batches} ({len(batch)} notes)...")
        
        try:
            # Insert batch
            await rag.ainsert(batch)
            print(f"✅ Batch {batch_num} complete")
        except Exception as e:
            print(f"⚠️  Error in batch {batch_num}: {e}")
            print("Continuing with next batch...")
        
        print("")
    
    print("")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                  ✅ Indexing Complete!                      ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("")
    print(f"📊 Indexed {len(notes)} notes")
    print(f"💾 Database: {WORKING_DIR}")
    print("")
    print("Next steps:")
    print("  1. View graph: python3 visualize_graph.py")
    print("  2. Start UI: ./Scripts/docker_start.sh")
    print("  3. Open browser: http://localhost:8501")
    print("")


if __name__ == "__main__":
    asyncio.run(main())

