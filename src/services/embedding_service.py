#!/usr/bin/env python3
"""
Enhanced Embedding Service with Query Expansion and Re-ranking
Handles semantic search, indexing, and advanced retrieval features
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import chromadb
from sentence_transformers import SentenceTransformer, CrossEncoder
import os
from datetime import datetime
import time
import numpy as np
from pathlib import Path

# Load environment variables from .env.local if it exists
try:
    from dotenv import load_dotenv
    env_file = Path('.env.local')
    if env_file.exists():
        load_dotenv(env_file)
        print(f"✅ Loaded environment from {env_file}")
    else:
        # Try to load from .env as fallback
        load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not installed. Using only system environment variables.")

# Add parent directories to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.utils.query_feedback import log_query, save_feedback, get_metrics, get_all_mode_performance, get_database_stats

app = Flask(__name__)
CORS(app)  # Enable CORS for browser access

# Initialize models
print("Loading embedding model...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
print("Loading cross-encoder for re-ranking...")
cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

# Initialize ChromaDB
print("Initializing ChromaDB (SOTA Branch)...")
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(
    name="obsidian_vault_sota",
    metadata={"hnsw:space": "cosine"}
)

def get_embedding(text):
    """Generate embedding for text"""
    return embedding_model.encode(text).tolist()

def expand_query(query):
    """Expand query with variations for better recall"""
    variations = [query]
    
    # Add hyphen variations
    if '-' in query:
        variations.append(query.replace('-', ' '))
        variations.append(query.replace('-', ''))
    
    # Add common medical synonyms
    medical_synonyms = {
        'car-t': ['car t', 'cart', 'cell therapy', 'yescarta'],
        'pet scan': ['pet-ct', 'pet ct scan', 'positron emission'],
        'lymphoma': ['dlbcl', 'b-cell lymphoma'],
    }
    
    query_lower = query.lower()
    for term, synonyms in medical_synonyms.items():
        if term in query_lower:
            variations.extend(synonyms)
    
    return variations[:5]  # Limit to 5 variations

def rerank_results(query, documents, distances):
    """Re-rank results using cross-encoder for better precision"""
    if len(documents) <= 1:
        return documents, distances
    
    # Create pairs for cross-encoder
    pairs = [(query, doc) for doc in documents]
    
    # Get reranking scores
    scores = cross_encoder.predict(pairs)
    
    # Sort by new scores
    sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    
    reranked_docs = [documents[i] for i in sorted_indices]
    reranked_dists = [float(1 - scores[i]) for i in sorted_indices]  # Convert to distance and ensure Python float
    
    return reranked_docs, reranked_dists

def deduplicate_sources(results):
    """Remove duplicate sources, keep best chunk from each file"""
    seen_files = {}
    
    documents = results.get('documents', [[]])[0]
    metadatas = results.get('metadatas', [[]])[0]
    distances = results.get('distances', [[]])[0]
    
    unique_docs = []
    unique_meta = []
    unique_dist = []
    
    for doc, meta, dist in zip(documents, metadatas, distances):
        filepath = meta.get('filepath', '')
        
        if filepath not in seen_files or dist < seen_files[filepath]['distance']:
            seen_files[filepath] = {'distance': dist, 'index': len(unique_docs)}
            
            if filepath in [m.get('filepath') for m in unique_meta]:
                # Replace existing entry
                idx = seen_files[filepath]['index']
                unique_docs[idx] = doc
                unique_meta[idx] = meta
                unique_dist[idx] = dist
            else:
                unique_docs.append(doc)
                unique_meta.append(meta)
                unique_dist.append(dist)
    
    return {
        'documents': [unique_docs],
        'metadatas': [unique_meta],
        'distances': [unique_dist]
    }

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint with stats"""
    try:
        count = collection.count()
        return jsonify({
            "status": "healthy",
            "documents": count
        }), 200
    except:
        return jsonify({"status": "healthy", "documents": 0}), 200

@app.route('/stats', methods=['GET'])
def stats():
    """Get collection statistics"""
    try:
        count = collection.count()
        return jsonify({
            "total_documents": count,
            "collection": collection.name,
            "estimated_notes": int(count / 4.4)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add', methods=['POST'])
def add_document():
    """Add document to collection"""
    try:
        data = request.json
        doc_id = data.get('id')
        text = data.get('text')
        metadata = data.get('metadata', {})
        
        if not doc_id or not text:
            return jsonify({"error": "Missing id or text"}), 400
        
        # Ensure metadata is not empty
        if not metadata:
            metadata = {"source": "default"}
        
        # Add timestamp
        metadata['indexed_at'] = datetime.now().isoformat()
        
        # Generate embedding
        embedding = get_embedding(text)
        
        # Add to collection
        collection.add(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata]
        )
        
        return jsonify({"status": "success", "id": doc_id}), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/query', methods=['POST'])
def query_documents():
    """Query documents with advanced features"""
    start_time = time.time()
    try:
        data = request.json
        query = data.get('query')
        n_results = data.get('n_results', 5)
        use_reranking = data.get('reranking', True)
        use_dedup = data.get('deduplicate', True)
        filters = data.get('filters', {})
        mode = data.get('mode', 'vector')  # Retrieve mode for metrics

        if not query:
            return jsonify({"error": "Missing query"}), 400

        # Expand query for better recall
        query_variations = expand_query(query)

        # Search with expanded queries
        all_results = []
        for q in query_variations:
            q_embedding = get_embedding(q)

            where_clause = None
            if filters:
                # Build where clause from filters
                conditions = []
                if 'tags' in filters:
                    for tag in filters['tags']:
                        conditions.append({"tags": {"$contains": tag}})
                if conditions:
                    where_clause = {"$and": conditions} if len(conditions) > 1 else conditions[0]

            results = collection.query(
                query_embeddings=[q_embedding],
                n_results=n_results * 2,  # Get extra for deduplication
                where=where_clause
            )

            all_results.append(results)

        # Merge results from all variations
        merged_docs = []
        merged_meta = []
        merged_dist = []

        for res in all_results:
            merged_docs.extend(res['documents'][0])
            merged_meta.extend(res['metadatas'][0])
            merged_dist.extend(res['distances'][0])

        # Remove duplicates
        seen = set()
        unique_docs = []
        unique_meta = []
        unique_dist = []

        for doc, meta, dist in zip(merged_docs, merged_meta, merged_dist):
            doc_id = meta.get('filepath', '') + str(meta.get('chunk_id', ''))
            if doc_id not in seen:
                seen.add(doc_id)
                unique_docs.append(doc)
                unique_meta.append(meta)
                unique_dist.append(dist)

        # Re-rank if enabled
        if use_reranking and len(unique_docs) > 1:
            unique_docs, unique_dist = rerank_results(query, unique_docs, unique_dist)

        # Deduplicate sources if enabled
        merged_results = {
            'documents': [unique_docs[:n_results*2]],
            'metadatas': [unique_meta[:n_results*2]],
            'distances': [unique_dist[:n_results*2]]
        }

        if use_dedup:
            merged_results = deduplicate_sources(merged_results)

        # Trim to requested size and ensure all floats are Python native
        final_results = {
            'documents': [merged_results['documents'][0][:n_results]],
            'metadatas': [merged_results['metadatas'][0][:n_results]],
            'distances': [[float(d) for d in merged_results['distances'][0][:n_results]]]
        }

        # Log metrics
        latency_ms = (time.time() - start_time) * 1000
        num_returned = len(final_results['documents'][0])
        avg_score = float(np.mean(final_results['distances'][0])) if num_returned > 0 else 0.0

        try:
            query_id = log_query(
                query_text=query,
                mode=mode,
                num_results=num_returned,
                avg_score=avg_score,
                latency_ms=latency_ms
            )
            # Include query_id in response for feedback collection
            final_results['query_id'] = query_id
        except Exception as e:
            print(f"Warning: Failed to log metrics: {str(e)}")

        return jsonify(final_results), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    """Submit user feedback for a query"""
    try:
        data = request.json
        query_id = data.get('query_id')
        rating = data.get('rating', 0)  # 1-5 or 0 for no rating
        feedback_text = data.get('feedback', '')

        if not query_id:
            return jsonify({"error": "Missing query_id"}), 400

        if not (0 <= rating <= 5):
            return jsonify({"error": "Rating must be 0-5"}), 400

        save_feedback(query_id, rating, feedback_text)
        return jsonify({"status": "success", "query_id": query_id}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/metrics', methods=['GET'])
def get_query_metrics():
    """Get query metrics and statistics"""
    try:
        hours = request.args.get('hours', 24, type=int)
        metrics = get_metrics(hours)
        mode_perf = get_all_mode_performance()
        db_stats = get_database_stats()

        return jsonify({
            'metrics': metrics,
            'mode_performance': mode_perf,
            'database_stats': db_stats
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete', methods=['POST'])
def delete_document():
    """Delete document by ID"""
    try:
        data = request.json
        doc_id = data.get('id')

        if not doc_id:
            return jsonify({"error": "Missing id"}), 400

        collection.delete(ids=[doc_id])
        return jsonify({"status": "success"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print(f"\n{'='*60}")
    print("Embedding Service Ready!")
    print(f"Total documents: {collection.count()}")
    print(f"Estimated notes: ~{int(collection.count() / 4.4)}")
    print(f"{'='*60}\n")
    
    app.run(host='0.0.0.0', port=8000, debug=False)
