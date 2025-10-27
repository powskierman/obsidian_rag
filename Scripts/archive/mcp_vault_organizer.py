#!/usr/bin/env python3
"""
MCP-Enhanced Vault Organization Tool
Uses Obsidian MCP and LightRAG services for intelligent organization
"""

import asyncio
import json
import requests
import sys
from pathlib import Path
from collections import defaultdict, Counter

# MCP Integration
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("⚠️  MCP not available - install with: pip install mcp")

# Service URLs
EMBEDDING_URL = "http://localhost:8000"
LIGHTRAG_URL = "http://localhost:8001"
OLLAMA_URL = "http://localhost:11434"

class MCPVaultOrganizer:
    """Enhanced vault organizer using MCP services"""
    
    def __init__(self):
        self.mcp_server = None
        self.services_available = self.check_services()
    
    def check_services(self):
        """Check which services are available"""
        services = {
            'embedding': False,
            'lightrag': False,
            'ollama': False,
            'mcp': MCP_AVAILABLE
        }
        
        # Check embedding service
        try:
            response = requests.get(f"{EMBEDDING_URL}/health", timeout=2)
            services['embedding'] = response.status_code == 200
        except:
            pass
        
        # Check LightRAG service
        try:
            response = requests.get(f"{LIGHTRAG_URL}/health", timeout=2)
            services['lightrag'] = response.status_code == 200
        except:
            pass
        
        # Check Ollama
        try:
            response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
            services['ollama'] = response.status_code == 200
        except:
            pass
        
        return services
    
    def print_service_status(self):
        """Print status of available services"""
        print("╔════════════════════════════════════════════════════════════╗")
        print("║                    Service Status                         ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print()
        
        for service, available in self.services_available.items():
            status = "✅ Available" if available else "❌ Not Available"
            print(f"   {service.upper():12s}: {status}")
        
        print()
        
        if not any(self.services_available.values()):
            print("⚠️  No services available. Start services with:")
            print("   ./Scripts/docker_start.sh")
            return False
        
        return True
    
    def search_vault_mcp(self, query, n_results=10):
        """Search vault using MCP integration"""
        if not self.services_available['embedding']:
            return None
        
        try:
            response = requests.post(
                f"{EMBEDDING_URL}/query",
                json={
                    "query": query,
                    "n_results": n_results,
                    "reranking": True,
                    "deduplicate": True
                },
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"❌ Vault search failed: {e}")
        
        return None
    
    def query_graph_mcp(self, query, mode="graph-local"):
        """Query knowledge graph using MCP integration"""
        if not self.services_available['lightrag']:
            return None
        
        try:
            response = requests.post(
                f"{LIGHTRAG_URL}/query",
                json={
                    "query": query,
                    "mode": mode,
                    "top_k": 20
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"❌ Graph query failed: {e}")
        
        return None
    
    def analyze_topic_with_mcp(self, topic):
        """Analyze a topic using both vector and graph search"""
        print(f"🔍 Analyzing topic: {topic}")
        print()
        
        # Vector search
        print("📄 Vector Search Results:")
        vector_results = self.search_vault_mcp(topic, n_results=10)
        
        if vector_results:
            documents = vector_results.get('documents', [[]])[0]
            metadatas = vector_results.get('metadatas', [[]])[0]
            distances = vector_results.get('distances', [[]])[0]
            
            for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                relevance = (1 - dist) * 100
                filename = meta.get('filename', 'unknown')
                print(f"   {i:2d}. {filename} ({relevance:.0f}% relevant)")
        else:
            print("   No vector results found")
        
        print()
        
        # Graph search
        print("🌐 Graph Search Results:")
        graph_results = self.query_graph_mcp(topic, mode="graph-local")
        
        if graph_results:
            answer = graph_results.get('answer', '')
            sources = graph_results.get('sources', [])
            
            if answer:
                print(f"   Summary: {answer[:200]}...")
            
            if sources:
                print(f"   Sources: {len(sources)} documents")
                for source in sources[:5]:
                    print(f"   • {source}")
        else:
            print("   No graph results found")
        
        print()
        return vector_results, graph_results
    
    def suggest_organization_with_ai(self, topic):
        """Use AI to suggest organization strategy for a topic"""
        print(f"🤖 AI Organization Suggestions for: {topic}")
        print()
        
        # Get comprehensive analysis
        vector_results, graph_results = self.analyze_topic_with_mcp(topic)
        
        # Combine insights
        suggestions = []
        
        if vector_results:
            documents = vector_results.get('documents', [[]])[0]
            metadatas = vector_results.get('metadatas', [[]])[0]
            
            # Analyze document patterns
            filenames = [meta.get('filename', '') for meta in metadatas]
            filename_patterns = Counter()
            
            for filename in filenames:
                # Extract patterns from filenames
                if 'setup' in filename.lower():
                    filename_patterns['Setup/Configuration'] += 1
                elif 'project' in filename.lower():
                    filename_patterns['Projects'] += 1
                elif 'guide' in filename.lower() or 'tutorial' in filename.lower():
                    filename_patterns['Guides/Tutorials'] += 1
                elif 'note' in filename.lower() or 'moc' in filename.lower():
                    filename_patterns['Notes/MOCs'] += 1
                else:
                    filename_patterns['General'] += 1
            
            suggestions.append("📁 Suggested Folder Structure:")
            for pattern, count in filename_patterns.most_common():
                suggestions.append(f"   • {pattern}: {count} files")
        
        if graph_results:
            sources = graph_results.get('sources', [])
            if sources:
                suggestions.append(f"\n🔗 Related Topics ({len(sources)} connections):")
                for source in sources[:5]:
                    suggestions.append(f"   • {source}")
        
        # AI-powered recommendations
        suggestions.extend([
            "\n💡 AI Recommendations:",
            "   1. Create topic-specific MOC file",
            "   2. Group related notes by subtopic",
            "   3. Add cross-references to related areas",
            "   4. Consider creating project folders for active work",
            "   5. Archive completed or outdated content"
        ])
        
        for suggestion in suggestions:
            print(suggestion)
        
        print()
        return suggestions
    
    def interactive_organization(self):
        """Interactive organization session using MCP services"""
        print("╔════════════════════════════════════════════════════════════╗")
        print("║              MCP-Enhanced Vault Organization              ║")
        print("╚════════════════════════════════════════════════════════════╝")
        print()
        
        if not self.print_service_status():
            return
        
        print("🎯 Available Commands:")
        print("   1. analyze <topic>     - Analyze a specific topic")
        print("   2. suggest <topic>     - Get AI organization suggestions")
        print("   3. search <query>      - Search vault content")
        print("   4. graph <query>       - Query knowledge graph")
        print("   5. status              - Show service status")
        print("   6. quit                - Exit")
        print()
        
        while True:
            try:
                command = input("🔍 Enter command: ").strip().lower()
                
                if command == "quit":
                    print("👋 Goodbye!")
                    break
                elif command == "status":
                    self.print_service_status()
                elif command.startswith("analyze "):
                    topic = command[8:].strip()
                    if topic:
                        self.analyze_topic_with_mcp(topic)
                elif command.startswith("suggest "):
                    topic = command[8:].strip()
                    if topic:
                        self.suggest_organization_with_ai(topic)
                elif command.startswith("search "):
                    query = command[7:].strip()
                    if query:
                        results = self.search_vault_mcp(query)
                        if results:
                            print(f"📄 Found {len(results.get('documents', [[]])[0])} results")
                        else:
                            print("❌ No results found")
                elif command.startswith("graph "):
                    query = command[6:].strip()
                    if query:
                        results = self.query_graph_mcp(query)
                        if results:
                            print(f"🌐 Graph query completed")
                        else:
                            print("❌ Graph query failed")
                else:
                    print("❓ Unknown command. Type 'quit' to exit.")
                
                print()
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

def create_mcp_tools():
    """Create MCP tools for vault organization"""
    
    if not MCP_AVAILABLE:
        print("❌ MCP not available")
        return None
    
    app = Server("obsidian-vault-organizer")
    
    @app.list_tools()
    async def list_tools() -> list[Tool]:
        """List available organization tools"""
        return [
            Tool(
                name="analyze_topic",
                description="Analyze a topic using both vector and graph search to understand content patterns and relationships",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "The topic to analyze (e.g., 'Home Assistant', 'Swift development')"
                        }
                    },
                    "required": ["topic"]
                }
            ),
            Tool(
                name="suggest_organization",
                description="Get AI-powered organization suggestions for a specific topic including folder structure and MOC recommendations",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "The topic to get organization suggestions for"
                        }
                    },
                    "required": ["topic"]
                }
            ),
            Tool(
                name="search_vault",
                description="Search your vault using semantic search for specific content",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "n_results": {
                            "type": "integer",
                            "description": "Number of results (1-20)",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="query_graph",
                description="Query the knowledge graph for relationships and connections",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Graph query"
                        },
                        "mode": {
                            "type": "string",
                            "description": "Query mode: graph-local, graph-global, graph-hybrid",
                            "default": "graph-local"
                        }
                    },
                    "required": ["query"]
                }
            )
        ]
    
    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls"""
        organizer = MCPVaultOrganizer()
        
        try:
            if name == "analyze_topic":
                topic = arguments.get("topic")
                vector_results, graph_results = organizer.analyze_topic_with_mcp(topic)
                
                output = f"# 📊 Topic Analysis: {topic}\n\n"
                
                if vector_results:
                    documents = vector_results.get('documents', [[]])[0]
                    metadatas = vector_results.get('metadatas', [[]])[0]
                    distances = vector_results.get('distances', [[]])[0]
                    
                    output += "## 📄 Vector Search Results\n\n"
                    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                        relevance = (1 - dist) * 100
                        filename = meta.get('filename', 'unknown')
                        output += f"{i}. **{filename}** ({relevance:.0f}% relevant)\n"
                
                if graph_results:
                    answer = graph_results.get('answer', '')
                    sources = graph_results.get('sources', [])
                    
                    output += "\n## 🌐 Graph Search Results\n\n"
                    if answer:
                        output += f"**Summary:** {answer}\n\n"
                    if sources:
                        output += f"**Sources:** {len(sources)} documents\n"
                
                return [TextContent(type="text", text=output)]
            
            elif name == "suggest_organization":
                topic = arguments.get("topic")
                suggestions = organizer.suggest_organization_with_ai(topic)
                
                output = f"# 🗂️ Organization Suggestions: {topic}\n\n"
                output += "\n".join(suggestions)
                
                return [TextContent(type="text", text=output)]
            
            elif name == "search_vault":
                query = arguments.get("query")
                n_results = arguments.get("n_results", 10)
                
                results = organizer.search_vault_mcp(query, n_results)
                
                if results:
                    documents = results.get('documents', [[]])[0]
                    metadatas = results.get('metadatas', [[]])[0]
                    distances = results.get('distances', [[]])[0]
                    
                    output = f"# 🔍 Vault Search: {query}\n\n"
                    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                        relevance = (1 - dist) * 100
                        filename = meta.get('filename', 'unknown')
                        output += f"{i}. **{filename}** ({relevance:.0f}% relevant)\n"
                        output += f"   {doc[:200]}...\n\n"
                    
                    return [TextContent(type="text", text=output)]
                else:
                    return [TextContent(type="text", text=f"No results found for: {query}")]
            
            elif name == "query_graph":
                query = arguments.get("query")
                mode = arguments.get("mode", "graph-local")
                
                results = organizer.query_graph_mcp(query, mode)
                
                if results:
                    answer = results.get('answer', '')
                    sources = results.get('sources', [])
                    
                    output = f"# 🌐 Graph Query: {query}\n\n"
                    output += f"**Mode:** {mode}\n\n"
                    
                    if answer:
                        output += f"**Answer:** {answer}\n\n"
                    
                    if sources:
                        output += f"**Sources:** {len(sources)} documents\n"
                        for source in sources[:10]:
                            output += f"- {source}\n"
                    
                    return [TextContent(type="text", text=output)]
                else:
                    return [TextContent(type="text", text=f"Graph query failed for: {query}")]
            
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
        
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    return app

def main():
    """Main function"""
    
    if len(sys.argv) > 1 and sys.argv[1] == "--mcp-server":
        # Run as MCP server
        if not MCP_AVAILABLE:
            print("❌ MCP not available. Install with: pip install mcp")
            sys.exit(1)
        
        app = create_mcp_tools()
        if app:
            print("🚀 Starting MCP Vault Organizer Server...")
            asyncio.run(stdio_server(app))
    else:
        # Run interactive mode
        organizer = MCPVaultOrganizer()
        organizer.interactive_organization()

if __name__ == "__main__":
    main()






