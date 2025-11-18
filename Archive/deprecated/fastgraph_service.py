#!/usr/bin/env python3
"""
FastGraph Service - Flask API for querying knowledge_graph.json
Provides immediate graph search using pre-extracted entities and relationships
"""

import os
import json
import logging
from pathlib import Path
from flask import Flask, request, jsonify
from fuzzywuzzy import fuzz
from collections import defaultdict

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
GRAPH_FILE = os.getenv("GRAPH_FILE", "./knowledge_graph.json")

# Global graph data
graph_data = None


def load_graph():
    """Load knowledge graph from JSON file"""
    global graph_data
    
    try:
        with open(GRAPH_FILE, 'r') as f:
            graph_data = json.load(f)
        
        entity_count = len(graph_data.get('entities', {}))
        rel_count = len(graph_data.get('relationships', []))
        
        logger.info(f"✅ Loaded graph: {entity_count:,} entities, {rel_count:,} relationships")
        return True
    
    except FileNotFoundError:
        logger.error(f"❌ Graph file not found: {GRAPH_FILE}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in graph file: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Error loading graph: {e}")
        return False


def fuzzy_search_entities(query, threshold=60, max_results=50):
    """
    Search entities using fuzzy matching
    Returns list of (entity_key, entity_data, score) tuples
    """
    if not graph_data:
        return []
    
    entities = graph_data.get('entities', {})
    query_lower = query.lower()
    results = []
    
    for key, entity in entities.items():
        name = entity.get('name', '')
        entity_type = entity.get('type', '')
        
        # Calculate fuzzy match scores
        name_score = fuzz.partial_ratio(query_lower, name.lower())
        key_score = fuzz.partial_ratio(query_lower, key.lower())
        type_score = fuzz.partial_ratio(query_lower, entity_type.lower())
        
        # Take the best score
        best_score = max(name_score, key_score, type_score)
        
        # Boost score if query is a substring
        if query_lower in name.lower() or query_lower in key.lower():
            best_score = min(100, best_score + 20)
        
        if best_score >= threshold:
            results.append((key, entity, best_score))
    
    # Sort by score (descending) and mention count
    results.sort(key=lambda x: (x[2], x[1].get('count', 0)), reverse=True)
    
    return results[:max_results]


def find_related_entities(entity_keys, max_depth=2):
    """
    Find entities related to the given entity keys
    Returns dict of related entities with relationship info
    """
    if not graph_data:
        return {}
    
    relationships = graph_data.get('relationships', [])
    related = defaultdict(lambda: {'relationships': [], 'score': 0})
    
    # Start with the query entities
    current_level = set(entity_keys)
    visited = set(entity_keys)
    
    for depth in range(max_depth):
        next_level = set()
        
        for rel in relationships:
            entity1 = rel.get('entity1', '')
            entity2 = rel.get('entity2', '')
            rel_type = rel.get('type', 'RELATED_TO')
            
            # Check if relationship involves current level entities
            if entity1 in current_level and entity2 not in visited:
                related[entity2]['relationships'].append({
                    'from': entity1,
                    'type': rel_type,
                    'depth': depth + 1
                })
                related[entity2]['score'] += (10 - depth * 3)  # Decay score by depth
                next_level.add(entity2)
                visited.add(entity2)
            
            elif entity2 in current_level and entity1 not in visited:
                related[entity1]['relationships'].append({
                    'from': entity2,
                    'type': rel_type,
                    'depth': depth + 1
                })
                related[entity1]['score'] += (10 - depth * 3)
                next_level.add(entity1)
                visited.add(entity1)
        
        current_level = next_level
        if not current_level:
            break
    
    return dict(related)


def format_entity_response(entity_key, entity_data, related_entities=None):
    """Format entity data for response"""
    docs = entity_data.get('docs', [])
    
    response = {
        'key': entity_key,
        'name': entity_data.get('name', entity_key),
        'type': entity_data.get('type', 'UNKNOWN'),
        'mentions': entity_data.get('count', 0),
        'documents': docs,
        'document_count': len(docs)
    }
    
    if related_entities:
        response['related_entities'] = related_entities
    
    return response


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    if graph_data:
        return jsonify({
            "status": "healthy",
            "graph_loaded": True,
            "entity_count": len(graph_data.get('entities', {})),
            "relationship_count": len(graph_data.get('relationships', []))
        }), 200
    else:
        return jsonify({
            "status": "unhealthy",
            "graph_loaded": False,
            "error": "Graph data not loaded"
        }), 503


@app.route('/stats', methods=['GET'])
def stats():
    """Get graph statistics"""
    if not graph_data:
        return jsonify({"error": "Graph not loaded"}), 503
    
    entities = graph_data.get('entities', {})
    relationships = graph_data.get('relationships', [])
    
    # Calculate statistics
    entity_types = defaultdict(int)
    document_coverage = set()
    
    for entity in entities.values():
        entity_type = entity.get('type', 'UNKNOWN')
        entity_types[entity_type] += 1
        document_coverage.update(entity.get('docs', []))
    
    # Top entities by mention count
    top_entities = sorted(
        [(k, v.get('name', k), v.get('count', 0)) for k, v in entities.items()],
        key=lambda x: x[2],
        reverse=True
    )[:10]
    
    return jsonify({
        "total_entities": len(entities),
        "total_relationships": len(relationships),
        "document_coverage": len(document_coverage),
        "entity_types": dict(entity_types),
        "top_entities": [
            {"key": k, "name": n, "mentions": c}
            for k, n, c in top_entities
        ]
    }), 200


@app.route('/query', methods=['POST'])
def query_graph():
    """
    Query the knowledge graph
    
    Request JSON:
    {
        "query": "lymphoma treatment",
        "threshold": 60,  // optional, fuzzy match threshold (0-100)
        "max_results": 20,  // optional, max entities to return
        "include_related": true  // optional, include related entities
    }
    """
    if not graph_data:
        return jsonify({"error": "Graph not loaded"}), 503
    
    try:
        data = request.json
        query_text = data.get('query', '')
        threshold = data.get('threshold', 60)
        max_results = data.get('max_results', 20)
        include_related = data.get('include_related', True)
        
        if not query_text:
            return jsonify({"error": "No query provided"}), 400
        
        logger.info(f"🔍 Query: {query_text} (threshold={threshold})")
        
        # Search for matching entities
        matching_entities = fuzzy_search_entities(query_text, threshold, max_results)
        
        if not matching_entities:
            return jsonify({
                "query": query_text,
                "matches": 0,
                "entities": [],
                "result": "No matching entities found"
            }), 200
        
        # Get entity keys for relationship search
        entity_keys = [key for key, _, _ in matching_entities]
        
        # Find related entities if requested
        related = {}
        if include_related:
            related = find_related_entities(entity_keys, max_depth=2)
        
        # Build response
        entities_response = []
        all_docs = set()
        
        for key, entity, score in matching_entities:
            entity_related = {}
            if key in related or include_related:
                # Get related entities for this specific entity
                entity_related = find_related_entities([key], max_depth=1)
            
            entity_resp = format_entity_response(key, entity, entity_related if entity_related else None)
            entity_resp['relevance_score'] = score
            entities_response.append(entity_resp)
            
            # Collect all documents
            all_docs.update(entity.get('docs', []))
        
        # Build context text for response
        context_parts = []
        for i, ent in enumerate(entities_response[:10], 1):  # Top 10 for context
            name = ent['name']
            entity_type = ent['type']
            mentions = ent['mentions']
            doc_count = ent['document_count']
            
            context_parts.append(
                f"{i}. **{name}** ({entity_type}) - {mentions} mentions in {doc_count} documents"
            )
        
        context_text = "\n".join(context_parts)
        
        return jsonify({
            "query": query_text,
            "matches": len(matching_entities),
            "entities": entities_response,
            "documents": sorted(list(all_docs)),
            "document_count": len(all_docs),
            "result": context_text
        }), 200
    
    except Exception as e:
        logger.error(f"Query error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/entity/<path:entity_key>', methods=['GET'])
def get_entity(entity_key):
    """Get specific entity by key"""
    if not graph_data:
        return jsonify({"error": "Graph not loaded"}), 503
    
    entities = graph_data.get('entities', {})
    
    if entity_key not in entities:
        return jsonify({"error": f"Entity not found: {entity_key}"}), 404
    
    entity = entities[entity_key]
    related = find_related_entities([entity_key], max_depth=2)
    
    response = format_entity_response(entity_key, entity, related)
    
    return jsonify(response), 200


if __name__ == '__main__':
    logger.info("🚀 Starting FastGraph Service")
    logger.info(f"📊 Graph file: {GRAPH_FILE}")
    
    # Load graph on startup
    if load_graph():
        logger.info("✅ FastGraph Service ready")
        app.run(host='0.0.0.0', port=8006, debug=False)
    else:
        logger.error("❌ Failed to load graph, exiting")
        exit(1)

