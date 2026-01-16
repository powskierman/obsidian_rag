"""
Compatibility shim for moved module.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_module_path = Path(__file__).parent / "src" / "mcp" / "obsidian_rag_unified_mcp.py"
_spec = spec_from_file_location("obsidian_rag_unified_mcp_impl", _module_path)
_module = module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_module)

EMBEDDING_URL = _module.EMBEDDING_URL
GRAPH_SERVICE_URL = getattr(_module, "GRAPH_SERVICE_URL", None)

load_graph = _module.load_graph
search_vault = _module.search_vault
get_vault_statistics = _module.get_vault_statistics

async def query_knowledge_graph(arguments: dict):
    _module.load_graph = load_graph
    return await _module.query_knowledge_graph(arguments)


async def get_entity_info(arguments: dict):
    _module.load_graph = load_graph
    return await _module.get_entity_info(arguments)


async def find_entity_path(arguments: dict):
    _module.load_graph = load_graph
    return await _module.find_entity_path(arguments)


async def search_entities(arguments: dict):
    _module.load_graph = load_graph
    return await _module.search_entities(arguments)


async def get_graph_stats(arguments: dict):
    _module.load_graph = load_graph
    return await _module.get_graph_stats(arguments)


TextContent = _module.TextContent

async def list_tools():
    return await _module.list_tools()


async def call_tool(name: str, arguments: dict):
    try:
        if name in {"obsidian_semantic_search", "obsidian_simple_search", "search_vault"}:
            return await search_vault(arguments)
        if name in {"get_vault_stats", "obsidian_vault_stats"}:
            return await get_vault_statistics(arguments)
        if name in {"obsidian_graph_query", "query_knowledge_graph"}:
            return await query_knowledge_graph(arguments)
        if name == "get_entity_info":
            return await get_entity_info(arguments)
        if name == "find_entity_path":
            return await find_entity_path(arguments)
        if name == "search_entities":
            return await search_entities(arguments)
        if name == "get_graph_stats":
            return await get_graph_stats(arguments)
        return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]


class _AppWrapper:
    def __init__(self, server):
        self._server = server
        self.name = getattr(server, "name", "obsidian-rag-unified")

    async def list_tools(self):
        return await list_tools()

    async def call_tool(self, name: str, arguments: dict):
        return await call_tool(name, arguments)

    def __getattr__(self, name):
        return getattr(self._server, name)


app = _AppWrapper(_module.app)

graph_loaded = getattr(_module, "graph_loaded", False)
querier = getattr(_module, "querier", None)

__all__ = [
    "app",
    "EMBEDDING_URL",
    "GRAPH_SERVICE_URL",
    "graph_loaded",
    "querier",
    "load_graph",
    "search_vault",
    "get_vault_statistics",
    "query_knowledge_graph",
    "get_entity_info",
    "find_entity_path",
    "search_entities",
    "get_graph_stats",
    "list_tools",
    "call_tool",
]

if __name__ == "__main__":
    import asyncio

    asyncio.run(_module.main())
