import os
import logging
from mem0 import Memory
from pathlib import Path

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Manages user-specific episodic memory using mem0.
    Stores and retrieves atomic facts about the user to provide personalized context.
    """
    def __init__(self, user_id="michel_obsidian_user"):
        self.user_id = user_id
        
        # Configuration for mem0
        # We point it to the same ChromaDB instance if possible, or a local path
        # For simplicity and isolation, we'll use a local subdirectory
        vector_provider = os.getenv("MEM0_VECTOR_PROVIDER", "chroma").strip().lower()
        # Backward compatibility: older config used "chromadb", mem0 expects "chroma".
        if vector_provider == "chromadb":
            vector_provider = "chroma"

        config = {
            "vector_store": {
                "provider": vector_provider,
                "config": {
                    "path": "./memory_db",
                    "collection_name": "user_memories",
                }
            },
            "llm": {
                "provider": "openai",
                "config": {
                    "model": "gpt-4o-mini", # Lightweight for fact extraction
                    # API Key will be picked up from OPENAI_API_KEY env var
                }
            }
        }
        
        # Check for OpenAI API Key (required by mem0 for embedding/reasoning)
        if not os.environ.get("OPENAI_API_KEY"):
            logger.warning("OPENAI_API_KEY not set. mem0 might fail during fact extraction.")
        
        try:
            self.memory = Memory.from_config(config)
            logger.info("MemoryManager initialized with mem0")
        except Exception as e:
            logger.error(f"Failed to initialize mem0: {e}")
            self.memory = None

    def add_memory(self, text: str):
        """Add new information to memory"""
        if not self.memory:
            return None
        
        try:
            return self.memory.add(text, user_id=self.user_id)
        except Exception as e:
            logger.error(f"Error adding to memory: {e}")
            return None

    def search_memory(self, query: str, limit: int = 5):
        """Search memory for relevant facts"""
        if not self.memory:
            return ""
        
        try:
            results = self.memory.search(query, user_id=self.user_id, limit=limit)
            if not results:
                return ""

            # mem0 response shape varies by version/provider:
            # - list[dict] with "text"
            # - dict with "results"/"memories"/"data" arrays
            if isinstance(results, dict):
                for key in ("results", "memories", "data"):
                    value = results.get(key)
                    if isinstance(value, list):
                        results = value
                        break
                else:
                    results = []
            elif not isinstance(results, list):
                results = []

            facts = []
            for entry in results:
                if isinstance(entry, dict):
                    text = (
                        entry.get("text")
                        or entry.get("memory")
                        or entry.get("content")
                        or ""
                    )
                elif isinstance(entry, str):
                    text = entry
                else:
                    text = str(entry) if entry is not None else ""
                text = str(text).strip()
                if text:
                    facts.append(text)
            if not facts:
                return ""
            return "\n".join([f"- {fact}" for fact in facts])
        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            return ""

    def get_all_memories(self):
        """Retrieve all stored memories for the user"""
        if not self.memory:
            return []
        
        try:
            return self.memory.get_all(user_id=self.user_id)
        except Exception as e:
            logger.error(f"Error getting all memories: {e}")
            return []

# Singleton instance
_manager = None

def get_memory_manager():
    global _manager
    if _manager is None:
        _manager = MemoryManager()
    return _manager
