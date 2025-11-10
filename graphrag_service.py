#!/usr/bin/env python3
"""
GraphRAG Service - Flask API for Microsoft GraphRAG
Stable replacement for LightRAG with better async handling
"""

import os
import json
import logging
import asyncio
import yaml
from pathlib import Path
from flask import Flask, request, jsonify
from typing import List, Dict, Any, Optional

# Check if GraphRAG CLI is available
import subprocess
import shutil

def check_graphrag_cli():
    """Check if GraphRAG CLI is available"""
    try:
        result = subprocess.run(['graphrag', '--help'],
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

GRAPHRAG_AVAILABLE = check_graphrag_cli()
if not GRAPHRAG_AVAILABLE:
    print("GraphRAG CLI not available. Install with: pip install graphrag")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
WORKING_DIR = os.getenv("GRAPHRAG_DIR", "./graphrag_db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:14b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# Global state
is_initialized = False
config_path = None


def initialize_graphrag_workspace():
    """Initialize GraphRAG workspace using CLI"""
    global config_path

    try:
        os.makedirs(WORKING_DIR, exist_ok=True)
        os.chdir(WORKING_DIR)

        # Initialize GraphRAG workspace if not already done
        settings_file = Path(WORKING_DIR) / "settings.yaml"
        if not settings_file.exists():
            logger.info("Initializing GraphRAG workspace...")
            result = subprocess.run(['graphrag', 'init', '--root', WORKING_DIR],
                                  capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"GraphRAG init failed: {result.stderr}")
                return False

        # Create .env file for Ollama configuration
        env_file = Path(WORKING_DIR) / ".env"
        env_content = f"""# GraphRAG Configuration for Ollama
GRAPHRAG_API_KEY=not_needed
GRAPHRAG_API_BASE={OLLAMA_HOST}/v1
GRAPHRAG_LLM_MODEL={LLM_MODEL}
GRAPHRAG_EMBEDDING_MODEL={EMBED_MODEL}
"""
        with open(env_file, 'w') as f:
            f.write(env_content)

        # Update settings.yaml for Ollama
        if settings_file.exists():
            # Read existing settings
            with open(settings_file, 'r') as f:
                settings = yaml.safe_load(f) or {}

            # Update for Ollama with proper authentication handling
            settings.update({
                "llm": {
                    "api_type": "openai_chat",
                    "api_base": f"{OLLAMA_HOST}/v1",
                    "api_key": "not_required",  # Ollama doesn't need auth
                    "model": LLM_MODEL,
                    "max_tokens": 4000,
                    "temperature": 0.1,
                    "request_timeout": 180.0,
                    "concurrent_requests": 1
                },
                "embeddings": {
                    "api_type": "openai_embedding",
                    "api_base": f"{OLLAMA_HOST}/v1",
                    "api_key": "not_required",  # Ollama doesn't need auth
                    "model": EMBED_MODEL,
                    "request_timeout": 180.0,
                    "concurrent_requests": 1
                },
                "models": {
                    "default_chat_model": {
                        "type": "chat",
                        "model_provider": "openai",
                        "model": LLM_MODEL,
                        "api_key": "not_required",
                        "auth_type": "none",  # No authentication required
                        "async_mode": "threaded",
                        "concurrent_requests": 1,
                        "max_retries": 3,
                        "retry_strategy": "exponential_backoff"
                    },
                    "default_embedding_model": {
                        "type": "embedding",
                        "model_provider": "openai",
                        "model": EMBED_MODEL,
                        "api_key": "not_required",
                        "auth_type": "none",  # No authentication required
                        "async_mode": "threaded",
                        "concurrent_requests": 1,
                        "max_retries": 3,
                        "retry_strategy": "exponential_backoff"
                    }
                },
                "chunks": {
                    "size": 1200,
                    "overlap": 100
                },
                "entity_extraction": {
                    "entity_types": ["person", "organization", "location", "event", "concept", "technology", "medical_condition", "treatment", "medication", "procedure"]
                }
            })

            # Write updated settings
            with open(settings_file, 'w') as f:
                yaml.dump(settings, f, default_flow_style=False)

        config_path = settings_file
        logger.info(f"✅ GraphRAG workspace initialized at {WORKING_DIR}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize GraphRAG workspace: {e}")
        return False


def initialize_graphrag():
    """Initialize GraphRAG configuration"""
    global is_initialized

    if not GRAPHRAG_AVAILABLE:
        logger.warning("GraphRAG CLI not available - using mock responses")
        is_initialized = True
        return True

    try:
        # Initialize workspace
        if initialize_graphrag_workspace():
            is_initialized = True
            logger.info("✅ GraphRAG initialized successfully")
            return True
        else:
            return False

    except Exception as e:
        logger.error(f"Failed to initialize GraphRAG: {e}")
        is_initialized = False
        return False


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "graphrag",
        "initialized": is_initialized,
        "graphrag_available": GRAPHRAG_AVAILABLE,
        "ollama_host": OLLAMA_HOST,
        "llm_model": LLM_MODEL
    }), 200


@app.route('/stats', methods=['GET'])
def stats():
    """Get statistics about the knowledge graph"""
    try:
        db_path = Path(WORKING_DIR)
        exists = db_path.exists()

        stats_data = {
            "working_dir": WORKING_DIR,
            "database_exists": exists,
            "initialized": is_initialized,
            "llm_model": LLM_MODEL,
            "embed_model": EMBED_MODEL,
            "graphrag_available": GRAPHRAG_AVAILABLE
        }

        if exists:
            files = list(db_path.rglob("*"))
            stats_data["total_files"] = len(files)

        return jsonify(stats_data), 200

    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/insert', methods=['POST'])
def insert_documents():
    """Insert documents into GraphRAG knowledge graph"""
    try:
        data = request.json
        texts = data.get('texts', [])

        if not texts:
            return jsonify({"error": "No texts provided"}), 400

        if not GRAPHRAG_AVAILABLE or not is_initialized:
            return jsonify({"error": "GraphRAG not available or initialized"}), 500

        # Write texts to input directory for GraphRAG processing
        input_dir = Path(WORKING_DIR) / "input"
        input_dir.mkdir(exist_ok=True)

        for i, text in enumerate(texts):
            with open(input_dir / f"doc_{i}.txt", 'w', encoding='utf-8') as f:
                f.write(text)

        return jsonify({
            "status": "success",
            "documents_inserted": len(texts),
            "note": "Documents saved to input directory. Run indexing to build knowledge graph."
        }), 200

    except Exception as e:
        logger.error(f"Insert error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/build-index', methods=['POST'])
def build_index():
    """Build the GraphRAG knowledge graph index"""
    try:
        if not GRAPHRAG_AVAILABLE or not is_initialized:
            return jsonify({"error": "GraphRAG not available or initialized"}), 500

        # Run the indexing pipeline using CLI
        logger.info("Starting GraphRAG indexing pipeline...")
        os.chdir(WORKING_DIR)

        result = subprocess.run(['graphrag', 'index', '--root', WORKING_DIR],
                              capture_output=True, text=True, timeout=1800)  # 30 min timeout

        if result.returncode == 0:
            return jsonify({
                "status": "success",
                "message": "Knowledge graph index built successfully",
                "output": result.stdout
            }), 200
        else:
            logger.error(f"GraphRAG indexing failed: {result.stderr}")
            return jsonify({
                "error": "Indexing failed",
                "details": result.stderr,
                "stdout": result.stdout
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({"error": "Indexing timed out after 30 minutes"}), 500
    except Exception as e:
        logger.error(f"Index building error: {e}")
        return jsonify({"error": str(e)}), 500


def perform_graphrag_query(query_text: str, mode: str) -> str:
    """Perform GraphRAG query using CLI"""
    try:
        os.chdir(WORKING_DIR)

        # Map our modes to GraphRAG CLI modes
        if mode == 'global':
            search_type = 'global'
        elif mode == 'local':
            search_type = 'local'
        else:
            # Default to global for other modes
            search_type = 'global'

        # Run GraphRAG query via CLI
        result = subprocess.run([
            'graphrag', 'query',
            '--root', WORKING_DIR,
            '--method', search_type,
            query_text
        ], capture_output=True, text=True, timeout=300)  # 5 min timeout

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            logger.error(f"GraphRAG query failed: {result.stderr}")
            return f"Query failed: {result.stderr}"

    except subprocess.TimeoutExpired:
        return "Query timed out after 5 minutes"
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        return f"Query error: {str(e)}"


@app.route('/query', methods=['POST'])
def query_graph():
    """Query the knowledge graph using GraphRAG"""
    try:
        data = request.json
        query_text = data.get('query')
        mode = data.get('mode', 'global')  # naive, local, global, or hybrid

        if not query_text:
            return jsonify({"error": "No query provided"}), 400

        if not GRAPHRAG_AVAILABLE or not is_initialized:
            # Fallback response when GraphRAG not available
            return jsonify({
                "query": query_text,
                "mode": mode,
                "result": f"GraphRAG service unavailable. Your query '{query_text}' would be processed in {mode} mode when the service is properly configured. Please use vector search for now."
            }), 200

        # Validate mode
        valid_modes = ['naive', 'local', 'global', 'hybrid']
        if mode not in valid_modes:
            return jsonify({"error": f"Invalid mode. Use: {valid_modes}"}), 400

        # Check if index exists
        output_dir = Path(WORKING_DIR) / "output"
        if not output_dir.exists() or not list(output_dir.glob("*.parquet")):
            return jsonify({
                "error": "No knowledge graph index found. Please run /build-index first.",
                "query": query_text,
                "mode": mode
            }), 400

        # Execute query
        result = perform_graphrag_query(query_text, mode)

        return jsonify({
            "query": query_text,
            "mode": mode,
            "result": result
        }), 200

    except Exception as e:
        logger.error(f"Query error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/index-vault', methods=['POST'])
def index_vault():
    """Index all markdown files from a vault directory"""
    try:
        data = request.json or {}
        vault_path = data.get('vault_path', './vault')

        # Load markdown files
        notes = []
        vault_dir = Path(vault_path)

        if not vault_dir.exists():
            return jsonify({"error": f"Vault path not found: {vault_path}"}), 400

        for md_file in vault_dir.rglob("*.md"):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        notes.append({
                            "content": content,
                            "filename": md_file.name,
                            "filepath": str(md_file.relative_to(vault_dir))
                        })
            except Exception as e:
                logger.warning(f"Could not read {md_file}: {e}")

        if not notes:
            return jsonify({"error": "No markdown files found"}), 400

        if not GRAPHRAG_AVAILABLE or not is_initialized:
            return jsonify({
                "status": "fallback",
                "message": "GraphRAG not available - files would be indexed when service is configured",
                "files_found": len(notes),
                "vault_path": vault_path
            }), 200

        # Write documents to input directory
        input_dir = Path(WORKING_DIR) / "input"
        input_dir.mkdir(exist_ok=True)

        # Clear existing input files
        for existing_file in input_dir.glob("*.txt"):
            existing_file.unlink()

        # Write vault content to input files
        for i, note in enumerate(notes):
            filename = f"{note['filepath'].replace('/', '_')}_{i}.txt"
            with open(input_dir / filename, 'w', encoding='utf-8') as f:
                f.write(f"# {note['filename']}\n\n{note['content']}")

        logger.info(f"Prepared {len(notes)} files for GraphRAG indexing")

        # Trigger automatic indexing
        try:
            os.chdir(WORKING_DIR)
            logger.info("Starting GraphRAG indexing pipeline for vault...")
            result = subprocess.run(['graphrag', 'index', '--root', WORKING_DIR],
                                  capture_output=True, text=True, timeout=1800)

            if result.returncode == 0:
                return jsonify({
                    "status": "success",
                    "files_indexed": len(notes),
                    "vault_path": vault_path,
                    "message": "Vault successfully indexed and knowledge graph built"
                }), 200
            else:
                logger.error(f"Indexing failed: {result.stderr}")
                return jsonify({
                    "status": "partial_success",
                    "files_prepared": len(notes),
                    "vault_path": vault_path,
                    "message": "Files prepared but indexing failed. Run /build-index manually.",
                    "error": result.stderr
                }), 200

        except subprocess.TimeoutExpired:
            return jsonify({
                "status": "partial_success",
                "files_prepared": len(notes),
                "vault_path": vault_path,
                "message": "Files prepared but indexing timed out. Run /build-index manually.",
                "error": "Indexing timed out after 30 minutes"
            }), 200
        except Exception as index_error:
            logger.error(f"Indexing failed: {index_error}")
            return jsonify({
                "status": "partial_success",
                "files_prepared": len(notes),
                "vault_path": vault_path,
                "message": "Files prepared but indexing failed. Run /build-index manually.",
                "error": str(index_error)
            }), 200

    except Exception as e:
        logger.error(f"Index vault error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info(f"""
╔══════════════════════════════════════════════════════════╗
║          GraphRAG Service - Knowledge Graph RAG          ║
╚══════════════════════════════════════════════════════════╝

📂 Working Dir: {WORKING_DIR}
🤖 LLM Model:   {LLM_MODEL}
🔤 Embed Model: {EMBED_MODEL}
🌐 Ollama Host: {OLLAMA_HOST}
📦 GraphRAG:    {'Available' if GRAPHRAG_AVAILABLE else 'Not Installed'}

Endpoints:
  GET  /health         - Health check
  GET  /stats          - Database statistics
  POST /insert         - Insert documents
  POST /build-index    - Build knowledge graph index
  POST /query          - Query knowledge graph
  POST /index-vault    - Index Obsidian vault

Starting server...
""")

    # Initialize GraphRAG
    initialize_graphrag()

    app.run(host='0.0.0.0', port=8001, debug=False)