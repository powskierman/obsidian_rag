#!/usr/bin/env python3
"""
Fixed Obsidian RAG MCP Server for Claude Desktop
Corrected tool names and improved error handling
"""

import asyncio
import json
import requests
import os
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.append('/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag')

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError as e:
    print(f"MCP import error: {e}", file=sys.stderr)
    sys.exit(1)

# Service URLs
EMBEDDING_URL = "http://localhost:8000"
LIGHTRAG_URL = "http://localhost:8001"

app = Server("obsidian-rag-fixed")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="obsidian_simple_search",
            description="Search your Obsidian vault using semantic search. Returns top filenames and relevance scores (2 results max).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for your vault"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of results to return (1-3)",
                        "default": 3
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="obsidian_graph_query",
            description="Query your knowledge graph to understand relationships between notes and entities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query for the knowledge graph"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="obsidian_vault_stats",
            description="Get comprehensive statistics about your vault including entity counts and relationships.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    
    try:
        if name == "obsidian_simple_search":
            return await search_vault(arguments)
        elif name == "obsidian_graph_query":
            return await query_knowledge_graph(arguments)
        elif name == "obsidian_vault_stats":
            return await get_vault_statistics(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]

async def search_vault(arguments: dict) -> list[TextContent]:
    """Search vault using semantic search"""
    query = arguments.get("query")
    n_results = min(arguments.get("n_results", 3), 3)  # Cap at 3 to prevent overflow
    
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
        
        if response.status_code == 200:
            results = response.json()
            documents = results.get('documents', [[]])[0]
            metadatas = results.get('metadatas', [[]])[0]
            distances = results.get('distances', [[]])[0]
            
            # Build concise output - just filenames
            output = f"Found {len(documents)} notes for '{query}':\n"
            
            for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                relevance = (1 - dist) * 100
                filename = meta.get('filename', 'unknown')
                output += f"{i}. {filename} ({relevance:.0f}%)\n"
            
            return [TextContent(type="text", text=output)]
        else:
            return [TextContent(type="text", text=f"Search failed: {response.status_code}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Search error: {str(e)}")]

async def query_knowledge_graph(arguments: dict) -> list[TextContent]:
    """Query knowledge graph"""
    query = arguments.get("query")
    
    try:
        response = requests.post(
            f"{LIGHTRAG_URL}/query",
            json={
                "query": query,
                "mode": "graph-local",
                "top_k": 10
            },
            timeout=30
        )
        
        if response.status_code == 200:
            results = response.json()
            answer = results.get('answer', '')
            sources = results.get('sources', [])
            
            output = f"# 🌐 Knowledge Graph Query: {query}\n\n"
            
            if answer:
                output += f"## Analysis\n\n{answer}\n\n"
            
            if sources:
                output += f"## Sources ({len(sources)} documents)\n\n"
                for i, source in enumerate(sources, 1):
                    output += f"{i}. {source}\n"
            
            return [TextContent(type="text", text=output)]
        else:
            return [TextContent(type="text", text=f"Graph query failed: {response.status_code} - {response.text}")]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Graph query error: {str(e)}")]

async def get_vault_statistics(arguments: dict) -> list[TextContent]:
    """Get comprehensive vault statistics"""
    try:
        # Load basic stats
        db_dir = Path('./lightrag_db')
        
        with open(db_dir / 'kv_store_doc_status.json', 'r') as f:
            doc_status = json.load(f)
        
        with open(db_dir / 'kv_store_full_entities.json', 'r') as f:
            entities = json.load(f)
        
        with open(db_dir / 'kv_store_full_relations.json', 'r') as f:
            relations = json.load(f)
        
        output = "# 📊 Vault Statistics\n\n"
        output += f"## Basic Statistics\n\n"
        output += f"- **Total Documents**: {len(doc_status)}\n"
        
        # Count entities
        total_entities = 0
        for entity_data in entities.values():
            total_entities += len(entity_data.get('entity_names', []))
        
        output += f"- **Total Entities**: {total_entities}\n"
        
        # Count relations
        total_relations = 0
        for relation_data in relations.values():
            total_relations += len(relation_data.get('relation_names', []))
        
        output += f"- **Total Relations**: {total_relations}\n\n"
        
        # Service status
        output += f"## Service Status\n\n"
        output += f"- **Embedding Service**: {'✅ Running' if check_service(EMBEDDING_URL) else '❌ Not Available'}\n"
        output += f"- **Graph Service**: {'✅ Running' if check_service(LIGHTRAG_URL) else '❌ Not Available'}\n\n"
        
        # Top entities
        entity_counts = {}
        for doc_id, entity_data in entities.items():
            entity_names = entity_data.get('entity_names', [])
            for entity_name in entity_names:
                entity_counts[entity_name] = entity_counts.get(entity_name, 0) + 1
        
        top_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        output += "## Top Entities\n\n"
        for entity, count in top_entities:
            output += f"- **{entity}**: {count} mentions\n"
        
        return [TextContent(type="text", text=output)]
    
    except Exception as e:
        return [TextContent(type="text", text=f"Stats error: {str(e)}")]

def check_service(url):
    """Check if a service is running"""
    try:
        response = requests.get(f"{url}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

async def main():
    """Run MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())







