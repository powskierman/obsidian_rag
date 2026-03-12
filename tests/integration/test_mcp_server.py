"""
Tests for MCP server endpoints and functionality
"""
import json
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
from starlette.testclient import TestClient

pytest.importorskip("mcp")

# Insert PROJECT_ROOT to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.mcp.obsidian_rag_unified_mcp import (
    app,
    list_tools,
    call_tool,
    search_vault,
    search_with_mode,
    get_vault_statistics,
    query_knowledge_graph,
    get_entity_info,
    find_entity_path,
    search_entities,
    get_graph_stats,
    summarize_url_to_capture,
    summarize_youtube_to_capture,
    apply_existing_tags_frontmatter_only,
    obsidian_unified_query,
    build_streamable_http_app,
)


class TestMCPServerTools:
    """Test MCP server tool listing"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_tools_basic(self):
        """Test listing available tools"""
        tools = await list_tools()

        assert len(tools) >= 2  # At minimum, search and stats
        tool_names = [tool.name for tool in tools]

        # Should always have these tools
        assert 'obsidian_semantic_search' in tool_names
        assert 'obsidian_vault_stats' in tool_names

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_tools_schema(self):
        """Test tool schemas are valid"""
        tools = await list_tools()

        for tool in tools:
            # Each tool should have required fields
            assert hasattr(tool, 'name')
            assert hasattr(tool, 'description')
            assert hasattr(tool, 'inputSchema')

            # Name should not be empty
            assert len(tool.name) > 0

            # Description should be helpful
            assert len(tool.description) > 10

            # Schema should have type
            assert 'type' in tool.inputSchema
            assert tool.inputSchema['type'] == 'object'


class TestMCPHttpSurface:
    @pytest.mark.integration
    def test_http_root_and_health_routes(self):
        http_app = build_streamable_http_app(
            mount_path="/mcp",
            stateless=True,
            auth_mode="none",
            api_key=None,
            public_url="https://example.ngrok-free.dev",
            host="127.0.0.1",
            port=8811,
        )

        with TestClient(http_app) as client:
            root = client.get("/")
            assert root.status_code == 200
            assert root.json()["service"] == "obsidian-rag-unified-mcp"
            assert root.json()["path"] == "/mcp"

            health = client.get("/health")
            assert health.status_code == 200
            assert health.text == "ok"

    @pytest.mark.integration
    def test_http_mcp_requires_streamable_accept_headers(self):
        http_app = build_streamable_http_app(
            mount_path="/mcp",
            stateless=True,
            auth_mode="none",
            api_key=None,
            public_url="https://example.ngrok-free.dev",
            host="127.0.0.1",
            port=8811,
        )

        with TestClient(http_app) as client:
            response = client.get("/mcp")
            assert response.status_code == 406
            assert "text/event-stream" in response.text


class TestSemanticSearch:
    """Test semantic search functionality"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_vault_missing_query(self):
        """Test search with missing query parameter"""
        result = await search_vault({})

        assert len(result) == 1
        assert 'required' in result[0].text.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_search_vault_success(self, mock_post):
        """Test successful vault search"""
        # Mock the embedding service response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'documents': [['Sample content about CAR-T therapy']],
            'metadatas': [[{
                'filename': 'cart_therapy.md',
                'filepath': '/vault/cart_therapy.md'
            }]],
            'distances': [[0.3]]
        }
        mock_post.return_value = mock_response

        result = await search_vault({
            'query': 'CAR-T therapy',
            'n_results': 5
        })

        assert len(result) == 1
        assert 'cart_therapy.md' in result[0].text
        assert '70%' in result[0].text  # relevance score

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_search_vault_connection_error(self, mock_post):
        """Test search with connection error"""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()

        result = await search_vault({
            'query': 'test query'
        })

        assert len(result) == 1
        assert 'Cannot connect' in result[0].text

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_search_vault_no_results(self, mock_post):
        """Test search with no results"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'documents': [[]],
            'metadatas': [[]],
            'distances': [[]]
        }
        mock_post.return_value = mock_response

        result = await search_vault({
            'query': 'nonexistent query'
        })

        assert len(result) == 1
        assert 'No notes found' in result[0].text

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_search_vault_custom_params(self, mock_post):
        """Test search with custom parameters"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'documents': [['Content 1', 'Content 2']],
            'metadatas': [[
                {'filename': 'note1.md', 'filepath': '/vault/note1.md'},
                {'filename': 'note2.md', 'filepath': '/vault/note2.md'}
            ]],
            'distances': [[0.2, 0.4]]
        }
        mock_post.return_value = mock_response

        result = await search_vault({
            'query': 'test',
            'n_results': 2,
            'include_content': True
        })

        assert len(result) == 1
        assert 'note1.md' in result[0].text
        assert 'note2.md' in result[0].text


class TestSearchModeTool:
    """Test mode-based search tool routing"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_mode_missing_query(self):
        result = await search_with_mode({"mode": "hybrid"})
        assert len(result) == 1
        assert "required" in result[0].text.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_mode_invalid_mode(self):
        result = await search_with_mode({"query": "test", "mode": "invalid-mode"})
        assert len(result) == 1
        assert "unsupported mode" in result[0].text.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('src.mcp.obsidian_rag_unified_mcp.requests.post')
    async def test_search_mode_lightrag_maps_to_entities(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"mode": "entities", "answer": "ok"}
        mock_post.return_value = mock_response

        result = await search_with_mode({"query": "lymphoma", "mode": "lightrag", "max_results": 3})
        assert len(result) == 1
        assert "lightrag" in result[0].text.lower()
        assert mock_post.called
        sent_payload = mock_post.call_args.kwargs.get("json", {})
        assert sent_payload.get("mode") == "entities"
        assert sent_payload.get("max_results") == 3

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('src.mcp.obsidian_rag_unified_mcp._run_deep_research_via_gateway', new_callable=AsyncMock)
    async def test_search_mode_deep_research(self, mock_run):
        mock_run.return_value = {
            "mode": "deep-research",
            "result": {"answer": "deep answer"},
            "events": [],
        }
        result = await search_with_mode({"query": "test", "mode": "deep-research"})
        assert len(result) == 1
        assert "deep answer" in result[0].text
        mock_run.assert_awaited_once()


class TestVaultStatistics:
    """Test vault statistics endpoint"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('requests.get')
    async def test_get_vault_stats_success(self, mock_get):
        """Test successful vault stats retrieval"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'total_documents': 100,
            'total_chunks': 500
        }
        mock_get.return_value = mock_response

        result = await get_vault_statistics({})

        assert len(result) == 1
        assert '100' in result[0].text
        assert '500' in result[0].text

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('requests.get')
    async def test_get_vault_stats_error(self, mock_get):
        """Test vault stats with error"""
        mock_get.side_effect = Exception("Connection failed")

        result = await get_vault_statistics({})

        assert len(result) == 1
        assert 'Unable to retrieve' in result[0].text


class TestKnowledgeGraphQueries:
    """Test knowledge graph query functionality"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_query_graph_not_available(self, mock_post):
        """Test graph query when graph is not available"""
        mock_post.side_effect = Exception("Graph service unavailable")
        with patch('src.mcp.obsidian_rag_unified_mcp.load_graph', return_value=False):
            result = await query_knowledge_graph({
                'query': 'What treats lymphoma?'
            })

            assert len(result) == 1
            assert 'Could not load' in result[0].text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_graph_missing_query(self):
        """Test graph query with missing query"""
        with patch('src.mcp.obsidian_rag_unified_mcp.load_graph', return_value=True):
            result = await query_knowledge_graph({})

            assert len(result) == 1
            assert 'required' in result[0].text.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_entity_info_missing_name(self):
        """Test entity info with missing name"""
        with patch('src.mcp.obsidian_rag_unified_mcp.load_graph', return_value=True):
            result = await get_entity_info({})

            assert len(result) == 1
            assert 'required' in result[0].text.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_find_entity_path_missing_params(self):
        """Test find path with missing parameters"""
        with patch('src.mcp.obsidian_rag_unified_mcp.load_graph', return_value=True):
            result = await find_entity_path({
                'source': 'A'
                # Missing 'target'
            })

            assert len(result) == 1
            assert 'required' in result[0].text.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_search_entities_missing_term(self):
        """Test search entities with missing term"""
        with patch('src.mcp.obsidian_rag_unified_mcp.load_graph', return_value=True):
            result = await search_entities({})

            assert len(result) == 1
            assert 'required' in result[0].text.lower()


class TestMCPToolCalls:
    """Test MCP tool call routing"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_call_unknown_tool(self):
        """Test calling unknown tool"""
        result = await call_tool('unknown_tool_name', {})

        assert len(result) == 1
        assert 'Unknown tool' in result[0].text

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('src.mcp.obsidian_rag_unified_mcp.search_vault')
    async def test_call_search_tool_aliases(self, mock_search):
        """Test that search tool aliases work"""
        mock_search.return_value = [MagicMock(text='result')]

        # Test different aliases
        for tool_name in ['obsidian_semantic_search', 'obsidian_simple_search', 'search_vault']:
            result = await call_tool(tool_name, {'query': 'test'})
            assert mock_search.called

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('src.mcp.obsidian_rag_unified_mcp.get_vault_statistics')
    async def test_call_stats_tool_aliases(self, mock_stats):
        """Test that stats tool aliases work"""
        mock_stats.return_value = [MagicMock(text='stats')]

        for tool_name in ['get_vault_stats', 'obsidian_vault_stats']:
            result = await call_tool(tool_name, {})
            assert mock_stats.called

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_call_tool_with_exception(self):
        """Test tool call with exception"""
        with patch('src.mcp.obsidian_rag_unified_mcp.search_vault', side_effect=Exception('Test error')):
            result = await call_tool('obsidian_semantic_search', {'query': 'test'})

            assert len(result) == 1
            assert 'Error' in result[0].text


class TestMCPServerConfiguration:
    """Test MCP server configuration and setup"""

    @pytest.mark.integration
    def test_server_name(self):
        """Test server is properly named"""
        assert app.name == "obsidian-rag-unified"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_graph_lazy_loading(self):
        """Test that graph globals are in a consistent state"""
        from src.mcp.obsidian_rag_unified_mcp import graph_loaded, querier

        if graph_loaded:
            assert querier is not None
        else:
            assert querier is None

    @pytest.mark.integration
    def test_environment_variables_respected(self, monkeypatch):
        """Test that environment variables are used"""
        monkeypatch.setenv('EMBEDDING_SERVICE_URL', 'http://custom:9000')
        monkeypatch.setenv('CLAUDE_GRAPH_SERVICE_URL', 'http://custom:9001')

        # Reimport to pick up env vars
        import importlib
        from src.mcp import obsidian_rag_unified_mcp
        importlib.reload(obsidian_rag_unified_mcp)

        assert obsidian_rag_unified_mcp.EMBEDDING_URL == 'http://custom:9000'
        assert obsidian_rag_unified_mcp.GRAPH_SERVICE_URL == 'http://custom:9001'


class TestMCPErrorHandling:
    """Test error handling across MCP server"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_search_handles_timeout(self, mock_post):
        """Test search handles timeout gracefully"""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()

        result = await search_vault({'query': 'test'})

        assert len(result) == 1
        assert 'error' in result[0].text.lower() or 'timeout' in result[0].text.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('requests.post')
    async def test_search_handles_malformed_response(self, mock_post):
        """Test search handles malformed API response"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # Missing expected fields
        mock_post.return_value = mock_response

        result = await search_vault({'query': 'test'})

        # Should handle gracefully, not crash
        assert len(result) == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_all_tools_handle_empty_args(self):
        """Test that all tools handle empty arguments gracefully"""
        tools = await list_tools()

        for tool in tools:
            try:
                result = await call_tool(tool.name, {})
                # Should return some result, not crash
                assert len(result) > 0
            except Exception as e:
                pytest.fail(f"Tool {tool.name} crashed with empty args: {e}")


class TestMCPGuardrails:
    """Regression coverage for MCP quality guardrails."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch("src.mcp.obsidian_rag_unified_mcp._save_capture_from_text")
    @patch("src.mcp.obsidian_rag_unified_mcp.requests.get")
    async def test_url_summary_formats_health_payload_as_human_readable_bullets(
        self,
        mock_get,
        mock_save_capture,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.text = json.dumps(
            {
                "success": True,
                "data": {
                    "gateway": "healthy",
                    "services": {
                        "embedding": {"status": "healthy", "count": 6881, "url": "http://embedding-service:8000"},
                        "networkx": {"status": "healthy", "nodes": 26895, "edges": 30633},
                        "lightrag": {"status": "healthy", "nodes": 31438, "edges": 34068, "indexed_notes": 1755},
                    },
                },
            }
        )
        mock_get.return_value = mock_response
        mock_save_capture.return_value = ("00_Inbox/_capture/health-test.md", None)

        result = await summarize_url_to_capture(
            {"url": "http://100.110.65.38:4000/api/v1/health", "max_points": 4}
        )

        assert len(result) == 1
        assert "URL summary saved" in result[0].text
        assert "Gateway: ✅ Healthy" in result[0].text
        assert "Embedding service: ✅ Healthy (6,881 items)" in result[0].text
        assert "NetworkX service: ✅ Healthy (26,895 nodes; 30,633 edges)" in result[0].text
        assert "LightRAG service: ✅ Healthy (31,438 nodes; 34,068 edges; 1,755 indexed notes)" in result[0].text

        saved_kwargs = mock_save_capture.call_args.kwargs
        assert saved_kwargs["points"][0] == "Gateway: ✅ Healthy"
        assert "{" not in saved_kwargs["content"]
        assert "}" not in saved_kwargs["content"]
        assert '"success"' not in saved_kwargs["content"]
        assert "embedding-service:8000" not in saved_kwargs["content"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch("src.mcp.obsidian_rag_unified_mcp._save_capture_from_text")
    @patch("src.mcp.obsidian_rag_unified_mcp._fetch_youtube_title")
    @patch("src.mcp.obsidian_rag_unified_mcp._fetch_youtube_transcript")
    @patch("src.mcp.obsidian_rag_unified_mcp._rewrite_points_abstractive")
    async def test_youtube_summary_filters_music_glyphs_and_lyric_repetition(
        self,
        mock_rewrite,
        mock_fetch_transcript,
        mock_fetch_title,
        mock_save_capture,
    ):
        transcript = (
            "♪ [music] la la la la la la la la. "
            "♫ [applause] let it go let it go let it go let it go. "
            "In this video, we explain how to verify Docker services with explicit health checks and startup order. "
            "The key step is to validate gateway, embedding, networkx, and lightrag endpoints before querying. "
            "♪ [music] la la la la la la la la."
        )
        mock_fetch_transcript.return_value = transcript
        mock_rewrite.return_value = (
            [
                "♪ [music] la la la la la la la la.",
                "Verify Docker services correctly with explicit checks and robust ordering.",
                "Ensure all backend APIs including embedding and graph endpoints are fully operational.",
                "♫ [applause] let it go let it go let it go let it go."
            ],
            "This video explains how to ensure the docker services work. It requires validation."
        )
        mock_fetch_title.return_value = "Docker Health Walkthrough"
        mock_save_capture.return_value = ("00_Inbox/_capture/test.md", None)

        result = await summarize_youtube_to_capture(
            {"url": "https://youtu.be/abc123xyz01", "max_points": 2}
        )

        assert len(result) == 1
        assert "YouTube summary saved" in result[0].text
        bullet_lines = [line for line in result[0].text.splitlines() if line.startswith("- ")]
        assert 1 <= len(bullet_lines) <= 2
        assert "la la la la" not in result[0].text.lower()
        assert "♪" not in result[0].text
        assert "♫" not in result[0].text

        saved_kwargs = mock_save_capture.call_args.kwargs
        assert len(saved_kwargs["points"]) <= 2
        assert "la la la la" not in saved_kwargs["content"].lower()
        assert "let it go let it go" not in saved_kwargs["content"].lower()
        assert "♪" not in saved_kwargs["content"]
        assert "♫" not in saved_kwargs["content"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch("src.mcp.obsidian_rag_unified_mcp._collect_existing_tags")
    async def test_existing_tags_only_noop_for_junk_candidates(self, mock_collect_tags, tmp_path, monkeypatch):
        vault_root = tmp_path / "vault"
        capture_dir = vault_root / "00_Inbox" / "_capture"
        capture_dir.mkdir(parents=True, exist_ok=True)
        note_path = capture_dir / "junk-note.md"
        original_text = "This note mentions make each 22 if repeatedly."
        note_path.write_text(original_text, encoding="utf-8")

        monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault_root))
        mock_collect_tags.return_value = {"#make", "#each", "#22", "#if"}

        result = await apply_existing_tags_frontmatter_only(
            {"path": "00_Inbox/_capture/junk-note.md", "max_tags": 5}
        )

        assert len(result) == 1
        assert "No matching existing tags" in result[0].text
        assert note_path.read_text(encoding="utf-8") == original_text

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch("src.mcp.obsidian_rag_unified_mcp.requests.post")
    async def test_unified_query_returns_unknown_when_medical_timeline_is_ungrounded(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "answer": "Your treatment started in January and progressed to remission by spring.",
            "mode": "hybrid",
        }
        mock_post.return_value = mock_response

        result = await obsidian_unified_query(
            {"query": "What is my DLBCL treatment timeline?", "mode": "hybrid"}
        )

        assert len(result) == 1
        assert "Unknown from current notes." in result[0].text
        assert "started in January" not in result[0].text


class TestMCPIntegration:
    """Integration tests for MCP server"""

    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.asyncio
    @patch('requests.post')
    @patch('requests.get')
    async def test_full_search_workflow(self, mock_get, mock_post):
        """Test complete search workflow"""
        # Mock search response
        mock_search_response = MagicMock()
        mock_search_response.status_code = 200
        mock_search_response.json.return_value = {
            'documents': [['Test document']],
            'metadatas': [[{'filename': 'test.md', 'filepath': '/vault/test.md'}]],
            'distances': [[0.5]]
        }
        mock_post.return_value = mock_search_response

        # Mock stats response
        mock_stats_response = MagicMock()
        mock_stats_response.status_code = 200
        mock_stats_response.json.return_value = {
            'total_documents': 10,
            'total_chunks': 50
        }
        mock_get.return_value = mock_stats_response

        # Execute search
        search_result = await search_vault({
            'query': 'test query',
            'n_results': 5
        })
        assert 'test.md' in search_result[0].text

        # Get stats
        stats_result = await get_vault_statistics({})
        assert '10' in stats_result[0].text
