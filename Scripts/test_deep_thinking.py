import os
import sys
import anthropic
from dotenv import load_dotenv

# Add parent directory to path so we can import deep_thinking
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from deep_thinking.orchestrator import DeepThinkingRAG

# Load environment variables
load_dotenv()

def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env")
        return

    vector_url = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
    graph_url = os.getenv("LIGHTRAG_SERVICE_URL", "http://localhost:8020") # Default to port 8020 if not set, but check docker-compose

    print(f"Using Vector Service: {vector_url}")
    print(f"Using Graph Service: {graph_url}")

    client = anthropic.Anthropic(api_key=api_key)
    
    rag = DeepThinkingRAG(client, vector_url, graph_url)
    
    # Test query
    question = "Review my lymphoma journey using PET scan results and notes."
    print(f"\n❓ Question: {question}\n")
    
    result = rag.query(question, max_iterations=5)
    
    print("\n\n✅ Final Answer:\n")
    print(result["answer"])
    
    print("\n📚 Citations:\n")
    for citation in result["citations"]:
        print(f"- {citation}")

if __name__ == "__main__":
    main()
