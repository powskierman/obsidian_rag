#!/usr/bin/env python3
"""
Enhanced Embedding Service with Query Expansion and Re-ranking
Handles semantic search, indexing, and advanced retrieval features
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import chromadb
import torch
from sentence_transformers import SentenceTransformer, CrossEncoder
import os
from datetime import datetime
import time
import numpy as np
from pathlib import Path
import re

# Fix for tokenizers parallelism/deadlock issues in Docker
os.environ["TOKENIZERS_PARALLELISM"] = "false"

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

def _parse_allowed_origins() -> list[str]:
    raw = os.getenv("OBSIDIAN_RAG_ALLOWED_ORIGINS", "").strip()
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]


def _get_api_key() -> str | None:
    return os.getenv("OBSIDIAN_RAG_API_KEY")


def _api_key_valid() -> bool:
    expected = _get_api_key()
    if not expected:
        return True
    provided = request.headers.get("X-API-Key")
    return provided == expected


app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": _parse_allowed_origins()}})


@app.before_request
def _require_api_key():
    if not _api_key_valid():
        return jsonify({"error": "Unauthorized"}), 401

# Initialize models
device = 'mps' if torch.backends.mps.is_available() else 'cpu'
print(f"Loading embedding model (Nomic v1.5) on {device}...")
embedding_model = SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True, device=device)
print("Loading cross-encoder for re-ranking...")
cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

# Initialize ChromaDB
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "obsidian_vault")
DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
print(f"Initializing ChromaDB (Collection: {COLLECTION_NAME}) at {DB_PATH}...")
chroma_client = chromadb.PersistentClient(path=DB_PATH)
collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME,
    metadata={"hnsw:space": "cosine"}
)


def _reset_collection():
    global collection
    try:
        chroma_client.delete_collection(name=COLLECTION_NAME)
    except Exception:
        pass
    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )


def _admin_token_valid() -> bool:
    expected_token = os.getenv("EMBEDDING_CLEAR_TOKEN")
    if not expected_token:
        return False
    provided = request.headers.get("X-Admin-Token")
    return provided == expected_token

def get_embedding(text, is_query=False):
    """Generate embedding for text with Nomic specific prefixes"""
    # Nomic v1.5 requires specific prefixes for asymmetric retrieval tasks
    prefix = "search_query: " if is_query else "search_document: "
    return embedding_model.encode(prefix + text).tolist()

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9/._-]{1,}")
STOP_WORDS = {
    "and", "or", "the", "a", "an", "in", "on", "with", "for", "to", "of", "from",
    "by", "is", "are", "was", "were", "be", "been", "it", "this", "that", "these",
    "those", "as", "at", "via", "etc", "my", "me", "your", "you", "we", "our", "us",
    "please", "review", "provide", "assessment", "assess", "summarize", "summary",
    "explain", "show", "find", "search", "notes", "note", "file", "files", "doc",
    "docs", "page", "pages", "what", "which", "who", "where", "when", "why", "how",
    "details", "detail", "dates", "date", "findings", "finding", "report", "reports",
    "result", "results", "information", "info", "data", "overview", "vault"
}

def _dedupe_keep_order(items):
    seen = set()
    output = []
    for item in items:
        if item not in seen:
            output.append(item)
            seen.add(item)
    return output

def _extract_significant_terms(query: str) -> list[str]:
    tokens = TOKEN_PATTERN.findall(query)
    terms = []
    for token in tokens:
        lower = token.lower()
        if lower.isdigit():
            continue
        if lower in STOP_WORDS:
            continue
        if len(lower) < 2 and not any(ch.isdigit() for ch in lower) and not any(ch in "/_-." for ch in lower):
            continue
        terms.append(lower)
    return _dedupe_keep_order(terms)

def expand_query(query):
    """Expand query with variations for better recall"""
    variations = []
    
    # 1. Clean query of stop words for a "keyword only" variation
    # This matches "Nextion ESP32" from "Nextion and ESP32"
    words = [w.lower() for w in TOKEN_PATTERN.findall(query)]
    keywords = [w for w in words if w not in STOP_WORDS]
    
    keyword_query = " ".join(keywords)
    if keyword_query:
        variations.append(keyword_query)
        
    # 2. Add significant terms as a compact query and singletons
    # Helps include important tokens while staying domain-agnostic.
    significant_terms = _extract_significant_terms(query)
    if significant_terms:
        variations.append(" ".join(significant_terms))
        if len(significant_terms) > 3:
            variations.append(" ".join(significant_terms[:3]))
        bigrams = [" ".join(pair) for pair in zip(significant_terms, significant_terms[1:])]
        variations.extend(bigrams[:3])
        for term in significant_terms:
            if len(term) >= 4 or any(ch.isdigit() for ch in term) or any(ch in "/_-." for ch in term):
                variations.append(term)

    # 3. Add hyphen variations
    if '-' in query:
        variations.append(query.replace('-', ' '))
        variations.append(query.replace('-', ''))

    # Deduplicate while preserving order
    variations.append(query)
    unique_vars = _dedupe_keep_order(variations)

    return unique_vars[:6]  # Limit to 6 variations


def rerank_results(query, documents, distances, metadatas):
    """Re-rank results using cross-encoder for better precision"""
    if len(documents) <= 1:
        return documents, distances, metadatas
    
    # Create pairs for cross-encoder
    pairs = [(query, doc) for doc in documents]
    
    # Get reranking scores
    scores = cross_encoder.predict(pairs)
    
    # Sort by new scores
    sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    
    reranked_docs = [documents[i] for i in sorted_indices]
    reranked_meta = [metadatas[i] for i in sorted_indices]
    reranked_dists = [float(1 - scores[i]) for i in sorted_indices]  # Convert to distance and ensure Python float
    
    return reranked_docs, reranked_dists, reranked_meta

def deduplicate_sources(results):
    """Remove duplicate sources, keep best chunk from each file"""
    documents = results.get('documents', [[]])[0]
    metadatas = results.get('metadatas', [[]])[0]
    distances = results.get('distances', [[]])[0]
    
    unique_docs = []
    unique_meta = []
    unique_dist = []
    index_map = {}
    
    for doc, meta, dist in zip(documents, metadatas, distances):
        filepath = meta.get('filepath', '')

        if filepath in index_map:
            idx = index_map[filepath]
            if dist < unique_dist[idx]:
                unique_docs[idx] = doc
                unique_meta[idx] = meta
                unique_dist[idx] = dist
        else:
            index_map[filepath] = len(unique_docs)
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
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Stats error: {e}\n{error_trace}")
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
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error adding document: {e}\n{error_trace}")
        return jsonify({"error": str(e)}), 500


@app.route('/upsert', methods=['POST'])
def upsert_document():
    """Upsert document by ID (insert or replace)."""
    try:
        data = request.json
        doc_id = data.get('id')
        text = data.get('text')
        metadata = data.get('metadata', {})

        if not doc_id or not text:
            return jsonify({"error": "Missing id or text"}), 400

        if not metadata:
            metadata = {"source": "default"}

        metadata['indexed_at'] = datetime.now().isoformat()
        embedding = get_embedding(text)

        collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[metadata]
        )

        return jsonify({"status": "success", "id": doc_id}), 200
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Error upserting document: {e}\n{error_trace}")
        return jsonify({"error": str(e)}), 500

@app.route('/query', methods=['POST'])
def query_documents():
    """Query documents with advanced features"""
    start_time = time.time()
    query = None
    n_results = None
    use_reranking = None
    use_dedup = None
    filters = None
    mode = None
    relevance_threshold = None
    try:
        data = request.json or {}
        query = data.get('query')
        n_results = data.get('n_results', 5)
        use_reranking = data.get('reranking', True)
        use_dedup = data.get('deduplicate', True)
        filters = data.get('filters', {})
        mode = data.get('mode', 'vector')  # Retrieve mode for metrics
        
        # NEW: Accept relevance_threshold (0-100) instead of distance_threshold
        # For backward compatibility, check both parameters
        relevance_threshold = data.get('relevance_threshold', data.get('distance_threshold', 0))
        print(f"🔍 Embedding Service received relevance_threshold: {relevance_threshold}%")

        if not query:
            return jsonify({"error": "Missing query"}), 400

        # Clean query fluff for better semantic match
        clean_query = query.lower()
        starters = ["find notes on", "find notes about", "search for", "look for", "give me info on"]
        for starter in starters:
            if clean_query.startswith(starter):
                clean_query = clean_query[len(starter):].strip()
                break
        
        # Expand query for better recall
        query_variations = expand_query(clean_query)

        # Search with expanded queries
        all_results = []
        query_errors = []
        for q in query_variations:
            if not q:
                continue
            q_embedding = get_embedding(q, is_query=True)

            where_clause = None
            if filters:
                # Preserve advanced filters (e.g., $or/$and) as-is
                if any(key.startswith("$") for key in filters.keys()):
                    where_clause = filters
                else:
                    # Build where clause from simple filters
                    conditions = []
                    for key, value in filters.items():
                        if isinstance(value, dict) and "$contains" in value:
                            # Handle list-based contains (e.g., tags)
                            conditions.append({key: {"$contains": value["$contains"]}})
                        elif isinstance(value, list):
                            # Handle OR for multiple values if list provided
                            if len(value) > 1:
                                conditions.append({key: {"$in": value}})
                            elif len(value) == 1:
                                conditions.append({key: value[0]})
                        else:
                            # Default to exact match
                            conditions.append({key: value})
                    
                    if conditions:
                        where_clause = {"$and": conditions} if len(conditions) > 1 else conditions[0]

            try:
                results = collection.query(
                    query_embeddings=[q_embedding],
                    n_results=n_results * 2,  # Get extra for deduplication
                    where=where_clause
                )
                all_results.append(results)
            except Exception as e:
                query_errors.append(f"{e}")
                print(f"❌ Chroma query failed for variation '{q}' filters={filters}: {e}")

        if not all_results and query_errors:
            raise RuntimeError(f"Chroma query failed for all variations: {query_errors[-1]}")

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
            unique_docs, unique_dist, unique_meta = rerank_results(clean_query, unique_docs, unique_dist, unique_meta)

        # Deduplicate sources if enabled
        merged_results = {
            'documents': [unique_docs],
            'metadatas': [unique_meta],
            'distances': [unique_dist]
        }

        if use_dedup:
            merged_results = deduplicate_sources(merged_results)

        # Apply RELEVANCE threshold filtering (convert distance to relevance %)
        # Use same formula as frontend: 100 / (1 + exp(distance / 2))
        import math
        
        filtered_docs = []
        filtered_meta = []
        filtered_dist = []

        total_before = len(merged_results['documents'][0])
        for doc, meta, dist in zip(
            merged_results['documents'][0],
            merged_results['metadatas'][0],
            merged_results['distances'][0]
        ):
            # Calculate relevance percentage from distance
            relevance = max(0, min(100, 100 / (1 + math.exp(dist / 2))))
            
            # Filter by relevance threshold
            if relevance >= relevance_threshold:
                filtered_docs.append(doc)
                filtered_meta.append(meta)
                filtered_dist.append(dist)

        total_after = len(filtered_docs)
        filtered_out = total_before - total_after
        print(f"📊 Relevance filtering: {total_before} results before, {total_after} passed (threshold: {relevance_threshold}%), {filtered_out} filtered out")

        # Trim to requested size and ensure all floats are Python native
        final_results = {
            'documents': [filtered_docs[:n_results]],
            'metadatas': [filtered_meta[:n_results]],
            'distances': [[float(d) for d in filtered_dist[:n_results]]]
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
        import traceback
        error_trace = traceback.format_exc()
        debug_payload = {
            "query": query,
            "n_results": n_results,
            "use_reranking": use_reranking,
            "use_dedup": use_dedup,
            "filters": filters,
            "mode": mode,
            "relevance_threshold": relevance_threshold
        }
        print(f"❌ Query error: {e}\nPayload: {debug_payload}\n{error_trace}")
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
    """Delete document by ID (requires EMBEDDING_CLEAR_TOKEN)."""
    try:
        if not _admin_token_valid():
            return jsonify({"error": "Forbidden"}), 403

        data = request.json
        doc_id = data.get('id')

        if not doc_id:
            return jsonify({"error": "Missing id"}), 400

        collection.delete(ids=[doc_id])
        return jsonify({"status": "success"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/clear', methods=['POST'])
def clear_collection():
    """Clear and recreate the collection (requires EMBEDDING_CLEAR_TOKEN)."""
    try:
        if not _admin_token_valid():
            return jsonify({"error": "Forbidden"}), 403

        _reset_collection()
        return jsonify({"status": "cleared"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/delete_by_filepath', methods=['POST'])
def delete_by_filepath():
    """Delete all chunks by filepath (requires EMBEDDING_CLEAR_TOKEN)."""
    try:
        if not _admin_token_valid():
            return jsonify({"error": "Forbidden"}), 403

        data = request.json
        filepath = data.get('filepath')
        if not filepath:
            return jsonify({"error": "Missing filepath"}), 400

        collection.delete(where={"filepath": filepath})
        return jsonify({"status": "success", "filepath": filepath}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print(f"\n{'='*60}")
    print("Embedding Service Ready!")
    print(f"Total documents: {collection.count()}")
    print(f"Estimated notes: ~{int(collection.count() / 4.4)}")
    print(f"{'='*60}\n")
    
    app.run(host='0.0.0.0', port=8000, debug=False)
