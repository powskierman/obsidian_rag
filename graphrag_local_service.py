#!/usr/bin/env python3
"""
GraphRAG Local Service - Flask API with Ollama Monkey Patch
Stable GraphRAG integration specifically designed for Ollama
"""

import os
import json
import logging
import subprocess
import shutil
from pathlib import Path
from flask import Flask, request, jsonify
from typing import List, Dict, Any, Optional

# Apply monkey patches BEFORE importing GraphRAG
from graphrag_local_patch import apply_all_patches, verify_models
logger = logging.getLogger(__name__)

# Apply patches early
if not apply_all_patches():
    logger.error("Failed to apply monkey patches!")
    exit(1)

# Check models
if not verify_models():
    logger.warning("Some required models may not be available")

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Configuration
WORKING_DIR = os.getenv("GRAPHRAG_DIR", "/app/ragtest")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:14b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# Global state
is_initialized = False


def check_graphrag_local():
    """Check if GraphRAG is available"""
    try:
        import graphrag
        result = subprocess.run(['python', '-m', 'graphrag.index', '--help'],
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, ImportError):
        return False


GRAPHRAG_AVAILABLE = check_graphrag_local()
if not GRAPHRAG_AVAILABLE:
    logger.warning("GraphRAG-Local-Ollama not available")


def initialize_graphrag_local():
    """Initialize GraphRAG-Local-Ollama workspace"""
    global is_initialized

    try:
        # Create working directory
        os.makedirs(WORKING_DIR, exist_ok=True)
        os.makedirs(f"{WORKING_DIR}/input", exist_ok=True)

        # Initialize if not already done
        settings_file = Path(WORKING_DIR) / "settings.yaml"
        if not settings_file.exists():
            logger.info("Initializing GraphRAG-Local workspace...")

            # Initialize the workspace
            result = subprocess.run(['python', '-m', 'graphrag.index',
                                   '--init', '--root', WORKING_DIR],
                                  capture_output=True, text=True, cwd="/app")

            if result.returncode != 0:
                logger.error(f"GraphRAG-Local init failed: {result.stderr}")
                return False

            # Copy our optimized settings
            settings_source = Path("/app/settings.yaml")
            if settings_source.exists():
                shutil.copy(settings_source, settings_file)
                logger.info("✅ Custom settings applied")

        # Set environment variable
        os.environ['GRAPHRAG_API_KEY'] = 'ollama'

        is_initialized = True
        logger.info(f"✅ GraphRAG-Local workspace initialized at {WORKING_DIR}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize GraphRAG-Local: {e}")
        return False


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "graphrag-local",
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

            # Check for output directory
            output_dir = db_path / "output"
            if output_dir.exists():
                artifacts = list(output_dir.rglob("*.parquet"))
                stats_data["indexed_artifacts"] = len(artifacts)

        return jsonify(stats_data), 200

    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/index-vault', methods=['POST'])
def index_vault():
    """Index all markdown files from a vault directory"""
    try:
        data = request.json or {}
        vault_path = data.get('vault_path', '/app/vault')

        if not GRAPHRAG_AVAILABLE or not is_initialized:
            return jsonify({
                "status": "fallback",
                "message": "GraphRAG-Local not available - files would be indexed when service is configured",
                "vault_path": vault_path
            }), 200

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

        logger.info(f"Prepared {len(notes)} files for GraphRAG-Local indexing")

        # Trigger indexing
        try:
            logger.info("Starting GraphRAG-Local indexing pipeline...")
            result = subprocess.run(['python', '-m', 'graphrag.index',
                                   '--root', WORKING_DIR],
                                  capture_output=True, text=True,
                                  cwd="/app", timeout=1800)

            if result.returncode == 0:
                return jsonify({
                    "status": "success",
                    "files_indexed": len(notes),
                    "vault_path": vault_path,
                    "message": "Vault successfully indexed with GraphRAG-Local"
                }), 200
            else:
                logger.error(f"GraphRAG-Local indexing failed: {result.stderr}")
                return jsonify({
                    "status": "partial_success",
                    "files_prepared": len(notes),
                    "vault_path": vault_path,
                    "message": "Files prepared but indexing failed",
                    "error": result.stderr
                }), 200

        except subprocess.TimeoutExpired:
            return jsonify({
                "status": "partial_success",
                "files_prepared": len(notes),
                "vault_path": vault_path,
                "message": "Files prepared but indexing timed out",
                "error": "Indexing timed out after 30 minutes"
            }), 200
        except Exception as index_error:
            logger.error(f"Indexing failed: {index_error}")
            return jsonify({
                "status": "partial_success",
                "files_prepared": len(notes),
                "vault_path": vault_path,
                "message": "Files prepared but indexing failed",
                "error": str(index_error)
            }), 200

    except Exception as e:
        logger.error(f"Index vault error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/build-index', methods=['POST'])
def build_index():
    """Build the knowledge graph index"""
    try:
        if not GRAPHRAG_AVAILABLE or not is_initialized:
            return jsonify({"error": "GraphRAG-Local not available or initialized"}), 500

        logger.info("Starting GraphRAG-Local indexing...")
        result = subprocess.run(['python', '-m', 'graphrag.index',
                               '--root', WORKING_DIR],
                              capture_output=True, text=True,
                              cwd="/app", timeout=1800)

        if result.returncode == 0:
            return jsonify({
                "status": "success",
                "message": "Knowledge graph index built successfully",
                "output": result.stdout
            }), 200
        else:
            logger.error(f"GraphRAG-Local indexing failed: {result.stderr}")
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


@app.route('/query', methods=['POST'])
def query_graph():
    """Query the knowledge graph using GraphRAG-Local"""
    try:
        data = request.json
        query_text = data.get('query')
        mode = data.get('mode', 'global')  # global or local

        if not query_text:
            return jsonify({"error": "No query provided"}), 400

        if not GRAPHRAG_AVAILABLE or not is_initialized:
            return jsonify({
                "query": query_text,
                "mode": mode,
                "result": f"GraphRAG-Local service unavailable. Your query '{query_text}' would be processed in {mode} mode when the service is properly configured."
            }), 200

        # Validate mode
        valid_modes = ['global', 'local']
        if mode not in valid_modes:
            return jsonify({"error": f"Invalid mode. Use: {valid_modes}"}), 400

        # Check if index exists
        output_dir = Path(WORKING_DIR) / "output"
        if not output_dir.exists() or not list(output_dir.rglob("*.parquet")):
            return jsonify({
                "error": "No knowledge graph index found. Please run /build-index first.",
                "query": query_text,
                "mode": mode
            }), 400

        # Execute query
        try:
            logger.info(f"Executing GraphRAG-Local {mode} query: {query_text}")
            result = subprocess.run(['python', '-m', 'graphrag.query',
                                   '--root', WORKING_DIR,
                                   '--method', mode,
                                   query_text],
                                  capture_output=True, text=True,
                                  cwd="/app", timeout=300)

            if result.returncode == 0:
                return jsonify({
                    "query": query_text,
                    "mode": mode,
                    "result": result.stdout.strip()
                }), 200
            else:
                logger.error(f"GraphRAG-Local query failed: {result.stderr}")
                return jsonify({
                    "query": query_text,
                    "mode": mode,
                    "result": f"Query failed: {result.stderr}"
                }), 200

        except subprocess.TimeoutExpired:
            return jsonify({
                "query": query_text,
                "mode": mode,
                "result": "Query timed out after 5 minutes"
            }), 200
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return jsonify({
                "query": query_text,
                "mode": mode,
                "result": f"Query error: {str(e)}"
            }), 200

    except Exception as e:
        logger.error(f"Query error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info(f"""
╔══════════════════════════════════════════════════════════╗
║       GraphRAG-Local Service - Ollama Integration       ║
╚══════════════════════════════════════════════════════════╝

📂 Working Dir: {WORKING_DIR}
🤖 LLM Model:   {LLM_MODEL}
🔤 Embed Model: {EMBED_MODEL}
🌐 Ollama Host: {OLLAMA_HOST}
📦 GraphRAG:    {'Available' if GRAPHRAG_AVAILABLE else 'Not Available'}

Endpoints:
  GET  /health         - Health check
  GET  /stats          - Database statistics
  POST /build-index    - Build knowledge graph index
  POST /query          - Query knowledge graph
  POST /index-vault    - Index Obsidian vault

Starting server...
""")

    # Initialize GraphRAG-Local
    initialize_graphrag_local()

    app.run(host='0.0.0.0', port=8001, debug=False)