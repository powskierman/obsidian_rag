#!/usr/bin/env python3
"""
Unified Obsidian RAG MCP Server for Claude Desktop
Combines enhanced vault search with knowledge graph queries
"""

import asyncio
import json
import requests
import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError as e:
    print(f"MCP import error: {e}", file=sys.stderr)
    sys.exit(1)

# Lazy import for graph builder to avoid read-only filesystem issues
GRAPH_AVAILABLE = None  # Will be determined when needed
def _check_graph_available():
    """Check if graph builder is available (lazy import)"""
    global GRAPH_AVAILABLE
    if GRAPH_AVAILABLE is not None:
        return GRAPH_AVAILABLE
    
    try:
        # Try importing - this may fail if graph_data directory can't be created
        # The claude_graph_builder now handles OSError gracefully, so import should work
        import claude_graph_builder
        GRAPH_AVAILABLE = True
        return True
    except (ImportError, OSError, Exception) as e:
        GRAPH_AVAILABLE = False
        # Only print warning if it's not a read-only filesystem issue (which is expected)
        if "Read-only file system" not in str(e):
            print(f"Warning: Graph features unavailable: {e}", file=sys.stderr)
        return False

# Service URLs
EMBEDDING_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
GRAPH_SERVICE_URL = os.getenv("CLAUDE_GRAPH_SERVICE_URL", "http://localhost:8002")

# Initialize server
app = Server("obsidian-rag-unified")

# Global graph querier (lazy-loaded)
querier = None
graph_loaded = False

def load_graph():
    """Load the knowledge graph"""
    global querier, graph_loaded
    
    if graph_loaded:
        return True
    
    # Lazy import check
    if not _check_graph_available():
        return False
    
    # Import here to avoid read-only filesystem issues at module load
    from claude_graph_builder import ClaudeGraphBuilder, ClaudeGraphQuerier
    
    try:
        # Get API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return False
        
        # Get graph file path
        graph_path = os.environ.get("KNOWLEDGE_GRAPH_PATH")
        if not graph_path:
            # Try default locations - use absolute paths based on script location
            script_dir = Path(__file__).parent.absolute()
            default_paths = [
                script_dir / "graph_data" / "knowledge_graph_full.pkl",
                script_dir / "graph_data" / "knowledge_graph_test.pkl",
                script_dir / "graph_data" / "knowledge_graph.pkl",
                script_dir / "knowledge_graph_full.pkl",
                script_dir / "knowledge_graph_test.pkl",
                script_dir / "knowledge_graph.pkl",
                # Also try relative paths (for backward compatibility)
                Path("graph_data/knowledge_graph_full.pkl"),
                Path("graph_data/knowledge_graph_test.pkl"),
                Path("graph_data/knowledge_graph.pkl"),
                Path("knowledge_graph_full.pkl"),
                Path("knowledge_graph_test.pkl"),
                Path("knowledge_graph.pkl")
            ]
            for path in default_paths:
                if path.exists():
                    graph_path = str(path.absolute())
                    break
        
        if not graph_path:
            return False
        
        # Convert to absolute path if relative
        graph_path_obj = Path(graph_path)
        if not graph_path_obj.is_absolute():
            # If relative, try from script directory
            script_dir = Path(__file__).parent.absolute()
            graph_path_obj = script_dir / graph_path
        
        if not graph_path_obj.exists():
            print(f"Graph file not found: {graph_path_obj}", file=sys.stderr)
            return False
        
        graph_path = str(graph_path_obj.absolute())
        
        # Load graph
        builder = ClaudeGraphBuilder(api_key=api_key)
        builder.load_graph(graph_path)
        querier = ClaudeGraphQuerier(builder, api_key=api_key)
        graph_loaded = True
        return True
        
    except Exception as e:
        print(f"Error loading graph: {e}", file=sys.stderr)
        return False

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools"""
    
    tools = [
        # Enhanced Vault Search (unique name to distinguish from Docker toolkit)
        Tool(
            name="obsidian_semantic_search",
            description="Search your Obsidian vault using SEMANTIC SEARCH (not text search). Returns top matching notes with content snippets and relevance scores (5-10 results). This uses ChromaDB embeddings for intelligent search. Use this for finding information by meaning, not just keywords.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for your vault (e.g., 'CAR-T therapy', 'Home Assistant setup', 'ESP32 projects')"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return (1-10, default: 5)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    },
                    "include_content": {
                        "type": "boolean",
                        "description": "Include content snippets in results (default: true)",
                        "default": True
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="obsidian_vault_stats",
            description="Get statistics about your vault including total documents, entities, and relationships.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]
    
    # Add graph tools if available (lazy check)
    if _check_graph_available():
        # Try to load graph (but don't fail if it can't load)
        try:
            load_graph()  # Try to load graph
        except Exception:
            pass  # Graph tools won't be added if load fails
        
        if graph_loaded:
            tools.extend([
                Tool(
                    name="obsidian_graph_query",
                    description="Query your knowledge graph using Claude's reasoning. Ask questions about entities, relationships, and connections in your vault. Returns comprehensive answers based on graph structure.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Your question about the knowledge graph (e.g., 'What treatments are mentioned?', 'How does CAR-T relate to lymphoma?')"
                            },
                            "max_entities": {
                                "type": "integer",
                                "description": "Maximum number of entities to consider (default: 20)",
                                "default": 20
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_entity_info",
                    description="Get detailed information about a specific entity in the knowledge graph, including its type, properties, and all relationships.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "entity_name": {
                                "type": "string",
                                "description": "Name of the entity to explore (e.g., 'CAR-T Therapy', 'Home Assistant')"
                            }
                        },
                        "required": ["entity_name"]
                    }
                ),
                Tool(
                    name="find_entity_path",
                    description="Find connection paths between two entities in the knowledge graph. Shows how entities relate to each other.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Source entity name"
                            },
                            "target": {
                                "type": "string",
                                "description": "Target entity name"
                            },
                            "max_depth": {
                                "type": "integer",
                                "description": "Maximum path depth to search (default: 3)",
                                "default": 3
                            }
                        },
                        "required": ["source", "target"]
                    }
                ),
                Tool(
                    name="search_entities",
                    description="Search for entities in the knowledge graph by name. Returns matching entities with their types and connection counts.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "search_term": {
                                "type": "string",
                                "description": "Search term to find entities (e.g., 'treatment', 'CAR-T', '3D printing')"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of results (default: 10)",
                                "default": 10
                            }
                        },
                        "required": ["search_term"]
                    }
                ),
                Tool(
                    name="get_graph_stats",
                    description="Get statistics about the knowledge graph including total entities, relationships, density, and top connected entities.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ])
    
    return tools

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    
    try:
        if name == "obsidian_semantic_search" or name == "obsidian_simple_search" or name == "search_vault":
            # Support multiple names for compatibility
            return await search_vault(arguments)
        elif name == "get_vault_stats" or name == "obsidian_vault_stats":
            # Support both names for compatibility
            return await get_vault_statistics(arguments)
        elif name == "obsidian_graph_query" or name == "query_knowledge_graph":
            # Support both names for compatibility
            return await query_knowledge_graph(arguments)
        elif name == "get_entity_info":
            return await get_entity_info(arguments)
        elif name == "find_entity_path":
            return await find_entity_path(arguments)
        elif name == "search_entities":
            return await search_entities(arguments)
        elif name == "get_graph_stats":
            return await get_graph_stats(arguments)
        else:
            return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

async def search_vault(arguments: dict) -> list[TextContent]:
    """Enhanced vault search with better results"""
    query = arguments.get("query", "")
    n_results = min(max(arguments.get("n_results", 5), 1), 10)  # Clamp between 1-10
    include_content = arguments.get("include_content", True)
    
    if not query:
        return [TextContent(type="text", text="❌ Query is required")]
    
    try:
        response = requests.post(
            f"{EMBEDDING_URL}/query",
            json={
                "query": query,
                "n_results": n_results,
                "reranking": True,
                "deduplicate": True
            },
            timeout=15
        )
        
        if response.status_code != 200:
            return [TextContent(
                type="text",
                text=f"❌ Search failed: {response.status_code}\n"
                     f"Make sure the embedding service is running at {EMBEDDING_URL}"
            )]
        
        results = response.json()
        documents = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        distances = results.get('distances', [[]])[0]
        
        if not documents:
            return [TextContent(
                type="text",
                text=f"🔍 No notes found matching '{query}'"
            )]
        
        # Build enhanced output
        output = f"🔍 **Found {len(documents)} note(s) for '{query}':**\n\n"
        
        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
            relevance = (1 - dist) * 100 if dist < 1 else abs(dist) * 100
            relevance = min(100, max(0, relevance))
            filename = meta.get('filename', 'unknown')
            filepath = meta.get('filepath', 'unknown')
            
            output += f"**{i}. {filename}** ({relevance:.0f}% relevant)\n"
            output += f"   📁 {filepath}\n"
            
            if include_content:
                # Show first 300 chars of content
                snippet = doc[:300] + "..." if len(doc) > 300 else doc
                output += f"   📄 {snippet}\n"
            
            output += "\n"
        
        return [TextContent(type="text", text=output)]
    
    except requests.exceptions.ConnectionError:
        return [TextContent(
            type="text",
            text=f"❌ Cannot connect to embedding service at {EMBEDDING_URL}\n"
                 f"Make sure the service is running: docker-compose up embedding-service"
        )]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Search error: {str(e)}")]

async def get_vault_statistics(arguments: dict) -> list[TextContent]:
    """Get vault statistics"""
    try:
        # Try embedding service stats
        try:
            stats_response = requests.get(f"{EMBEDDING_URL}/stats", timeout=5)
            if stats_response.status_code == 200:
                stats = stats_response.json()
                output = "📊 **Vault Statistics:**\n\n"
                output += f"**Total Documents:** {stats.get('total_documents', 0):,}\n"
                output += f"**Total Chunks:** {stats.get('total_chunks', 0):,}\n"
                return [TextContent(type="text", text=output)]
        except:
            pass
        
        # Fallback
        return [TextContent(
            type="text",
            text="📊 **Vault Statistics:**\n\n"
                 "Unable to retrieve statistics. Make sure the embedding service is running."
        )]
    
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Stats error: {str(e)}")]

async def query_knowledge_graph(arguments: dict) -> list[TextContent]:
    """Query knowledge graph"""
    if not GRAPH_AVAILABLE:
        return [TextContent(
            type="text",
            text="❌ Knowledge graph not available. claude_graph_builder.py not found."
        )]
    
    if not load_graph():
        return [TextContent(
            type="text",
            text="❌ Could not load knowledge graph. Make sure:\n"
                 "1. ANTHROPIC_API_KEY is set\n"
                 "2. KNOWLEDGE_GRAPH_PATH points to a valid .pkl file\n"
                 "3. Or knowledge_graph_full.pkl exists in graph_data/"
        )]
    
    query = arguments.get("query", "")
    max_entities = arguments.get("max_entities", 20)
    
    if not query:
        return [TextContent(type="text", text="❌ Query is required")]
    
    try:
        answer = querier.query_with_claude(query, max_entities=max_entities)
        return [TextContent(type="text", text=answer)]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Graph query error: {str(e)}")]

async def get_entity_info(arguments: dict) -> list[TextContent]:
    """Get entity information"""
    if not load_graph():
        return [TextContent(type="text", text="❌ Graph not loaded")]
    
    entity_name = arguments.get("entity_name", "")
    if not entity_name:
        return [TextContent(type="text", text="❌ Entity name is required")]
    
    try:
        neighborhood = querier.get_entity_neighborhood(entity_name)
        
        if not neighborhood.get('found', True):
            return [TextContent(
                type="text",
                text=f"❌ Entity '{entity_name}' not found in graph"
            )]
        
        result = f"📍 **Entity:** {neighborhood['entity']}\n"
        result += f"**Type:** {neighborhood['properties'].get('entity_type', 'Unknown')}\n\n"
        
        if neighborhood.get('outgoing'):
            result += "**Outgoing Relationships:**\n"
            for rel in neighborhood['outgoing'][:10]:
                result += f"  → {rel['relationship']} → {rel['target']}\n"
            result += "\n"
        
        if neighborhood.get('incoming'):
            result += "**Incoming Relationships:**\n"
            for rel in neighborhood['incoming'][:10]:
                result += f"  ← {rel['relationship']} ← {rel['source']}\n"
        
        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

async def find_entity_path(arguments: dict) -> list[TextContent]:
    """Find path between entities"""
    if not load_graph():
        return [TextContent(type="text", text="❌ Graph not loaded")]
    
    source = arguments.get("source", "")
    target = arguments.get("target", "")
    max_depth = arguments.get("max_depth", 3)
    
    if not source or not target:
        return [TextContent(type="text", text="❌ Both source and target are required")]
    
    try:
        paths = querier.find_paths(source, target, max_depth=max_depth)
        
        if not paths:
            return [TextContent(
                type="text",
                text=f"❌ No path found between '{source}' and '{target}'"
            )]
        
        result = f"🛤️  **Found {len(paths)} path(s) between '{source}' and '{target}':**\n\n"
        for i, path in enumerate(paths[:5], 1):
            result += f"{i}. {' → '.join(path)}\n"
        
        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

async def search_entities(arguments: dict) -> list[TextContent]:
    """Search entities"""
    if not load_graph():
        return [TextContent(type="text", text="❌ Graph not loaded")]
    
    search_term = arguments.get("search_term", "").lower()
    limit = arguments.get("limit", 10)
    
    if not search_term:
        return [TextContent(type="text", text="❌ Search term is required")]
    
    try:
        matching_entities = []
        for node in querier.graph.nodes():
            if search_term in node.lower():
                node_data = dict(querier.graph.nodes[node])
                matching_entities.append({
                    'name': node,
                    'type': node_data.get('entity_type', 'Unknown'),
                    'connections': querier.graph.degree(node)
                })
        
        matching_entities.sort(key=lambda x: x['connections'], reverse=True)
        
        if not matching_entities:
            return [TextContent(
                type="text",
                text=f"❌ No entities found matching '{search_term}'"
            )]
        
        result = f"🔍 **Found {len(matching_entities)} entity(ies) matching '{search_term}':**\n\n"
        for entity in matching_entities[:limit]:
            result += f"• **{entity['name']}** ({entity['type']}) - {entity['connections']} connections\n"
        
        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

async def get_graph_stats(arguments: dict) -> list[TextContent]:
    """Get graph statistics"""
    if not load_graph():
        return [TextContent(type="text", text="❌ Graph not loaded")]
    
    try:
        stats = querier.get_graph_stats()
        
        result = "📊 **Knowledge Graph Statistics:**\n\n"
        result += f"**Total Entities:** {stats['total_nodes']:,}\n"
        result += f"**Total Relationships:** {stats['total_edges']:,}\n"
        result += f"**Density:** {stats['density']:.4f}\n"
        result += f"**Connected:** {stats['is_connected']}\n\n"
        result += "**Top 10 Most Connected Entities:**\n"
        for entity in stats['top_entities'][:10]:
            result += f"  • {entity['entity']}: {entity['connections']} connections\n"
        
        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error: {str(e)}")]

async def main():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())

