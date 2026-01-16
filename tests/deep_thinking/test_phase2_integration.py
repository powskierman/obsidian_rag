"""
Integration test for Phase 2: Reranking
Tests the full Deep Thinking workflow with reranking enabled.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_reranking_integration():
    """
    Test that reranking is properly integrated into the Deep Thinking workflow.
    
    This is a smoke test that verifies:
    1. Reranker can be imported
    2. Supervisor initializes with reranking
    3. Reranking gracefully degrades if sentence-transformers not installed
    """
    from deep_thinking.supervisor import RetrievalSupervisor, RERANKER_AVAILABLE
    
    print("Testing reranking integration...")
    print(f"Reranker available: {RERANKER_AVAILABLE}")
    
    # Test supervisor initialization with reranking enabled
    supervisor = RetrievalSupervisor(
        vector_service_url="http://localhost:8000",
        graph_service_url="http://localhost:8003",
        enable_reranking=True
    )
    
    # Verify reranking state
    if RERANKER_AVAILABLE:
        assert supervisor.enable_reranking == True, "Reranking should be enabled"
        assert supervisor.reranker is not None, "Reranker should be initialized"
        print("✅ Reranking enabled and initialized")
    else:
        assert supervisor.enable_reranking == False, "Reranking should be disabled if library missing"
        assert supervisor.reranker is None, "Reranker should be None if library missing"
        print("⚠️  Reranking disabled (sentence-transformers not installed)")
    
    # Test supervisor with reranking disabled
    supervisor_no_rerank = RetrievalSupervisor(
        vector_service_url="http://localhost:8000",
        graph_service_url="http://localhost:8003",
        enable_reranking=False
    )
    
    assert supervisor_no_rerank.enable_reranking == False, "Reranking should be disabled"
    assert supervisor_no_rerank.reranker is None, "Reranker should be None when disabled"
    print("✅ Reranking can be disabled")
    
    print("\n✅ All integration tests passed!")

if __name__ == "__main__":
    try:
        test_reranking_integration()
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
