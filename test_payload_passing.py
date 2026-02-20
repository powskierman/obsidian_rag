import sys
import os
import json
import asyncio
from unittest.mock import patch, MagicMock

# Add src/ to sys.path so we can import services
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Mock the get_memory_manager function instead of patching the module
import src.utils.memory_manager
from unittest.mock import patch, MagicMock

mock_manager = MagicMock()
mock_manager.search_memory.return_value = "Mocked memory context"
src.utils.memory_manager.get_memory_manager = MagicMock(return_value=mock_manager)

from services.api_gateway import app, CascadingRetriever
from fastapi.testclient import TestClient
import httpx

client = TestClient(app)

class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)

def test_extract_query_context():
    from services.api_gateway import _extract_query_context
    entities, mem_ctx = _extract_query_context("testing the bread recipe", include_memory=True)
    print(f"Entities: {entities}")
    print(f"Mem0 Context: {mem_ctx}")
    assert "bread" in entities or "recipe" in entities
    assert "Mocked memory context" in mem_ctx
    print("✅ _extract_query_context works correctly.")

@patch('httpx.AsyncClient.post', new_callable=AsyncMock)
def test_cascading_retriever_payloads(mock_post):
    # Setup mock responses
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}
    mock_post.return_value = mock_resp

    retriever = CascadingRetriever(
        embed_url="http://embed",
        graph_url="http://graph",
        lightrag_url="http://lightrag",
        llm_provider="test_llm"
    )

    async def run_retrieve():
        return await retriever.retrieve(
            "test query", 
            max_results=5, 
            entities=["test", "query"], 
            mem0_context="test mem0 context"
        )
    
    asyncio.run(run_retrieve())

    # Verify payloads
    print(f"mock_post call count: {mock_post.call_count}")
    assert mock_post.call_count >= 3
    
    # Extract the first 3 calls which were launched via gather
    calls = [call.kwargs.get('json') or call.args[1] for call in mock_post.call_args_list[:3]]
    # Since we can't guarantee order if they await, let's find them by 'mode' or similar
    
    graph_payload = next((c for c in calls if c.get('mode') == 'graph'), None)
    vec_payload = next((c for c in calls if 'n_results' in c and 'reranking' in c), None)
    
    assert graph_payload is not None
    assert graph_payload['entities'] == ["test", "query"]
    assert graph_payload['mem0_context'] == "test mem0 context"
    
    assert vec_payload is not None
    assert vec_payload['entities'] == ["test", "query"]
    assert vec_payload['mem0_context'] == "test mem0 context"

    print("✅ CascadingRetriever payloads pass entities and mem0_context correctly.")

@patch('services.api_gateway._post_json', new_callable=AsyncMock)
def test_unified_search_payloads(mock_post_json):
    # Setup mock
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}
    mock_post_json.return_value = mock_resp

    # Test notes mode
    response = client.post("/api/v1/search", json={
        "query": "find medical notes",
        "mode": "notes",
        "llm_knowledge": True
    })
    
    if response.status_code != 200:
        raise AssertionError(f"Expected 200, got {response.status_code}: {response.text}")
    
    # Check what was passed to _post_json
    if mock_post_json.call_count < 1:
        raise AssertionError(f"mock_post_json was not called! Call count is {mock_post_json.call_count}")
    call_args = mock_post_json.call_args_list[0]
    payload = call_args[0][2] # args[2] is the payload usually
    
    assert 'entities' in payload
    assert 'mem0_context' in payload
    assert payload['mem0_context'].startswith("Mocked memory context")

    print("✅ API Gateway /api/v1/search forwards entities and mem0_context to JSON payloads correctly.")

if __name__ == "__main__":
    print("Running Tests...\n")
    try:
        test_extract_query_context()
        test_cascading_retriever_payloads()
        test_unified_search_payloads()
        print("\n🎉 All tests passed successfully!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
