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

app = _module.app
load_graph = _module.load_graph
search_vault = _module.search_vault
get_vault_statistics = _module.get_vault_statistics
query_knowledge_graph = _module.query_knowledge_graph
get_entity_info = _module.get_entity_info
find_entity_path = _module.find_entity_path
search_entities = _module.search_entities
get_graph_stats = _module.get_graph_stats

__all__ = [
    "app",
    "load_graph",
    "search_vault",
    "get_vault_statistics",
    "query_knowledge_graph",
    "get_entity_info",
    "find_entity_path",
    "search_entities",
    "get_graph_stats",
]

if __name__ == "__main__":
    import asyncio

    asyncio.run(_module.main())
