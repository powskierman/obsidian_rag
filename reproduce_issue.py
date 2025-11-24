import os
import sys
from dotenv import load_dotenv

# Add current directory to path
sys.path.append(os.getcwd())

# Load environment variables
load_dotenv()

from deep_thinking.orchestrator import DeepThinkingRAG
from unittest.mock import MagicMock

# Mock Anthropic client to avoid API costs and control response
class MockAnthropic:
    def __init__(self):
        self.messages = MagicMock()
        # Mock response for Policy Agent (always continue or finish)
        # We need to simulate the flow:
        # 1. Planner: Decompose
        # 2. Supervisor: Retrieve (Vector)
        # 3. Policy: Decide (Continue/Finish)
        # 4. Planner: Extend (Web Search?)
        
        # This is hard to mock perfectly without complex logic. 
        # Instead, let's use the REAL client if available, or fail.
        pass

def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found")
        return

    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    
    # Use real service URLs
    vector_url = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
    graph_url = os.getenv("CLAUDE_GRAPH_SERVICE_URL", "http://localhost:8002")
    
    print(f"Connecting to Vector: {vector_url}")
    
    orchestrator = DeepThinkingRAG(client, vector_url, graph_url)
    
    query = "How do I connect a nextion display to an esp32 using esphome"
    print(f"\n❓ Query: {query}\n")
    
    def status_callback(msg, details=None):
        print(f"[{msg}]")
        if details and "plan" in details:
            print(f"  Plan: {len(details['plan'])} steps")
            for step in details['plan']:
                print(f"  - {step['sub_question']} ({step['search_strategy']})")
    
    try:
        result = orchestrator.query(query, max_iterations=5, status_callback=status_callback)
        print("\n✅ Result Generated")
        print(f"Confidence: {result.get('confidence_score')}")
        print("Citations:")
        for cit in result.get('citations', []):
            print(f"- {cit}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
