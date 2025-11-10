"""
Tests for MCP server endpoints and functionality
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from obsidian_rag_unified_mcp import (
    app,
    search_vault,
    get_vault_statistics,
    query_knowledge_graph,
    get_entity_info,
    find_entity_path,
    search_entities,
    get_graph_stats,
)


class TestMCPServerTools:
    """Test MCP server tool listing"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_tools_basic(self):
        """Test listing available tools"""
        tools = await app.list_tools()

        assert len(tools) >= 2  # At minimum, search and stats
        tool_names = [tool.name for tool in tools]

        # Should always have these tools
        assert 'obsidian_semantic_search' in tool_names
        assert 'obsidian_vault_stats' in tool_names

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_tools_schema(self):
        """Test tool schemas are valid"""
        tools = await app.list_tools()

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
    async def test_query_graph_not_available(self):
        """Test graph query when graph is not available"""
        with patch('obsidian_rag_unified_mcp.load_graph', return_value=False):
            result = await query_knowledge_graph({
                'query': 'What treats lymphoma?'
            })

            assert len(result) == 1
            assert 'Could not load' in result[0].text

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_query_graph_missing_query(self):
        """Test graph query with missing query"""
        with patch('obsidian_rag_unified_mcp.load_graph', return_value=True):
            result = await query_knowledge_graph({})

            assert len(result) == 1
            assert 'required' in result[0].text.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_get_entity_info_missing_name(self):
        """Test entity info with missing name"""
        with patch('obsidian_rag_unified_mcp.load_graph', return_value=True):
            result = await get_entity_info({})

            assert len(result) == 1
            assert 'required' in result[0].text.lower()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_find_entity_path_missing_params(self):
        """Test find path with missing parameters"""
        with patch('obsidian_rag_unified_mcp.load_graph', return_value=True):
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
        with patch('obsidian_rag_unified_mcp.load_graph', return_value=True):
            result = await search_entities({})

            assert len(result) == 1
            assert 'required' in result[0].text.lower()


class TestMCPToolCalls:
    """Test MCP tool call routing"""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_call_unknown_tool(self):
        """Test calling unknown tool"""
        result = await app.call_tool('unknown_tool_name', {})

        assert len(result) == 1
        assert 'Unknown tool' in result[0].text

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('obsidian_rag_unified_mcp.search_vault')
    async def test_call_search_tool_aliases(self, mock_search):
        """Test that search tool aliases work"""
        mock_search.return_value = [MagicMock(text='result')]

        # Test different aliases
        for tool_name in ['obsidian_semantic_search', 'obsidian_simple_search', 'search_vault']:
            result = await app.call_tool(tool_name, {'query': 'test'})
            assert mock_search.called

    @pytest.mark.integration
    @pytest.mark.asyncio
    @patch('obsidian_rag_unified_mcp.get_vault_statistics')
    async def test_call_stats_tool_aliases(self, mock_stats):
        """Test that stats tool aliases work"""
        mock_stats.return_value = [MagicMock(text='stats')]

        for tool_name in ['get_vault_stats', 'obsidian_vault_stats']:
            result = await app.call_tool(tool_name, {})
            assert mock_stats.called

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_call_tool_with_exception(self):
        """Test tool call with exception"""
        with patch('obsidian_rag_unified_mcp.search_vault', side_effect=Exception('Test error')):
            result = await app.call_tool('obsidian_semantic_search', {'query': 'test'})

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
        """Test that graph is lazy-loaded"""
        # Graph should not be loaded until first use
        from obsidian_rag_unified_mcp import graph_loaded, querier

        # Initially should be False
        assert graph_loaded is False or querier is None

    @pytest.mark.integration
    def test_environment_variables_respected(self, monkeypatch):
        """Test that environment variables are used"""
        monkeypatch.setenv('EMBEDDING_SERVICE_URL', 'http://custom:9000')
        monkeypatch.setenv('CLAUDE_GRAPH_SERVICE_URL', 'http://custom:9001')

        # Reimport to pick up env vars
        import importlib
        import obsidian_rag_unified_mcp
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
        tools = await app.list_tools()

        for tool in tools:
            try:
                result = await app.call_tool(tool.name, {})
                # Should return some result, not crash
                assert len(result) > 0
            except Exception as e:
                pytest.fail(f"Tool {tool.name} crashed with empty args: {e}")


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
