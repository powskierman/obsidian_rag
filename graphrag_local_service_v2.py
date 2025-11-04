#!/usr/bin/env python3
"""
GraphRAG-Local Service v2.0 - Using GraphRAG 2.7.0 with LiteLLM
Provides a REST API for GraphRAG operations with Ollama local models.
"""

import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import litellm
import requests
from flask import Flask, request, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
WORKING_DIR = "/app/ragtest"
VAULT_DIR = "/app/vault"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")

# Configure LiteLLM for Ollama
litellm.set_verbose = False
os.environ["LITELLM_LOG"] = "ERROR"

def verify_ollama_connection() -> bool:
    """Verify Ollama is accessible and models are available"""
    try:
        # Check Ollama connection
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        if response.status_code != 200:
            logger.error(f"Ollama not accessible at {OLLAMA_HOST}")
            return False

        models = response.json().get("models", [])
        model_names = [model["name"] for model in models]

        logger.info(f"Available models: {model_names}")

        # Check if required models are available
        llm_available = any(LLM_MODEL in name for name in model_names)
        embed_available = any(EMBED_MODEL in name for name in model_names)

        if not llm_available:
            logger.warning(f"LLM model '{LLM_MODEL}' not found. Please run: ollama pull {LLM_MODEL}")

        if not embed_available:
            logger.warning(f"Embedding model '{EMBED_MODEL}' not found. Please run: ollama pull {EMBED_MODEL}")

        return llm_available and embed_available

    except Exception as e:
        logger.error(f"Error checking Ollama: {e}")
        return False

def test_litellm_integration() -> bool:
    """Test LiteLLM integration with Ollama"""
    try:
        logger.info("Testing LiteLLM + Ollama integration...")

        # Test LLM
        response = litellm.completion(
            model=f"ollama/{LLM_MODEL}",
            messages=[{"role": "user", "content": "Hello, respond with 'OK' only."}],
            api_base=f"{OLLAMA_HOST}/v1",
            max_tokens=10,
            timeout=30
        )

        if "OK" in response.choices[0].message.content:
            logger.info("✅ LiteLLM LLM integration successful")
        else:
            logger.warning("⚠️ LiteLLM LLM integration may have issues")

        # Test embedding
        try:
            embed_response = litellm.embedding(
                model=f"ollama/{EMBED_MODEL}",
                input=["test embedding"],
                api_base=f"{OLLAMA_HOST}/v1"
            )

            if embed_response.data and len(embed_response.data[0].embedding) > 0:
                logger.info("✅ LiteLLM embedding integration successful")
                return True
            else:
                logger.warning("⚠️ LiteLLM embedding may have issues")
                return False

        except Exception as e:
            logger.warning(f"⚠️ LiteLLM embedding test failed: {e}")
            return False

    except Exception as e:
        logger.error(f"❌ LiteLLM integration failed: {e}")
        return False

def initialize_workspace() -> bool:
    """Initialize GraphRAG workspace"""
    try:
        # Create necessary directories
        os.makedirs(f"{WORKING_DIR}/input", exist_ok=True)
        os.makedirs(f"{WORKING_DIR}/output", exist_ok=True)
        os.makedirs(f"{WORKING_DIR}/cache", exist_ok=True)

        # Initialize GraphRAG if not already done
        settings_file = f"{WORKING_DIR}/settings.yaml"
        if not os.path.exists(settings_file):
            # Copy our settings file
            import shutil
            shutil.copy("/app/settings.yaml", settings_file)
            logger.info(f"Copied settings to {settings_file}")

        logger.info(f"✅ GraphRAG workspace initialized at {WORKING_DIR}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to initialize workspace: {e}")
        return False

def copy_vault_files() -> int:
    """Copy files from vault to GraphRAG input directory"""
    try:
        input_dir = f"{WORKING_DIR}/input"

        # Clear existing input files
        for file in Path(input_dir).glob("*.txt"):
            file.unlink()

        # Copy vault files and convert to txt
        file_count = 0
        for file_path in Path(VAULT_DIR).rglob("*.md"):
            if file_path.is_file():
                try:
                    # Read markdown file
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    # Write as txt file
                    txt_filename = f"{file_path.stem}_{file_count:04d}.txt"
                    txt_path = Path(input_dir) / txt_filename

                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(content)

                    file_count += 1

                except Exception as e:
                    logger.warning(f"Failed to process {file_path}: {e}")
                    continue

        logger.info(f"Copied {file_count} files from vault to input directory")
        return file_count

    except Exception as e:
        logger.error(f"Error copying vault files: {e}")
        return 0

def get_indexed_artifacts() -> int:
    """Get count of indexed artifacts"""
    try:
        output_dir = Path(f"{WORKING_DIR}/output")
        if not output_dir.exists():
            return 0

        # Find the most recent run directory
        run_dirs = [d for d in output_dir.iterdir() if d.is_dir()]
        if not run_dirs:
            return 0

        latest_run = max(run_dirs, key=lambda x: x.stat().st_mtime)
        artifacts_dir = latest_run / "artifacts"

        if not artifacts_dir.exists():
            return 0

        # Count parquet files as artifacts
        artifact_count = len(list(artifacts_dir.glob("*.parquet")))
        return artifact_count

    except Exception as e:
        logger.error(f"Error counting artifacts: {e}")
        return 0

# Flask Routes

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/stats', methods=['GET'])
def stats():
    """Get database statistics"""
    try:
        indexed_artifacts = get_indexed_artifacts()

        # Count vault files
        vault_files = len(list(Path(VAULT_DIR).rglob("*.md"))) if Path(VAULT_DIR).exists() else 0

        return jsonify({
            "database_exists": indexed_artifacts > 0,
            "initialized": True,
            "graphrag_available": True,
            "indexed_artifacts": indexed_artifacts,
            "total_files": vault_files,
            "llm_model": LLM_MODEL,
            "embed_model": EMBED_MODEL,
            "working_dir": WORKING_DIR
        })

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/build-index', methods=['POST'])
def build_index():
    """Build GraphRAG index"""
    try:
        logger.info("Starting GraphRAG indexing...")

        # Copy vault files to input directory
        file_count = copy_vault_files()
        if file_count == 0:
            return jsonify({"error": "No files found to index"}), 400

        # Run GraphRAG indexing
        cmd = [
            "python", "-m", "graphrag.index",
            "--root", WORKING_DIR,
            "--verbose"
        ]

        logger.info(f"Running indexing command: {' '.join(cmd)}")

        # Set environment variables for LiteLLM
        env = os.environ.copy()
        env.update({
            "LITELLM_LOG": "ERROR",
            "OLLAMA_HOST": OLLAMA_HOST
        })

        # Run indexing (this can take a long time)
        result = subprocess.run(
            cmd,
            cwd=WORKING_DIR,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
            env=env
        )

        if result.returncode == 0:
            artifacts = get_indexed_artifacts()
            logger.info(f"✅ GraphRAG indexing completed successfully. Artifacts: {artifacts}")
            return jsonify({
                "status": "success",
                "message": "Index built successfully",
                "artifacts": artifacts,
                "files_processed": file_count
            })
        else:
            logger.error(f"❌ GraphRAG indexing failed: {result.stderr}")
            return jsonify({
                "error": "Indexing failed",
                "details": result.stderr,
                "stdout": result.stdout
            }), 500

    except subprocess.TimeoutExpired:
        logger.error("GraphRAG indexing timed out")
        return jsonify({"error": "Indexing timed out"}), 500
    except Exception as e:
        logger.error(f"Error during indexing: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/query', methods=['POST'])
def query():
    """Query GraphRAG knowledge graph"""
    try:
        data = request.get_json()
        query_text = data.get('query', '')
        mode = data.get('mode', 'local')  # 'local' or 'global'

        if not query_text:
            return jsonify({"error": "Query text is required"}), 400

        # Check if index exists
        if get_indexed_artifacts() == 0:
            return jsonify({"error": "No index found. Please build index first."}), 400

        # Run GraphRAG query
        cmd = [
            "python", "-m", "graphrag.query",
            "--root", WORKING_DIR,
            "--method", mode,
            query_text
        ]

        logger.info(f"Running query: {' '.join(cmd)}")

        # Set environment variables for LiteLLM
        env = os.environ.copy()
        env.update({
            "LITELLM_LOG": "ERROR",
            "OLLAMA_HOST": OLLAMA_HOST
        })

        result = subprocess.run(
            cmd,
            cwd=WORKING_DIR,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout for queries
            env=env
        )

        if result.returncode == 0:
            response_text = result.stdout.strip()
            logger.info(f"✅ GraphRAG query completed")
            return jsonify({
                "result": response_text,
                "mode": mode,
                "query": query_text
            })
        else:
            logger.error(f"❌ GraphRAG query failed: {result.stderr}")
            return jsonify({
                "error": "Query failed",
                "details": result.stderr
            }), 500

    except subprocess.TimeoutExpired:
        logger.error("GraphRAG query timed out")
        return jsonify({"error": "Query timed out"}), 500
    except Exception as e:
        logger.error(f"Error during query: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║       GraphRAG-Local Service v2.0 - LiteLLM Integration ║
╚══════════════════════════════════════════════════════════╝
""")

    print(f"📂 Working Dir: {WORKING_DIR}")
    print(f"🤖 LLM Model:   {LLM_MODEL}")
    print(f"🔤 Embed Model: {EMBED_MODEL}")
    print(f"🌐 Ollama Host: {OLLAMA_HOST}")
    print(f"📦 GraphRAG:    2.7.0 with LiteLLM")
    print()
    print("Endpoints:")
    print("  GET  /health         - Health check")
    print("  GET  /stats          - Database statistics")
    print("  POST /build-index    - Build knowledge graph index")
    print("  POST /query          - Query knowledge graph")
    print()
    print("Starting server...")
    print()

    # Initialize components
    if not verify_ollama_connection():
        logger.error("❌ Ollama connection failed. Please ensure Ollama is running and models are available.")
        sys.exit(1)

    if not test_litellm_integration():
        logger.error("❌ LiteLLM integration failed. Check Ollama and model availability.")
        sys.exit(1)

    if not initialize_workspace():
        logger.error("❌ Failed to initialize GraphRAG workspace.")
        sys.exit(1)

    logger.info("✅ GraphRAG-Local v2.0 initialized successfully!")

    # Start Flask server
    app.run(host='0.0.0.0', port=8001, debug=False)