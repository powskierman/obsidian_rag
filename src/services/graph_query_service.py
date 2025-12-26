"""
Flask service for Claude-powered knowledge graph queries
Runs alongside your existing embedding service in Docker
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from kimi_graph_builder import GraphBuilder, GraphQuerier
import logging

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global graph builder and querier
builder = None
querier = None
graph_loaded = False


def initialize_graph(graph_path: str = None):
    """Initialize the knowledge graph"""
    global builder, querier, graph_loaded
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set")
        return False
    
    try:
        builder = GraphBuilder(api_key=api_key)
        
        # If no path provided, try default locations
        if graph_path is None:
            graph_path = os.environ.get('GRAPH_PATH', '/app/graph_data/knowledge_graph_full.pkl')
        
        # Try multiple possible locations - prioritize env var, then docker paths
        possible_paths = [
            graph_path,
            os.environ.get('GRAPH_PATH'),
            '/app/graph_data/knowledge_graph_full.pkl',
            'graph_data/knowledge_graph_full.pkl', # Local fallback
            'knowledge_graph_full.pkl' 
        ]
        
        graph_file = None
        for path in possible_paths:
            if path and os.path.exists(path):
                graph_file = path
                break
        
        if graph_file:
            builder.load_graph(graph_file)
            querier = GraphQuerier(builder, api_key=api_key)
            graph_loaded = True
            logger.info(f"Graph loaded from {graph_file}: {builder.graph.number_of_nodes()} nodes, {builder.graph.number_of_edges()} edges")
            return True
        else:
            logger.warning(f"Graph file not found. Tried: {possible_paths}")
            # Create a querier with empty graph so we can at least use client? 
            # Actually querier wraps graph. KimiGraphBuilder inits empty graph.
            # So let's init querier anyway.
            querier = GraphQuerier(builder, api_key=api_key)
            logger.info("Initialized with empty graph (waiting for build)")
            return False # Graph NOT loaded from disk, but valid state
    except Exception as e:
        logger.error(f"Error loading graph: {e}")
        return False


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'graph_loaded': graph_loaded,
        'nodes': builder.graph.number_of_nodes() if graph_loaded else 0,
        'edges': builder.graph.number_of_edges() if graph_loaded else 0
    })


@app.route('/query', methods=['POST'])
def query_graph():
    """
    Query the knowledge graph with Claude + Hybrid RAG (Vector Search)
    
    POST body:
    {
        "query": "What treatments are mentioned?",
        "max_entities": 20,
        "mode": "vector" | "graph" | "hybrid",
        "web_search": boolean
    }
    """
    # If graph not loaded, try init. If still not loaded, only allow vector/web modes.
    if not graph_loaded:
        initialize_graph()
        
    try:
        data = request.json
        logger.info(f"Received query request: {data}")
        user_query = data.get('query', '')
        max_entities = data.get('max_entities', 20)
        mode = data.get('mode', 'hybrid')
        web_search = data.get('web_search', False)
        model = data.get('model') # Extract model for parameter passing
        
        # If still no graph and needing graph mode, warn but try to proceed (will be empty)
        if not graph_loaded and mode in ['graph', 'hybrid'] and not web_search:
             logger.warning("Graph mode requested but graph not loaded.")
             # We can continue, likely yielding minimal results from graph part

        
        if not user_query:
            return jsonify({'error': 'Query is required'}), 400
            
        vector_context = ""
        
        # FEATURE: VECTOR SEARCH (Used in 'vector' and 'hybrid' modes)
        if mode in ['vector', 'hybrid']:
            try:
                embedding_service_url = os.environ.get('EMBEDDING_SERVICE_URL', 'http://localhost:8000')
                logger.info(f"Querying vector store at {embedding_service_url}...")
                
                vec_res = requests.post(
                    f"{embedding_service_url}/query",
                    json={
                        "query": user_query,
                        "n_results": 7,
                        "reranking": True
                    },
                    timeout=5
                )
                
                if vec_res.status_code == 200:
                    vec_data = vec_res.json()
                    docs = vec_data.get('documents', [[]])[0]
                    metas = vec_data.get('metadatas', [[]])[0]
                    
                    context_parts = []
                    for i, doc in enumerate(docs):
                        meta = metas[i] if i < len(metas) else {}
                        filename = meta.get('filename', 'Unknown')
                        context_parts.append(f"Source: {filename}\nContent: {doc}")
                    
                    vector_context = "\n\n".join(context_parts)
                    logger.info(f"Retrieved {len(docs)} vector chunks for context")
                else:
                    logger.warning(f"Embedding service returned {vec_res.status_code}: {vec_res.text}")
            except Exception as ve:
                logger.warning(f"Failed to fetch vector context: {ve}")

        # TODO: Implement Web Search / Deep Thinking integration here when 'web_search' is True
        if web_search:
            # LEGACY BEHAVIOR: Simple, fast web search (No Deep Thinking Agents)
            logger.info("Web search requested - using Legacy/Fast Web Search")
            try:
                from tavily import TavilyClient
                tavily_api_key = os.environ.get("TAVILY_API_KEY")
                if tavily_api_key:
                    tavily = TavilyClient(api_key=tavily_api_key)
                    # Use 'basic' depth for speed, as requested (Legacy was fast)
                    tav_response = tavily.search(query=user_query, search_depth="basic", max_results=3)
                    
                    if 'results' in tav_response and tav_response['results']:
                        web_context_parts = ["\n## 🌐 Web Search"]
                        for i, res in enumerate(tav_response['results'][:3], 1):
                            web_context_parts.append(f"**[{res['title']}]({res['url']})**\n{res['content']}")
                        
                        web_context_str = "\n\n".join(web_context_parts)
                        # Prepend to vector context for higher visibility
                        vector_context = f"{web_context_str}\n\n{vector_context}"
                        logger.info(f"Added {len(tav_response['results'])} web results to context (Prepend)")
                    else:
                        logger.info("No web results found")
                else:
                    logger.warning("TAVILY_API_KEY not set, skipping web search")
            except Exception as e:
                logger.error(f"Legacy Web Search error: {e}")
                # Continue without web results (graceful degradation)

        # Generate Answer
        # For 'vector' mode, we might want to skip graph context entirely to be pure,
        # but 'query_with_llm' currently enforces graph context.
        # For now, we'll pass vector_context to it.
        # If mode is 'graph', we just pass empty vector_context (which we initialized to "")
        
        answer = querier.query_with_llm(
            user_query, 
            max_entities=max_entities, 
            additional_context=vector_context, # Now prepended with web results for LLM
            model=model
        )
        
        # LEGACY/UX FEATURE: Explicitly append web search block to the answer for visibility
        if web_search and 'web_context_str' in locals() and web_context_str:
             answer += f"\n\n{web_context_str}"
        
        return jsonify({
            'answer': answer,
            'query': user_query,
            'mode': mode
        })
    
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/entity/<path:entity_name>', methods=['GET'])
def get_entity(entity_name: str):
    """Get information about a specific entity"""
    if not graph_loaded:
        return jsonify({'error': 'Graph not loaded'}), 503
    
    try:
        neighborhood = querier.get_entity_neighborhood(entity_name)
        return jsonify(neighborhood)
    except Exception as e:
        logger.error(f"Error getting entity: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/path', methods=['POST'])
def find_path():
    """
    Find paths between two entities
    """
    if not graph_loaded:
        return jsonify({'error': 'Graph not loaded'}), 503
    
    try:
        data = request.json
        source = data.get('source', '')
        target = data.get('target', '')
        max_depth = data.get('max_depth', 3)
        
        if not source or not target:
            return jsonify({'error': 'Both source and target are required'}), 400
        
        paths = querier.find_paths(source, target, max_depth)
        
        return jsonify({
            'source': source,
            'target': target,
            'paths': paths,
            'count': len(paths)
        })
    
    except Exception as e:
        logger.error(f"Error finding path: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get graph statistics"""
    if not graph_loaded:
        return jsonify({'error': 'Graph not loaded'}), 503
    
    try:
        stats = querier.get_graph_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/search_entities', methods=['POST'])
def search_entities():
    """Search for entities by name"""
    if not graph_loaded:
        initialize_graph() # Try to auto-init
        # Proceed even if not loaded, search will just be empty (or fallback to file matches)
    
    try:
        data = request.json
        search_query = data.get('query', '').lower()
        limit = data.get('limit', 10)
        
        if not search_query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Search entities
        matching_entities = []
        for node in builder.graph.nodes():
            if search_query in node.lower():
                node_data = dict(builder.graph.nodes[node])
                sources = node_data.get('sources', [])
                
                # Fallback: If no sources in graph, check if a note exists with this name
                if not sources:
                    safe_name = node.replace('/', '_').replace('\\', '_')
                    
                    # Determine vault root
                    vault_root = os.environ.get('VAULT_ROOT')
                    if not vault_root:
                        vault_root = os.environ.get('OBSIDIAN_VAULT_PATH')
                    if not vault_root:
                         vault_root = '/app/vault'
                    
                    # Check exact match first
                    potential_path = os.path.join(vault_root, f"{safe_name}.md")
                    if os.path.exists(potential_path):
                        sources.append({'filename': f"{safe_name}.md", 'chunk_id': 'file_match'})
                    else:
                        # Recursive search for the filename
                        if os.path.exists(vault_root):
                            for root, dirs, files in os.walk(vault_root):
                                if f"{safe_name}.md" in files:
                                    rel_dir = os.path.relpath(root, vault_root)
                                    rel_path = os.path.join(rel_dir, f"{safe_name}.md")
                                    if rel_dir == '.': rel_path = f"{safe_name}.md"
                                    sources.append({'filename': rel_path, 'chunk_id': 'file_match'})
                                    break
                
                matching_entities.append({
                    'name': node,
                    'type': node_data.get('entity_type', 'Unknown'),
                    'connections': builder.graph.degree(node),
                    'sources': sources
                })
        
        # Sort by number of connections
        matching_entities.sort(key=lambda x: x['connections'], reverse=True)
        
        return jsonify({
            'query': search_query,
            'results': matching_entities[:limit],
            'total': len(matching_entities)
        })
    
    except Exception as e:
        logger.error(f"Error searching entities: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/get_note_content', methods=['POST'])
def get_note_content():
    """Get raw content of a specific note"""
    try:
        data = request.json
        filename = data.get('filename')
        
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400
            
        # Security check: Prevent path traversal
        if '..' in filename or filename.startswith('/'):
            return jsonify({'error': 'Invalid filename'}), 400
            
        # Determine vault root - check env vars with local fallback
        vault_root = os.environ.get('VAULT_ROOT')
        if not vault_root:
            vault_root = os.environ.get('OBSIDIAN_VAULT_PATH')
        if not vault_root:
            vault_root = '/app/vault' # Docker default
            
        full_path = os.path.join(vault_root, filename)
        
        if not os.path.exists(full_path):
             # Try finding it recursively if path is just basename
            if '/' not in filename:
                for root, dirs, files in os.walk(vault_root):
                    if filename in files:
                        full_path = os.path.join(root, filename)
                        break
            
        if not os.path.exists(full_path):
            return jsonify({'error': 'File not found'}), 404
            
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        return jsonify({
            'filename': filename,
            'content': content
        })

    except Exception as e:
        logger.error(f"Error reading note: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Initialize graph on startup
    initialize_graph()
    
    # Run Flask app
    port = int(os.environ.get('PORT', 8002))
    app.run(host='0.0.0.0', port=port, debug=False)
