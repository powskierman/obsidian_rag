#!/usr/bin/env python3
"""
Unified Obsidian RAG MCP Server for ChatGPT Desktop
Combines enhanced vault search with knowledge graph queries.
"""

import argparse
import asyncio
import json
import logging
import os
import pickle
import re
import secrets
import sys
import time
from pathlib import Path

import requests
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parents[2] / ".env"
    load_dotenv(_env_path, override=False)
except Exception:
    pass

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

# Graph availability
GRAPH_AVAILABLE = NETWORKX_AVAILABLE
logger = logging.getLogger(__name__)

# Service URLs
EMBEDDING_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
GRAPH_SERVICE_URL = os.getenv("CLAUDE_GRAPH_SERVICE_URL", "http://localhost:8002")
MAX_NOTE_CHARS = int(os.getenv("MCP_MAX_NOTE_CHARS", "200000"))
PDF_MAX_PAGES = int(os.getenv("MCP_PDF_MAX_PAGES", "25"))
MAX_ATTACHMENTS_PER_NOTE = int(os.getenv("MCP_MAX_ATTACHMENTS_PER_NOTE", "3"))

def _service_headers() -> dict:
    api_key = os.getenv("OBSIDIAN_RAG_API_KEY")
    if not api_key:
        return {}
    return {"X-API-Key": api_key}


def _get_vault_root() -> Path | None:
    vault_root = os.getenv("OBSIDIAN_VAULT_PATH")
    if not vault_root:
        return None
    return Path(vault_root).expanduser().resolve()


def _resolve_vault_path(raw_path: str) -> tuple[Path | None, str | None]:
    if not raw_path:
        return None, "❌ Path is required"

    vault_root = _get_vault_root()
    if vault_root is None:
        return None, "❌ OBSIDIAN_VAULT_PATH is not set"

    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = vault_root / candidate

    try:
        resolved = candidate.resolve()
    except Exception:
        return None, "❌ Invalid path"

    try:
        resolved.relative_to(vault_root)
    except ValueError:
        return None, "❌ Path is outside the vault root"

    if not resolved.exists():
        return None, "❌ File not found"

    return resolved, None


def _read_text_file(resolved: Path, max_chars: int) -> str:
    with open(resolved, "r", encoding="utf-8", errors="replace") as handle:
        content = handle.read(max_chars + 1)
    if len(content) > max_chars:
        content = content[:max_chars] + "\n\n[TRUNCATED]"
    return content


def _extract_pdf_text(resolved: Path, max_pages: int, max_chars: int) -> tuple[str, bool]:
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError("pypdf is not installed in this environment") from e

    reader = PdfReader(str(resolved))
    pages_to_read = min(len(reader.pages), max_pages)
    parts = []
    total_chars = 0
    truncated = False

    for idx in range(pages_to_read):
        page_text = reader.pages[idx].extract_text() or ""
        if not page_text:
            continue
        remaining = max_chars - total_chars
        if remaining <= 0:
            truncated = True
            break
        if len(page_text) > remaining:
            parts.append(page_text[:remaining])
            truncated = True
            break
        parts.append(page_text)
        total_chars += len(page_text)

    content = "\n\n".join(parts)
    if truncated:
        content = content + "\n\n[TRUNCATED]"
    return content, truncated


def _extract_pdf_refs(note_text: str) -> list[str]:
    refs = re.findall(r"!\[\[([^\]]+)\]\]", note_text)
    cleaned = []
    for ref in refs:
        part = ref.split("|", 1)[0]
        part = part.split("#", 1)[0]
        part = part.strip()
        if part.lower().endswith(".pdf"):
            cleaned.append(part)
    return cleaned


def _resolve_attachment_path(note_path: Path, attachment_ref: str) -> tuple[Path | None, str | None]:
    vault_root = _get_vault_root()
    if vault_root is None:
        return None, "❌ OBSIDIAN_VAULT_PATH is not set"

    attachment_path = Path(attachment_ref)
    candidates = []
    if attachment_path.is_absolute():
        candidates.append(attachment_path)
    else:
        candidates.append(note_path.parent / attachment_ref)
        candidates.append(vault_root / attachment_ref)

    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except Exception:
            continue
        try:
            resolved.relative_to(vault_root)
        except ValueError:
            continue
        if resolved.exists():
            return resolved, None

    target_name = attachment_path.name
    try:
        for root, _, files in os.walk(vault_root):
            if target_name in files:
                found = Path(root) / target_name
                return found.resolve(), None
    except Exception:
        pass

    return None, "❌ Attachment not found"

# Initialize server
app = Server("obsidian-rag-unified")

class GraphQuerier:
    """Query the knowledge graph using OpenAI or Gemini for synthesis."""

    def __init__(self, graph):
        self.graph = graph
        
        self.gemini_key = os.environ.get("GEMINI_API_KEY")
        self.openai_key = os.environ.get("OPENAI_API_KEY")
        
        # 1. Check for explicit provider configuration
        preferred_provider = os.environ.get("MCP_GRAPH_PROVIDER", "").lower()
        
        if preferred_provider == "gemini":
            if not self.gemini_key:
                raise ValueError("MCP_GRAPH_PROVIDER is 'gemini' but GEMINI_API_KEY is missing.")
            if not GENAI_AVAILABLE:
                raise ValueError("MCP_GRAPH_PROVIDER is 'gemini' but google-generativeai is not installed.")
            self.provider = "gemini"
            
        elif preferred_provider == "openai":
            if not self.openai_key:
                raise ValueError("MCP_GRAPH_PROVIDER is 'openai' but OPENAI_API_KEY is missing.")
            self.provider = "openai"
            
        else:
            # 2. Auto-detect if no preference set
            if self.gemini_key and GENAI_AVAILABLE:
                self.provider = "gemini"
            elif self.openai_key:
                self.provider = "openai"
            else:
                self.provider = "none"
        
        # Configure the selected provider
        if self.provider == "gemini":
            genai.configure(api_key=self.gemini_key)
            self.model = os.environ.get("GEMINI_MODEL", "gemini-1.5-pro-latest")
        else:
            # Default to OpenAI logic (or fallback)
            self.model = os.environ.get("OPENAI_MODEL", "gpt-4o")

        self.timeout = float(os.environ.get("OPENAI_TIMEOUT", "60"))

    def find_paths(self, source: str, target: str, max_depth: int = 3):
        source = source.strip().strip('"\'')
        target = target.strip().strip('"\'')

        def find_best_match(name: str):
            name_lower = name.lower()
            matches = [
                n for n in self.graph.nodes()
                if name_lower in n.lower() or n.lower() in name_lower
            ]
            if not matches:
                return None
            return max(matches, key=lambda n: self.graph.degree(n))

        s_ent = source if self.graph.has_node(source) else find_best_match(source)
        t_ent = target if self.graph.has_node(target) else find_best_match(target)
        if not s_ent or not t_ent:
            return []
        try:
            paths = list(nx.all_simple_paths(self.graph.to_undirected(), s_ent, t_ent, cutoff=max_depth))
            return paths[:10]
        except Exception:
            return []

    def get_entity_neighborhood(self, entity: str, depth: int = 1):
        entity = entity.strip().strip('"\'')
        if self.graph.has_node(entity):
            matches = [entity]
        else:
            matches = [n for n in self.graph.nodes() if entity.lower() == n.lower()]
            if not matches and len(entity) > 3:
                matches = [n for n in self.graph.nodes() if entity.lower() in n.lower()]

        if not matches:
            return {"entity": entity, "found": False}

        entity = max(matches, key=lambda n: self.graph.degree(n))
        neighbors = {
            "entity": entity,
            "found": True,
            "properties": dict(self.graph.nodes[entity]),
            "outgoing": [],
            "incoming": []
        }

        for _, t, d in self.graph.out_edges(entity, data=True):
            neighbors["outgoing"].append({
                "target": t,
                "relationship": d.get("relationship_type", "related_to"),
                "properties": d
            })
        for s, _, d in self.graph.in_edges(entity, data=True):
            neighbors["incoming"].append({
                "source": s,
                "relationship": d.get("relationship_type", "related_to"),
                "properties": d
            })
        return neighbors

    def _extract_entities(self, user_query: str, max_entities: int = 20):
        query_lower = user_query.lower()
        entities_in_query = []
        stopwords = {
            "and", "or", "the", "a", "an", "in", "on", "with", "for", "to", "of",
            "from", "by", "is", "are", "was", "were", "be", "been", "it", "this",
            "that", "these", "those", "as", "at", "via", "etc"
        }

        def is_noise_entity(name: str) -> bool:
            name_lower = name.lower().strip()
            if len(name_lower) <= 2 or name_lower.isdigit():
                return True
            if name_lower in stopwords:
                return True
            tokens = [t for t in re.split(r"\W+", name_lower) if t]
            return bool(tokens) and all(t in stopwords for t in tokens)

        all_nodes = sorted(list(self.graph.nodes()), key=len, reverse=True)
        for node in all_nodes:
            node_lower = node.lower()
            if len(node_lower) <= 2 or is_noise_entity(node_lower):
                continue
            if re.search(r"\b" + re.escape(node_lower) + r"\b", query_lower):
                entities_in_query.append(node)
                continue
            if len(node_lower) > 3 and node_lower in query_lower:
                entities_in_query.append(node)

        return entities_in_query[:max_entities]

    def _build_context(self, user_query: str, max_entities: int = 20):
        entities_in_query = self._extract_entities(user_query, max_entities)
        graph_context = [self.get_entity_neighborhood(e) for e in entities_in_query]

        if not graph_context:
            return "I couldn't find specific entities in the knowledge graph. Relying on document search.", []

        blocks = []
        for context in graph_context:
            outgoing = ", ".join([
                f"{context['entity']} --[{r['relationship']}]--> {r['target']}"
                for r in context.get("outgoing", [])
            ])
            incoming = ", ".join([
                f"{r['source']} --[{r['relationship']}]--> {context['entity']}"
                for r in context.get("incoming", [])
            ])
            blocks.append(
                f"Entity: {context['entity']}\n"
                f"Outgoing: {outgoing}\n"
                f"Incoming: {incoming}"
            )

        context_text = "\n---\n".join(blocks)
        return context_text, graph_context

    def _call_llm(self, prompt: str):
        if self.provider == "gemini":
            try:
                model = genai.GenerativeModel(self.model)
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                 raise ValueError(f"Gemini API Error: {str(e)}")

        # Fallback to OpenAI
        if not self.openai_key:
            raise ValueError("OPENAI_API_KEY not configured and Gemini not available")

        model_lower = (self.model or "").lower()
        token_param = "max_tokens"
        restrict_temperature = False
        if model_lower.startswith(("gpt-5", "o1", "o3")):
            token_param = "max_completion_tokens"
            restrict_temperature = True

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are analyzing a personal knowledge graph. "
                        "Answer the user's question using only the provided graph context. "
                        "If the graph context is thin, say so briefly."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            token_param: 1200
        }
        if not restrict_temperature:
            payload["temperature"] = 0.4

        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        # Ensure base_url doesn't end with slash if we append path, but here we append /chat/completions
        # Handle full URL vs base URL provided
        if "/chat/completions" not in base_url:
            url = f"{base_url.rstrip('/')}/chat/completions"
        else:
            url = base_url

        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=self.timeout
        )

        if response.status_code != 200:
            raise ValueError(f"OpenAI API Error {response.status_code}: {response.text}")

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("No choices returned from OpenAI")
        message = choices[0].get("message", {})
        return message.get("content", "")

    def query_graph(self, user_query: str, max_entities: int = 20):
        context_text, graph_context = self._build_context(user_query, max_entities)
        if not graph_context:
            return context_text
        prompt = (
            f"Knowledge Graph Context:\n<graph>\n{context_text}\n</graph>\n\n"
            f"User Question: {user_query}\n"
            "Provide a concise, evidence-based answer citing specific entities when relevant."
        )
        return self._call_llm(prompt)

    # Alias for compatibility
    query_with_openai = query_graph

    def get_graph_stats(self):
        graph = self.graph
        try:
            is_connected = nx.is_connected(graph.to_undirected())
        except Exception:
            is_connected = False

        top_entities = [
            {"entity": node, "connections": degree}
            for node, degree in graph.degree()
        ]
        top_entities.sort(key=lambda item: item["connections"], reverse=True)

        return {
            "total_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
            "density": nx.density(graph),
            "is_connected": is_connected,
            "top_entities": top_entities
        }


# Global graph querier (lazy-loaded)
querier = None
graph_loaded = False

def _resolve_graph_path():
    graph_path = os.environ.get("KNOWLEDGE_GRAPH_PATH")
    if graph_path:
        return Path(graph_path)
    data_dir = os.environ.get("OBSIDIAN_RAG_DATA_DIR", "").strip()
    if data_dir:
        data_path = Path(data_dir) / "graph_data" / "knowledge_graph_full.pkl"
        if data_path.exists():
            return data_path

    script_dir = Path(__file__).parent.absolute()
    default_paths = [
        script_dir / "graph_data" / "knowledge_graph_full.pkl",
        script_dir / "graph_data" / "knowledge_graph_test.pkl",
        script_dir / "graph_data" / "knowledge_graph.pkl",
        script_dir / "knowledge_graph_full.pkl",
        script_dir / "knowledge_graph_test.pkl",
        script_dir / "knowledge_graph.pkl",
        Path("graph_data/knowledge_graph_full.pkl"),
        Path("graph_data/knowledge_graph_test.pkl"),
        Path("graph_data/knowledge_graph.pkl"),
        Path("knowledge_graph_full.pkl"),
        Path("knowledge_graph_test.pkl"),
        Path("knowledge_graph.pkl")
    ]
    for path in default_paths:
        if path.exists():
            return path.absolute()
    return None

def load_graph():
    """Load the knowledge graph"""
    global querier, graph_loaded

    if graph_loaded:
        return True

    if not GRAPH_AVAILABLE:
        return False

    try:
        graph_path = _resolve_graph_path()
        if not graph_path or not graph_path.exists():
            print("Graph file not found. Set KNOWLEDGE_GRAPH_PATH to a valid .pkl file.", file=sys.stderr)
            return False

        with open(graph_path, "rb") as handle:
            graph = pickle.load(handle)

        if not isinstance(graph, nx.Graph):
            print("Graph file did not contain a valid NetworkX graph.", file=sys.stderr)
            return False

        querier = GraphQuerier(graph)
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
            name="search_vault_full",
            description="Search your vault and return full note text for the top results. Can also extract PDF text for embedded attachments to avoid separate calls.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for your vault"
                    },
                    "n_results": {
                        "type": "integer",
                        "description": "Number of notes to return (1-5, default: 3)",
                        "default": 3,
                        "minimum": 1,
                        "maximum": 5
                    },
                    "include_attachments": {
                        "type": "boolean",
                        "description": "Extract PDF text for embedded attachments (default: true)",
                        "default": True
                    },
                    "max_attachments_per_note": {
                        "type": "integer",
                        "description": "Max PDFs to extract per note (default: 3)",
                        "default": 3,
                        "minimum": 0,
                        "maximum": 10
                    },
                    "max_pdf_pages": {
                        "type": "integer",
                        "description": "Max PDF pages to extract per attachment (default: 25)",
                        "default": 25,
                        "minimum": 1,
                        "maximum": 100
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
        ),
        Tool(
            name="read_vault_note",
            description="Read the full text of a vault note. Provide a path relative to OBSIDIAN_VAULT_PATH.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to a note in the vault (e.g., 'Medical/Lymphoma/Scan.md')"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="read_attachment_text",
            description="Extract text from a PDF attachment inside the vault. Provide a relative path to a .pdf.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to a PDF in the vault (e.g., 'Medical/Attachments/Scan.pdf')"
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "Max PDF pages to extract (default: 25)",
                        "default": 25,
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["path"]
            }
        )
    ]
    
    # Add graph tools if available (lazy check)
    if GRAPH_AVAILABLE:
        # Try to load graph (but don't fail if it can't load)
        try:
            load_graph()  # Try to load graph
        except Exception:
            pass  # Graph tools won't be added if load fails
        
        if graph_loaded:
            tools.extend([
                Tool(
                    name="obsidian_graph_query",
                    description="Query your knowledge graph using OpenAI synthesis. Ask questions about entities, relationships, and connections in your vault. Returns answers based on graph structure.",
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
        elif name == "search_vault_full":
            return await search_vault_full(arguments)
        elif name == "get_vault_stats" or name == "obsidian_vault_stats":
            # Support both names for compatibility
            return await get_vault_statistics(arguments)
        elif name == "obsidian_graph_query" or name == "query_knowledge_graph":
            # Support both names for compatibility
            return await query_knowledge_graph(arguments)
        elif name == "read_vault_note":
            return await read_vault_note(arguments)
        elif name == "read_attachment_text":
            return await read_attachment_text(arguments)
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
            headers=_service_headers(),
            timeout=15
        )

        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int):
            raise requests.exceptions.ConnectionError("Invalid response from embedding service")

        if status_code != 200:
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


async def search_vault_full(arguments: dict) -> list[TextContent]:
    """Search the vault and return full note text + optional PDF text."""
    query = (arguments or {}).get("query", "")
    n_results = min(max((arguments or {}).get("n_results", 3), 1), 5)
    include_attachments = (arguments or {}).get("include_attachments", True)
    max_attachments = min(
        max((arguments or {}).get("max_attachments_per_note", MAX_ATTACHMENTS_PER_NOTE), 0),
        10
    )
    max_pdf_pages = min(
        max((arguments or {}).get("max_pdf_pages", PDF_MAX_PAGES), 1),
        100
    )

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
            headers=_service_headers(),
            timeout=15
        )

        status_code = getattr(response, "status_code", None)
        if not isinstance(status_code, int):
            raise requests.exceptions.ConnectionError("Invalid response from embedding service")

        if status_code != 200:
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

        output = [f"🔍 **Found {len(documents)} note(s) for '{query}':**\n"]

        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
            relevance = (1 - dist) * 100 if dist < 1 else abs(dist) * 100
            relevance = min(100, max(0, relevance))
            filename = meta.get('filename', 'unknown')
            filepath = meta.get('filepath', 'unknown')

            output.append(f"--- Result {i}: {filename} ({relevance:.0f}% relevant)")
            output.append(f"Path: {filepath}")

            note_path = None
            note_text = None
            if filepath and filepath != "unknown":
                resolved, error = _resolve_vault_path(filepath)
                if error:
                    output.append(error)
                else:
                    note_path = resolved
                    try:
                        note_text = _read_text_file(resolved, MAX_NOTE_CHARS)
                        output.append("Note:")
                        output.append(note_text)
                    except Exception as e:
                        output.append(f"❌ Error reading note: {str(e)}")
            else:
                output.append("❌ No filepath in metadata for this result.")

            if include_attachments and note_path is not None and max_attachments > 0:
                pdf_refs = _extract_pdf_refs(note_text or doc)
                if not pdf_refs:
                    output.append("Attachments: none")
                else:
                    output.append("Attachments:")
                    for ref in pdf_refs[:max_attachments]:
                        resolved_pdf, error = _resolve_attachment_path(note_path, ref)
                        if error:
                            output.append(f"- {ref}: {error}")
                            continue
                        try:
                            pdf_text, _ = _extract_pdf_text(resolved_pdf, max_pdf_pages, MAX_NOTE_CHARS)
                            output.append(f"- {ref} ({resolved_pdf})")
                            output.append(pdf_text)
                        except RuntimeError as e:
                            output.append(f"- {ref}: ❌ {str(e)}")
                        except Exception as e:
                            output.append(f"- {ref}: ❌ Error reading PDF: {str(e)}")

            output.append("")

        return [TextContent(type="text", text="\n".join(output))]

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
            stats_response = requests.get(
                f"{EMBEDDING_URL}/stats",
                timeout=5,
                headers=_service_headers()
            )
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
    """Query knowledge graph (tries LightRAG service first, falls back to local graph)"""
    query = arguments.get("query", "")
    max_entities = arguments.get("max_entities", 20)

    if not query:
        return [TextContent(type="text", text="❌ Query is required")]

    # 1. Try LightRAG (Docker Service)
    # Check if we should prefer local graph via env var
    prefer_local = os.getenv("MCP_GRAPH_PROVIDER", "").lower() == "local"
    
    if not prefer_local:
        try:
            # Check health or just try query
            response = requests.post(
                f"{GRAPH_SERVICE_URL}/query",
                json={"query": query, "mode": "hybrid"},
                headers=_service_headers(),
                timeout=30  # Give LightRAG time to think
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get("response", "")
                if answer:
                    return [TextContent(type="text", text=f"🧠 **(LightRAG)** {answer}")]
        except Exception as e:
            logger.warning(f"LightRAG query failed, falling back to local graph: {e}")

    # 2. Fallback to Local NetworkX Graph
    if not GRAPH_AVAILABLE:
        return [TextContent(
            type="text",
            text="❌ Knowledge graph not available. LightRAG failed and networkx is not installed."
        )]
    
    if not load_graph():
        return [TextContent(
            type="text",
            text="❌ Could not load knowledge graph. Make sure:\n"
                 "1. LightRAG service is running OR\n"
                 "2. KNOWLEDGE_GRAPH_PATH points to a valid .pkl file"
        )]
    
    try:
        answer = querier.query_graph(query, max_entities=max_entities)
        return [TextContent(type="text", text=f"🕸️ **(Local Graph)** {answer}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Graph query error: {str(e)}")]

async def get_entity_info(arguments: dict) -> list[TextContent]:
    """Get entity information"""
    entity_name = arguments.get("entity_name", "")
    if not entity_name:
        return [TextContent(type="text", text="❌ Entity name is required")]

    if not load_graph():
        return [TextContent(type="text", text="❌ Graph not loaded")]
    
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


async def read_vault_note(arguments: dict) -> list[TextContent]:
    path = (arguments or {}).get("path", "")
    resolved, error = _resolve_vault_path(path)
    if error:
        return [TextContent(type="text", text=error)]

    try:
        content = _read_text_file(resolved, MAX_NOTE_CHARS)
        return [TextContent(type="text", text=content)]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error reading note: {str(e)}")]


async def read_attachment_text(arguments: dict) -> list[TextContent]:
    path = (arguments or {}).get("path", "")
    max_pages = int((arguments or {}).get("max_pages", PDF_MAX_PAGES))
    resolved, error = _resolve_vault_path(path)
    if error:
        return [TextContent(type="text", text=error)]

    if resolved.suffix.lower() != ".pdf":
        return [TextContent(type="text", text="❌ Only PDF attachments are supported")]

    try:
        content, _ = _extract_pdf_text(resolved, max_pages, MAX_NOTE_CHARS)
        return [TextContent(type="text", text=content)]
    except RuntimeError as e:
        return [TextContent(type="text", text=f"❌ {str(e)}")]
    except Exception as e:
        return [TextContent(type="text", text=f"❌ Error reading PDF: {str(e)}")]

async def find_entity_path(arguments: dict) -> list[TextContent]:
    """Find path between entities"""
    source = arguments.get("source", "")
    target = arguments.get("target", "")
    max_depth = arguments.get("max_depth", 3)
    
    if not source or not target:
        return [TextContent(type="text", text="❌ Both source and target are required")]

    if not load_graph():
        return [TextContent(type="text", text="❌ Graph not loaded")]
    
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
    search_term = arguments.get("search_term") or arguments.get("query") or ""
    search_term = search_term.lower()
    limit = arguments.get("limit", 10)
    
    if not search_term:
        return [TextContent(type="text", text="❌ Search term is required")]

    if not load_graph():
        return [TextContent(type="text", text="❌ Graph not loaded")]
    
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

class _StreamableHTTPASGIApp:
    def __init__(self, session_manager, api_key: str | None):
        self.session_manager = session_manager
        self.api_key = api_key

    async def __call__(self, scope, receive, send):
        if self.api_key:
            from starlette.responses import PlainTextResponse

            headers = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
            auth = headers.get("authorization", "")
            token = auth.split(" ", 1)[1].strip() if auth.lower().startswith("bearer ") else auth.strip()
            api_key = headers.get("x-api-key", "").strip()
            if token != self.api_key and api_key != self.api_key:
                response = PlainTextResponse("Unauthorized", status_code=401)
                await response(scope, receive, send)
                return

        await self.session_manager.handle_request(scope, receive, send)


class _InMemoryOAuthProvider:
    def __init__(self, access_ttl: int, refresh_ttl: int, auth_code_ttl: int, store_path: Path | None):
        from mcp.server.auth.provider import AuthorizationCode, RefreshToken, AccessToken
        from mcp.shared.auth import OAuthClientInformationFull

        self.AuthorizationCode = AuthorizationCode
        self.RefreshToken = RefreshToken
        self.AccessToken = AccessToken
        self.OAuthClientInformationFull = OAuthClientInformationFull
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl
        self.auth_code_ttl = auth_code_ttl
        self.clients = {}
        self.auth_codes = {}
        self.refresh_tokens = {}
        self.access_tokens = {}
        self.store_path = store_path
        self._load_clients()

    def _load_clients(self) -> None:
        if not self.store_path or not self.store_path.exists():
            return
        try:
            with open(self.store_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            for client_id, raw in data.items():
                client = self.OAuthClientInformationFull.model_validate(raw)
                if client.client_id:
                    self.clients[client_id] = client
        except Exception:
            pass

    def _save_clients(self) -> None:
        if not self.store_path:
            return
        try:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                client_id: client.model_dump()
                for client_id, client in self.clients.items()
            }
            tmp_path = self.store_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            tmp_path.replace(self.store_path)
        except Exception:
            pass

    async def get_client(self, client_id: str):
        return self.clients.get(client_id)

    async def register_client(self, client_info):
        if not client_info.client_id:
            from mcp.server.auth.provider import RegistrationError

            raise RegistrationError("invalid_client_metadata", "client_id is required")
        self.clients[client_info.client_id] = client_info
        self._save_clients()

    async def authorize(self, client, params):
        from mcp.server.auth.provider import construct_redirect_uri

        code = secrets.token_urlsafe(32)
        auth_code = self.AuthorizationCode(
            code=code,
            scopes=params.scopes or [],
            expires_at=time.time() + self.auth_code_ttl,
            client_id=client.client_id,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        self.auth_codes[code] = auth_code
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    async def load_authorization_code(self, client, authorization_code: str):
        return self.auth_codes.get(authorization_code)

    async def exchange_authorization_code(self, client, authorization_code):
        from mcp.shared.auth import OAuthToken

        self.auth_codes.pop(authorization_code.code, None)
        scopes = authorization_code.scopes or []
        now = int(time.time())
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)

        access = self.AccessToken(
            token=access_token,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=now + self.access_ttl,
            resource=authorization_code.resource,
        )
        refresh = self.RefreshToken(
            token=refresh_token,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=now + self.refresh_ttl,
        )

        self.access_tokens[access_token] = access
        self.refresh_tokens[refresh_token] = refresh

        return OAuthToken(
            access_token=access_token,
            expires_in=self.access_ttl,
            refresh_token=refresh_token,
            scope=" ".join(scopes) if scopes else None,
        )

    async def load_refresh_token(self, client, refresh_token: str):
        return self.refresh_tokens.get(refresh_token)

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        from mcp.shared.auth import OAuthToken

        self.refresh_tokens.pop(refresh_token.token, None)
        now = int(time.time())
        access_token = secrets.token_urlsafe(32)
        new_refresh = secrets.token_urlsafe(32)

        access = self.AccessToken(
            token=access_token,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=now + self.access_ttl,
        )
        refresh = self.RefreshToken(
            token=new_refresh,
            client_id=client.client_id,
            scopes=scopes,
            expires_at=now + self.refresh_ttl,
        )

        self.access_tokens[access_token] = access
        self.refresh_tokens[new_refresh] = refresh

        return OAuthToken(
            access_token=access_token,
            expires_in=self.access_ttl,
            refresh_token=new_refresh,
            scope=" ".join(scopes) if scopes else None,
        )

    async def load_access_token(self, token: str):
        return self.access_tokens.get(token)

    async def revoke_token(self, token):
        token_value = getattr(token, "token", None)
        if token_value:
            self.refresh_tokens.pop(token_value, None)
            self.access_tokens.pop(token_value, None)


def _normalize_http_path(path: str) -> str:
    if not path.startswith("/"):
        return f"/{path}"
    return path


def _parse_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    parts = re.split(r"[\s,]+", value.strip())
    return [part for part in parts if part]


def _normalize_public_url(public_url: str | None, host: str, port: int) -> str:
    if public_url:
        return public_url.rstrip("/")
    return f"http://{host}:{port}"


def build_streamable_http_app(
    mount_path: str,
    stateless: bool,
    auth_mode: str,
    api_key: str | None,
    public_url: str | None,
    host: str,
    port: int,
):
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.authentication import AuthenticationMiddleware
    from starlette.routing import Route
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    session_manager = StreamableHTTPSessionManager(app=app, stateless=stateless)
    if auth_mode == "oauth":
        api_key = None
    http_app = _StreamableHTTPASGIApp(session_manager, api_key=api_key)
    routes = []
    middleware = []

    if auth_mode == "oauth":
        from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend, RequireAuthMiddleware
        from mcp.server.auth.provider import ProviderTokenVerifier
        from mcp.server.auth.routes import (
            create_auth_routes,
            create_protected_resource_routes,
            build_resource_metadata_url,
        )
        from mcp.server.auth.settings import ClientRegistrationOptions
        from pydantic import AnyHttpUrl, TypeAdapter

        access_ttl = int(os.getenv("MCP_OAUTH_ACCESS_TTL", "3600"))
        refresh_ttl = int(os.getenv("MCP_OAUTH_REFRESH_TTL", "2592000"))
        auth_code_ttl = int(os.getenv("MCP_OAUTH_AUTH_CODE_TTL", "600"))
        store_path_raw = os.getenv("MCP_OAUTH_STORE_PATH", "/tmp/obsidian_rag_oauth_store.json")
        store_path = Path(store_path_raw).expanduser() if store_path_raw else None
        provider = _InMemoryOAuthProvider(access_ttl, refresh_ttl, auth_code_ttl, store_path)

        scopes = _parse_list(os.getenv("MCP_OAUTH_SCOPES"))
        allow_registration = os.getenv("MCP_OAUTH_ALLOW_REGISTRATION", "true").lower() != "false"
        registration_options = ClientRegistrationOptions(
            enabled=allow_registration,
            valid_scopes=scopes,
            default_scopes=scopes,
        )

        client_id = os.getenv("MCP_OAUTH_CLIENT_ID")
        redirect_uris = _parse_list(os.getenv("MCP_OAUTH_REDIRECT_URIS"))
        if client_id and redirect_uris:
            from mcp.shared.auth import OAuthClientInformationFull

            client_secret = os.getenv("MCP_OAUTH_CLIENT_SECRET")
            token_auth_method = "client_secret_post" if client_secret else "none"
            provider.clients[client_id] = OAuthClientInformationFull(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uris=redirect_uris,
                token_endpoint_auth_method=token_auth_method,
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                scope=" ".join(scopes) if scopes else None,
            )
            provider._save_clients()

        issuer_url_str = _normalize_public_url(public_url, host, port)
        issuer_url = TypeAdapter(AnyHttpUrl).validate_python(issuer_url_str)
        resource_url = TypeAdapter(AnyHttpUrl).validate_python(
            f"{str(issuer_url).rstrip('/')}{_normalize_http_path(mount_path)}"
        )

        token_verifier = ProviderTokenVerifier(provider)
        middleware = [
            Middleware(AuthenticationMiddleware, backend=BearerAuthBackend(token_verifier)),
        ]

        resource_metadata_url = build_resource_metadata_url(resource_url)
        routes.append(
            Route(
                _normalize_http_path(mount_path),
                endpoint=RequireAuthMiddleware(http_app, [], resource_metadata_url),
            )
        )
        routes.extend(
            create_auth_routes(
                provider=provider,
                issuer_url=issuer_url,
                client_registration_options=registration_options,
            )
        )
        routes.extend(
            create_protected_resource_routes(
                resource_url=resource_url,
                authorization_servers=[issuer_url],
                scopes_supported=scopes,
            )
        )
    else:
        routes.append(Route(_normalize_http_path(mount_path), http_app))

    return Starlette(routes=routes, middleware=middleware, lifespan=lambda _: session_manager.run())


async def run_stdio_server():
    """Run the MCP server over stdio (default)."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


def run_http_server(
    host: str,
    port: int,
    mount_path: str,
    stateless: bool,
    auth_mode: str,
    api_key: str | None,
    public_url: str | None,
) -> None:
    """Run the MCP server over streamable HTTP (for ChatGPT connectors)."""
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is required for HTTP transport. Install with: pip install uvicorn", file=sys.stderr)
        sys.exit(1)

    http_app = build_streamable_http_app(
        mount_path=mount_path,
        stateless=stateless,
        auth_mode=auth_mode,
        api_key=api_key,
        public_url=public_url,
        host=host,
        port=port,
    )
    uvicorn.run(http_app, host=host, port=port, log_level="info")


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Obsidian RAG MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HTTP_HOST", "127.0.0.1"),
        help="HTTP host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_HTTP_PORT", "8811")),
        help="HTTP port (default: 8811)",
    )
    parser.add_argument(
        "--path",
        default=os.getenv("MCP_HTTP_PATH", "/mcp"),
        help="HTTP path for MCP (default: /mcp)",
    )
    parser.add_argument(
        "--auth-mode",
        choices=["none", "api-key", "oauth"],
        default=os.getenv("MCP_HTTP_AUTH_MODE", "none"),
        help="HTTP auth mode (default: none)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("MCP_HTTP_API_KEY"),
        help="HTTP API key (default: MCP_HTTP_API_KEY)",
    )
    parser.add_argument(
        "--public-url",
        default=os.getenv("MCP_HTTP_PUBLIC_URL"),
        help="Public HTTPS base URL for OAuth metadata (example: https://xyz.ngrok.app)",
    )
    stateless_default = os.getenv("MCP_HTTP_STATELESS", "true").lower() != "false"
    parser.add_argument(
        "--stateless",
        dest="stateless",
        action="store_true",
        default=stateless_default,
        help="Serve MCP without session state (default: true)",
    )
    parser.add_argument(
        "--stateful",
        dest="stateless",
        action="store_false",
        help="Serve MCP with session state",
    )

    args = parser.parse_args(argv)
    auth_mode = args.auth_mode
    if auth_mode == "none" and args.api_key:
        auth_mode = "api-key"

    if args.transport == "stdio":
        asyncio.run(run_stdio_server())
    else:
        run_http_server(
            host=args.host,
            port=args.port,
            mount_path=args.path,
            stateless=args.stateless,
            auth_mode=auth_mode,
            api_key=args.api_key,
            public_url=args.public_url,
        )


async def main():
    """Backward-compatible entrypoint (stdio)."""
    await run_stdio_server()

if __name__ == "__main__":
    cli()
