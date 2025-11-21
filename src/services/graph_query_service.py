"""
Flask service for Claude-powered knowledge graph queries
Runs alongside your existing embedding service in Docker
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from claude_graph_builder import ClaudeGraphBuilder, ClaudeGraphQuerier
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
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not set")
        return False
    
    try:
        builder = ClaudeGraphBuilder(api_key=api_key)
        
        # If no path provided, try default locations
        if graph_path is None:
            graph_path = os.environ.get('GRAPH_PATH', '/app/graph_data/knowledge_graph_full.pkl')
        
        # Try multiple possible locations
        possible_paths = [
            graph_path,
            '/app/graph_data/knowledge_graph_full.pkl',
            '/app/graph_data/knowledge_graph_test.pkl',
            '/app/knowledge_graph_full.pkl',
            '/app/knowledge_graph_test.pkl'
        ]
        
        graph_file = None
        for path in possible_paths:
            if os.path.exists(path):
                graph_file = path
                break
        
        if graph_file:
            builder.load_graph(graph_file)
            querier = ClaudeGraphQuerier(builder, api_key=api_key)
            graph_loaded = True
            logger.info(f"Graph loaded from {graph_file}: {builder.graph.number_of_nodes()} nodes, {builder.graph.number_of_edges()} edges")
            return True
        else:
            logger.warning(f"Graph file not found. Tried: {possible_paths}")
            return False
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
    Query the knowledge graph with Claude
    
    POST body:
    {
        "query": "What treatments are mentioned?",
        "max_entities": 20  // optional
    }
    """
    if not graph_loaded:
        return jsonify({
            'error': 'Graph not loaded. Please build graph first.'
        }), 503
    
    try:
        data = request.json
        user_query = data.get('query', '')
        max_entities = data.get('max_entities', 20)
        
        if not user_query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Query with Claude
        answer = querier.query_with_claude(user_query, max_entities=max_entities)
        
        return jsonify({
            'answer': answer,
            'query': user_query
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
    
    POST body:
    {
        "source": "Entity 1",
        "target": "Entity 2",
        "max_depth": 3  // optional
    }
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
    """
    Search for entities by name
    
    POST body:
    {
        "query": "search term",
        "limit": 10  // optional
    }
    """
    if not graph_loaded:
        return jsonify({'error': 'Graph not loaded'}), 503
    
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
                matching_entities.append({
                    'name': node,
                    'type': node_data.get('entity_type', 'Unknown'),
                    'connections': builder.graph.degree(node)
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


if __name__ == '__main__':
    # Initialize graph on startup
    graph_path = os.environ.get('GRAPH_PATH')
    initialize_graph(graph_path)
    
    # Run Flask app
    port = int(os.environ.get('PORT', 8002))
    app.run(host='0.0.0.0', port=port, debug=False)
