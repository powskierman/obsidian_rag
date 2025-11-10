#!/usr/bin/env python3
"""
LightRAG Initialization for Obsidian RAG Stack
Compatible with LightRAG v1.4.9.4 and Ollama local backend
"""

import os
import asyncio
from pathlib import Path
from lightrag import LightRAG, QueryParam
from lightrag.llm.ollama import ollama_model_complete, ollama_embed
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.utils import EmbeddingFunc, setup_logger


# ────────────────────────────────────────────────
# Configuration
# ────────────────────────────────────────────────

WORKING_DIR = "./lightrag_db"
VAULT_DIR = "./vault"  # Mounted host folder: ~/Documents/ObsidianVault → /app/vault

LLM_MODEL_NAME = "qwen2.5:7b"
EMBED_MODEL_NAME = "nomic-embed-text"

# Optionally expand context window for Ollama
LLM_MODEL_KWARGS = {"options": {"num_ctx": 32768}}

# Setup logging
setup_logger("lightrag", level="INFO")


# ────────────────────────────────────────────────
# Load Markdown Notes from Obsidian Vault
# ────────────────────────────────────────────────

def load_vault_texts(vault_path: str):
    """Recursively load all Markdown files from the vault folder"""
    notes = []
    for md_file in Path(vault_path).rglob("*.md"):
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    notes.append(content)
        except Exception as e:
            print(f"⚠️ Could not read {md_file}: {e}")
    print(f"✅ Loaded {len(notes)} Markdown notes from {vault_path}")
    return notes


# ────────────────────────────────────────────────
# LightRAG Initialization
# ────────────────────────────────────────────────
os.environ["OLLAMA_HOST"] = "http://host.docker.internal:11434"

async def initialize_rag():
    """Create and initialize LightRAG with Ollama LLM and embedding"""
    rag = LightRAG(
        working_dir=WORKING_DIR,
        llm_model_func=ollama_model_complete,
        llm_model_name=LLM_MODEL_NAME,
        llm_model_kwargs=LLM_MODEL_KWARGS,
        embedding_func=EmbeddingFunc(
            embedding_dim=768,
            func=lambda texts: ollama_embed(texts, embed_model=EMBED_MODEL_NAME)
        ),
    )
    await rag.initialize_storages()
    await initialize_pipeline_status()
    return rag


# ────────────────────────────────────────────────
# Main async Entry Point
# ────────────────────────────────────────────────

async def main():
    rag = await initialize_rag()

    # Step 1: Load Notes
    notes = load_vault_texts(VAULT_DIR)

    # Step 2: Insert Notes
    if notes:
        print("📥 Inserting notes into LightRAG...")
        await rag.ainsert(notes)
        print("✅ Notes successfully indexed.")

    # Step 3: Run a Sample Query
    param = QueryParam(mode="hybrid")
    query = "How does my treatment relate to outcomes?"
    print(f"\n🔎 Querying: {query}\n")
    result = await rag.aquery(query, param=param)
    print("💬 Query Result:")
    print(result)

    await rag.finalize_storages()
    print("\n✅ LightRAG session complete.")


# ────────────────────────────────────────────────
# Entrypoint
# ────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(main())
