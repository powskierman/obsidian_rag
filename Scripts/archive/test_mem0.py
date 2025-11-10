from mem0 import Memory
from pprint import pprint

config = {
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "qwen2.5-coder:32b",
            "ollama_base_url": "http://localhost:11434"
        }
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://localhost:11434"
        }
    },
    "vector_store": {
        "provider": "chroma",
        "config": {
            "collection_name": "rag_memories",
            "path": "./mem0_db"
        }
    }
}

m = Memory.from_config(config)
m.add("Testing local Mem0", user_id="michel")

# Use keyword argument instead of positional
pprint(m.get_all(user_id="michel"))
