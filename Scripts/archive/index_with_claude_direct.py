#!/usr/bin/env python3
"""
Direct indexing with Claude API (runs outside Docker)
Uses Claude Haiku 4.5 for high-quality, low-cost indexing
"""

import os
import sys
import asyncio
from pathlib import Path
from lightrag import LightRAG, QueryParam
from lightrag.utils import EmbeddingFunc
import anthropic

# Configuration
VAULT_PATH = "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
WORKING_DIR = "./lightrag_db"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5")

# Check for API key
if not ANTHROPIC_API_KEY:
    print("❌ Error: ANTHROPIC_API_KEY not set")
    print("")
    print("Get your API key at: https://console.anthropic.com/")
    print("Then run:")
    print("  export ANTHROPIC_API_KEY='your-key-here'")
    print("  python3 index_with_claude_direct.py")
    sys.exit(1)

print("╔════════════════════════════════════════════════════════════╗")
print("║      Index with Claude Haiku 4.5 (Direct Mode)             ║")
print("╚════════════════════════════════════════════════════════════╝")
print("")
print(f"✅ API key found")
print(f"🤖 Model: {CLAUDE_MODEL}")
print(f"📂 Vault: {VAULT_PATH}")
print(f"💾 Output: {WORKING_DIR}")
print("")

# Claude LLM wrapper
async def claude_model_complete(
    prompt, system_prompt=None, history_messages=[], **kwargs
) -> str:
    """Claude API wrapper for LightRAG"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    messages = []
    if history_messages:
        messages.extend(history_messages)
    messages.append({"role": "user", "content": prompt})
    
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        system=system_prompt or "You are a helpful assistant.",
        messages=messages
    )
    
    return response.content[0].text


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
    notes = []
    vault = Path(vault_path)
    
    if not vault.exists():
        print(f"❌ Error: Vault not found at {vault_path}")
        sys.exit(1)
    
    md_files = list(vault.rglob("*.md"))
    print(f"📚 Found {len(md_files)} markdown files")
    print("")
    
    for md_file in md_files:
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    notes.append(content)
        except Exception as e:
            print(f"⚠️  Could not read {md_file.name}: {e}")
    
    return notes


# Main async function
async def main():
    print("📥 Loading notes from vault...")
    notes = load_vault_notes(VAULT_PATH)
    
    if not notes:
        print("❌ No markdown files found!")
        sys.exit(1)
    
    print(f"✅ Loaded {len(notes)} notes")
    print("")
    
    # Estimate cost
    avg_chars_per_note = sum(len(n) for n in notes) / len(notes)
    total_tokens = (sum(len(n) for n in notes) / 4)  # Rough estimate
    
    if "haiku" in CLAUDE_MODEL.lower():
        cost = (total_tokens / 1_000_000) * 0.80  # Input cost
        cost += (total_tokens * 0.3 / 1_000_000) * 4.00  # Output cost (estimate 30%)
        print(f"💰 Estimated cost: ${cost:.2f}")
    else:
        cost = (total_tokens / 1_000_000) * 3.00
        cost += (total_tokens * 0.3 / 1_000_000) * 15.00
        print(f"💰 Estimated cost: ${cost:.2f}")
    
    print(f"⏱️  Estimated time: {len(notes) * 2 / 60:.0f}-{len(notes) * 4 / 60:.0f} minutes")
    print("")
    
    response = input("Continue? (y/n): ")
    if response.lower() != 'y':
        print("❌ Cancelled")
        sys.exit(0)
    
    print("")
    print("🚀 Initializing LightRAG with Claude...")
    
    # Initialize LightRAG
    rag = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=claude_model_complete,
        llm_model_name=CLAUDE_MODEL,
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
    
    # Insert in batches to show progress
    batch_size = 50
    for i in range(0, len(notes), batch_size):
        batch = notes[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(notes) + batch_size - 1) // batch_size
        
        print(f"📊 Processing batch {batch_num}/{total_batches} ({len(batch)} notes)...")
        
        try:
            await rag.ainsert(batch)
            print(f"✅ Batch {batch_num} complete")
        except Exception as e:
            print(f"⚠️  Error in batch {batch_num}: {e}")
            print("Continuing with next batch...")
    
    await rag.finalize_storages()
    
    print("")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║                  ✅ Indexing Complete!                      ║")
    print("╚════════════════════════════════════════════════════════════╝")
    print("")
    print(f"📊 Indexed {len(notes)} notes")
    print(f"💾 Database: {WORKING_DIR}")
    print("")
    print("Next steps:")
    print("  1. Start services: ./Scripts/docker_start.sh")
    print("  2. Open UI: http://localhost:8501")
    print("  3. Try graph search modes!")
    print("")


if __name__ == "__main__":
    asyncio.run(main())

