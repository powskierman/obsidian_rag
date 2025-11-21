#!/usr/bin/env python3
"""
MCP Server for Claude Knowledge Graph
Enables Claude Desktop, Claude Code, and Cursor to query your knowledge graph
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    print("MCP not available. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

try:
    from claude_graph_builder import ClaudeGraphBuilder, ClaudeGraphQuerier
    GRAPH_AVAILABLE = True
except ImportError:
    print("claude_graph_builder not found. Make sure it's in the same directory.", file=sys.stderr)
    GRAPH_AVAILABLE = False

# Initialize server
app = Server("knowledge-graph")

# Global graph querier (lazy-loaded)
querier = None
graph_loaded = False

def load_graph():
    """Load the knowledge graph"""
    global querier, graph_loaded
    
    if graph_loaded:
        return True
    
    try:
        # Get API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return False
        
        # Get graph file path
        graph_path = os.environ.get("KNOWLEDGE_GRAPH_PATH")
        if not graph_path:
            # Try default locations (check graph_data directory first)
            default_paths = [
                "graph_data/knowledge_graph_full.pkl",
                "graph_data/knowledge_graph_test.pkl",
                "graph_data/knowledge_graph.pkl",
                "knowledge_graph_test.pkl",
                "knowledge_graph_full.pkl",
                "knowledge_graph.pkl"
            ]
            for path in default_paths:
                if Path(path).exists():
                    graph_path = path
                    break
        
        if not graph_path or not Path(graph_path).exists():
            return False
        
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
    """List available knowledge graph tools"""
    
    if not GRAPH_AVAILABLE:
        return []
    
    # Try to load graph
    load_graph()
    
    return [
        Tool(
            name="query_knowledge_graph",
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
                        "description": "Name of the entity to explore (e.g., 'CAR-T Therapy', 'Fusion 360')"
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
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    
    if not GRAPH_AVAILABLE:
        return [TextContent(
            type="text",
            text="❌ Knowledge graph not available. Make sure claude_graph_builder.py is in the same directory."
        )]
    
    # Load graph if not already loaded
    if not load_graph():
        return [TextContent(
            type="text",
            text="❌ Could not load knowledge graph. Make sure:\n"
                 "1. ANTHROPIC_API_KEY is set\n"
                 "2. KNOWLEDGE_GRAPH_PATH points to a valid .pkl file\n"
                 "3. Or knowledge_graph_test.pkl/knowledge_graph_full.pkl exists in graph_data/ or current directory"
        )]
    
    try:
        if name == "query_knowledge_graph":
            query = arguments.get("query", "")
            max_entities = arguments.get("max_entities", 20)
            
            if not query:
                return [TextContent(type="text", text="❌ Query is required")]
            
            answer = querier.query_with_claude(query, max_entities=max_entities)
            return [TextContent(type="text", text=answer)]
        
        elif name == "get_entity_info":
            entity_name = arguments.get("entity_name", "")
            
            if not entity_name:
                return [TextContent(type="text", text="❌ Entity name is required")]
            
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
        
        elif name == "find_entity_path":
            source = arguments.get("source", "")
            target = arguments.get("target", "")
            max_depth = arguments.get("max_depth", 3)
            
            if not source or not target:
                return [TextContent(type="text", text="❌ Both source and target are required")]
            
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
        
        elif name == "search_entities":
            search_term = arguments.get("search_term", "").lower()
            limit = arguments.get("limit", 10)
            
            if not search_term:
                return [TextContent(type="text", text="❌ Search term is required")]
            
            matching_entities = []
            for node in querier.graph.nodes():
                if search_term in node.lower():
                    node_data = dict(querier.graph.nodes[node])
                    matching_entities.append({
                        'name': node,
                        'type': node_data.get('entity_type', 'Unknown'),
                        'connections': querier.graph.degree(node)
                    })
            
            # Sort by connections
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
        
        elif name == "get_graph_stats":
            stats = querier.get_graph_stats()
            
            result = "📊 **Knowledge Graph Statistics:**\n\n"
            result += f"**Total Entities:** {stats['total_nodes']}\n"
            result += f"**Total Relationships:** {stats['total_edges']}\n"
            result += f"**Density:** {stats['density']:.4f}\n"
            result += f"**Connected:** {stats['is_connected']}\n\n"
            result += "**Top 10 Most Connected Entities:**\n"
            for entity in stats['top_entities'][:10]:
                result += f"  • {entity['entity']}: {entity['connections']} connections\n"
            
            return [TextContent(type="text", text=result)]
        
        else:
            return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=f"❌ Error: {str(e)}\n\nPlease check that the graph is loaded correctly."
        )]

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

