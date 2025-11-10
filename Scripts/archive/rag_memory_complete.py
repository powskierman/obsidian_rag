#!/usr/bin/env python3
"""
Memory-Enhanced RAG using Mem0
Remembers conversations, user context, and medical timeline
"""

from mem0 import Memory
import requests
from datetime import datetime
import json

# Initialize Mem0 with local storage
config = {
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "qwen2.5-coder:32b",
            "ollama_base_url": "http://localhost:11434",
            "temperature": 0.3
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

memory = Memory.from_config(config)

EMBEDDING_URL = "http://localhost:8000"
OLLAMA_URL = "http://localhost:11434"

class MemoryRAG:
    def __init__(self, user_id="michel"):
        self.user_id = user_id
        self.memory = memory
    
    def add_medical_timeline(self):
        """Initialize Michel's medical timeline in memory"""
        facts = [
            "User (Michel) has high-grade B-cell DLBCL with double-hit status",
            "Completed R-CHOP chemotherapy treatment",
            "Received Yescarta CAR-T therapy approximately 6 months ago (April 2025)",
            "Had 3-month post-Yescarta PET scan (July 2025) - results in '3rd PET Scan' note",
            "Scheduled for 6-month post-Yescarta PET scan week of October 19, 2025",
            "Important metrics to track: SUV max, lymph node status, Deauville score, IgG levels, B-cell recovery",
            "User also interested in: 3D printing (resin printing, Photon Zero), Raspberry Pi, Fusion 360, AI/ML",
            "User prefers privacy-first, local-only AI solutions",
            "User's knowledge base has ~1,560 notes in Obsidian, indexed as ~6,860 chunks",
            "User appreciates detailed technical and medical explanations"
        ]
        
        for fact in facts:
            self.memory.add(
                messages=[{"role": "system", "content": fact}],
                user_id=self.user_id
            )
        
        print(f"✅ Added {len(facts)} timeline facts to memory")
        return len(facts)
    
    def query(self, question, n_vault_results=5, model="qwen2.5-coder:32b"):
        """Query with memory-enhanced context"""
        
        print(f"\n{'='*60}")
        print(f"Query: {question}")
        print(f"{'='*60}\n")
        
        # 1. Retrieve relevant memories
        print("🧠 Retrieving memories...")
        memories = self.memory.search(
            query=question,
            user_id=self.user_id,
            limit=5
        )
        
        memory_context = "\n".join([
            f"- {m['memory']}" for m in memories
        ]) if memories else "No specific memories found."
        
        print(f"Found {len(memories)} relevant memories")
        
        # 2. Search vault with memory context
        print("📚 Searching vault...")
        enriched_query = f"{question}\n\nUser context: {memory_context}"
        
        try:
            vault_response = requests.post(
                f"{EMBEDDING_URL}/query",
                json={
                    "query": enriched_query,
                    "n_results": n_vault_results,
                    "reranking": True,
                    "deduplicate": True
                },
                timeout=10
            )
            
            vault_results = vault_response.json()
            documents = vault_results.get('documents', [[]])[0]
            metadatas = vault_results.get('metadatas', [[]])[0]
            distances = vault_results.get('distances', [[]])[0]
        except Exception as e:
            print(f"❌ Vault search failed: {e}")
            documents, metadatas, distances = [], [], []
        
        print(f"Found {len(documents)} relevant notes")
        
        # 3. Build context
        vault_context = "\n\n---\n\n".join([
            f"From {meta.get('filename', 'unknown')} ({(1-dist)*100:.0f}% relevant):\n{doc}"
            for doc, meta, dist in zip(documents, metadatas, distances)
        ]) if documents else "No relevant notes found in vault."
        
        # 4. Generate response with both contexts
        print(f"💭 Generating response with {model}...")
        
        system_prompt = f"""You are an AI assistant helping Michel with his Obsidian knowledge base.

MICHEL'S CONTEXT (from memory):
{memory_context}

RELEVANT NOTES FROM VAULT:
{vault_context}

USER QUESTION: {question}

Provide a thorough, personalized answer that:
1. References his specific medical timeline when relevant (DLBCL, Yescarta, scans)
2. Uses information from his notes with appropriate context
3. Is compassionate and supportive for medical topics
4. Is technically detailed for coding/project topics
5. Adapts to his level of understanding (he appreciates depth)
6. Avoids repeating things he already knows well
7. Cites which sources you're using

Answer:"""

        try:
            ollama_response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": system_prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_ctx": 65536
                    }
                },
                timeout=180
            )
            
            response_text = ollama_response.json().get('response', 'Error: No response generated')
        except Exception as e:
            response_text = f"Error generating response: {e}"
            print(f"❌ {response_text}")
        
        # 5. Store new memories
        print("💾 Storing conversation in memory...")
        self.memory.add(
            messages=[
                {"role": "user", "content": question},
                {"role": "assistant", "content": response_text}
            ],
            user_id=self.user_id
        )
        
        print(f"\n{'='*60}")
        print("✅ Query complete")
        print(f"{'='*60}\n")
        
        return {
            "answer": response_text,
            "memories_used": memories,
            "vault_sources": [
                {
                    "filename": m.get('filename'),
                    "relevance": (1-d)*100
                }
                for m, d in zip(metadatas, distances)
            ],
            "memory_context": memory_context
        }
    
    def get_all_memories(self):
        """Retrieve all memories for user"""
        return self.memory.get_all(user_id=self.user_id)
    
    def clear_memories(self):
        """Clear all memories (use with caution)"""
        all_memories = self.get_all_memories()
        for mem in all_memories:
            self.memory.delete(memory_id=mem['id'])
        print(f"🗑️ Cleared {len(all_memories)} memories")
        return len(all_memories)
    
    def add_fact(self, fact):
        """Manually add a fact about the user"""
        self.memory.add(
            messages=[{"role": "system", "content": fact}],
            user_id=self.user_id
        )
        print(f"✅ Added fact: {fact[:50]}...")
    
    def export_memories(self, filename=None):
        """Export memories to JSON file"""
        if filename is None:
            filename = f"memories_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        memories = self.get_all_memories()
        
        with open(filename, 'w') as f:
            json.dump(memories, f, indent=2)
        
        print(f"📝 Exported {len(memories)} memories to {filename}")
        return filename

def interactive_session():
    """Run interactive Q&A session"""
    rag = MemoryRAG()
    
    print("\n" + "="*60)
    print("🧠 Memory-Enhanced RAG - Interactive Session")
    print("="*60)
    print("Commands:")
    print("  'exit' or 'quit' - End session")
    print("  'memories' - Show all memories")
    print("  'clear' - Clear all memories")
    print("  'export' - Export memories to file")
    print("="*60 + "\n")
    
    while True:
        try:
            question = input("\n💬 Your question: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ['exit', 'quit']:
                print("\n👋 Goodbye!")
                break
            
            if question.lower() == 'memories':
                memories = rag.get_all_memories()
                print(f"\n📚 {len(memories)} memories stored:")
                for i, mem in enumerate(memories[-10:], 1):
                    print(f"{i}. {mem.get('memory', 'N/A')[:80]}...")
                continue
            
            if question.lower() == 'clear':
                confirm = input("⚠️ Clear all memories? (yes/no): ")
                if confirm.lower() == 'yes':
                    rag.clear_memories()
                continue
            
            if question.lower() == 'export':
                filename = rag.export_memories()
                print(f"✅ Memories exported to {filename}")
                continue
            
            # Process query
            result = rag.query(question)
            
            print(f"\n📝 Answer:\n{result['answer']}\n")
            
            if result['memories_used']:
                print(f"🧠 Used {len(result['memories_used'])} memories")
            
            if result['vault_sources']:
                print(f"📚 Used {len(result['vault_sources'])} vault sources")
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'init':
        # Initialize memory
        print("Initializing memory with Michel's timeline...")
        rag = MemoryRAG()
        rag.add_medical_timeline()
        print("\n✅ Memory initialized!")
    elif len(sys.argv) > 1 and sys.argv[1] == 'interactive':
        # Run interactive session
        interactive_session()
    else:
        # Quick test
        rag = MemoryRAG()
        
        # Check if memories exist
        memories = rag.get_all_memories()
        if len(memories) < 5:
            print("No memories found. Initializing...")
            rag.add_medical_timeline()
        
        # Test query
        print("\n📝 Test Query:")
        result = rag.query("What should I know about my upcoming 6-month PET scan?")
        print(f"\n{result['answer'][:500]}...\n")
        print(f"✅ Used {len(result['memories_used'])} memories")
        print(f"✅ Used {len(result['vault_sources'])} vault sources")
