#!/usr/bin/env python3
"""
GraphRAG-Claude Service - Using GraphRAG 2.7.0 with Claude models
Provides a REST API for GraphRAG operations with Claude models for indexing.
"""

import asyncio
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import requests
from flask import Flask, request, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuration
WORKING_DIR = "/app/ragtest"
VAULT_DIR = "/app/vault"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
SUPPORTED_EXTENSIONS = {".md", ".pdf"}

def verify_claude_setup() -> bool:
    """Verify Claude API key is available"""
    if not ANTHROPIC_API_KEY:
        logger.error("❌ ANTHROPIC_API_KEY environment variable not set")
        return False

    if ANTHROPIC_API_KEY.startswith("sk-ant-"):
        logger.info("✅ Claude API key detected")
        return True
    else:
        logger.error("❌ Invalid Claude API key format")
        return False

def verify_ollama_setup() -> bool:
    """Verify Ollama is available for embeddings"""
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            nomic_available = any('nomic-embed-text' in model.get('name', '') for model in models)
            if nomic_available:
                logger.info("✅ Ollama and nomic-embed-text detected")
                return True
            else:
                logger.error("❌ nomic-embed-text model not found in Ollama")
                return False
        else:
            logger.error("❌ Ollama not accessible")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to connect to Ollama: {e}")
        return False


def extract_pdf_text(pdf_path: Path) -> str:
    """Extract text from a PDF file using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning(f"pypdf not installed; skipping PDF: {pdf_path}")
        return ""

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        logger.warning(f"Failed to read PDF {pdf_path}: {e}")
        return ""

    pages_text = []
    for page_index, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            pages_text.append(f"[Page {page_index}]\n{page_text}")

    return "\n\n".join(pages_text).strip()

def initialize_workspace() -> bool:
    """Initialize GraphRAG workspace"""
    try:
        # Create necessary directories
        os.makedirs(f"{WORKING_DIR}/input", exist_ok=True)
        os.makedirs(f"{WORKING_DIR}/output", exist_ok=True)
        os.makedirs(f"{WORKING_DIR}/cache", exist_ok=True)

        # Copy Claude settings file
        import shutil
        shutil.copy("/app/settings_claude.yaml", f"{WORKING_DIR}/settings.yaml")
        logger.info(f"Copied Claude settings to {WORKING_DIR}/settings.yaml")

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
        vault_files = [
            path for path in Path(VAULT_DIR).rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        for file_path in vault_files:
            if file_path.is_file():
                try:
                    if file_path.suffix.lower() == ".pdf":
                        content = extract_pdf_text(file_path)
                    else:
                        # Read markdown file
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()

                    if not content or not content.strip():
                        continue

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

def estimate_cost(file_count: int) -> Dict[str, float]:
    """Estimate Claude API costs for indexing"""
    # Rough estimates based on typical GraphRAG usage
    # These are conservative estimates

    avg_tokens_per_file = 2000  # Average tokens per markdown file
    total_input_tokens = file_count * avg_tokens_per_file

    # GraphRAG typically processes text multiple times
    entity_extraction_multiplier = 2
    embedding_multiplier = 1
    community_report_multiplier = 0.5

    # Claude 3.5 Haiku pricing (as of 2024)
    claude_haiku_input_cost = 1.0 / 1000000  # $1.0 per 1M input tokens
    claude_haiku_output_cost = 5.0 / 1000000  # $5.0 per 1M output tokens

    # Ollama embeddings are free (local processing)
    embedding_cost = 0.0  # Free with Ollama

    # Estimate token usage
    llm_input_tokens = total_input_tokens * entity_extraction_multiplier
    llm_output_tokens = llm_input_tokens * 0.3  # Estimated output ratio
    embedding_tokens = total_input_tokens * embedding_multiplier

    # Calculate costs
    llm_cost = (llm_input_tokens * claude_haiku_input_cost) + (llm_output_tokens * claude_haiku_output_cost)
    embedding_cost_total = embedding_tokens * embedding_cost

    total_cost = llm_cost + embedding_cost_total

    return {
        "estimated_total_cost": round(total_cost, 2),
        "llm_cost": round(llm_cost, 2),
        "embedding_cost": round(embedding_cost_total, 2),
        "file_count": file_count,
        "estimated_tokens": total_input_tokens
    }

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

        # Get cost estimate
        cost_estimate = estimate_cost(vault_files)

        return jsonify({
            "database_exists": indexed_artifacts > 0,
            "initialized": True,
            "graphrag_available": True,
            "indexed_artifacts": indexed_artifacts,
            "total_files": vault_files,
            "llm_model": "claude-3-5-haiku-20241022",
            "embed_model": "nomic-embed-text",
            "working_dir": WORKING_DIR,
            "cost_estimate": cost_estimate
        })

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/cost-estimate', methods=['GET'])
def cost_estimate():
    """Get detailed cost estimate for indexing"""
    try:
        vault_files = len(list(Path(VAULT_DIR).rglob("*.md"))) if Path(VAULT_DIR).exists() else 0
        estimate = estimate_cost(vault_files)

        return jsonify({
            "cost_breakdown": estimate,
            "recommendation": "Proceed" if estimate["estimated_total_cost"] < 50 else "Review - High cost estimated",
            "notes": [
                "Estimates are conservative and may be higher than actual costs",
                "Using cost-effective models: Claude 3.5 Haiku + free Ollama embeddings",
                "Embeddings are processed locally via Ollama (no additional cost)",
                "Actual costs depend on content complexity and duplication",
                f"You have $250 Claude Code credits available"
            ]
        })

    except Exception as e:
        logger.error(f"Error calculating cost estimate: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/build-index', methods=['POST'])
def build_index():
    """Build GraphRAG index using Claude models"""
    try:
        # Check if API keys are set
        if not verify_claude_setup():
            return jsonify({"error": "Claude API key not configured"}), 400

        if not verify_ollama_setup():
            return jsonify({"error": "Ollama not available or nomic-embed-text not found"}), 400

        logger.info("Starting GraphRAG indexing with Claude models...")

        # Copy vault files to input directory
        file_count = copy_vault_files()
        if file_count == 0:
            return jsonify({"error": "No files found to index"}), 400

        # Show cost estimate
        cost_est = estimate_cost(file_count)
        logger.info(f"💰 Estimated cost: ${cost_est['estimated_total_cost']:.2f}")

        # Run GraphRAG indexing
        cmd = [
            "python", "-m", "graphrag",
            "index",
            "--root", WORKING_DIR,
            "--verbose"
        ]

        logger.info(f"Running indexing command: {' '.join(cmd)}")

        # Set environment variables
        env = os.environ.copy()
        env.update({
            "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
            "OLLAMA_HOST": OLLAMA_HOST
        })

        # Run indexing (this can take a long time and cost money)
        result = subprocess.run(
            cmd,
            cwd=WORKING_DIR,
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hour timeout
            env=env
        )

        if result.returncode == 0:
            artifacts = get_indexed_artifacts()
            logger.info(f"✅ GraphRAG indexing completed successfully. Artifacts: {artifacts}")
            return jsonify({
                "status": "success",
                "message": "Index built successfully",
                "artifacts": artifacts,
                "files_processed": file_count,
                "estimated_cost": cost_est["estimated_total_cost"]
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

        # Check if API keys are set
        if not verify_claude_setup():
            return jsonify({"error": "Claude API key not configured"}), 400

        if not verify_ollama_setup():
            return jsonify({"error": "Ollama not available or nomic-embed-text not found"}), 400

        # Check if index exists
        if get_indexed_artifacts() == 0:
            return jsonify({"error": "No index found. Please build index first."}), 400

        # Run GraphRAG query
        cmd = [
            "python", "-m", "graphrag",
            "query",
            "--root", WORKING_DIR,
            "--method", mode,
            query_text
        ]

        logger.info(f"Running query: {' '.join(cmd)}")

        # Set environment variables
        env = os.environ.copy()
        env.update({
            "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
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
║        GraphRAG-Claude Service - Using Claude Models    ║
╚══════════════════════════════════════════════════════════╝
""")

    print(f"📂 Working Dir: {WORKING_DIR}")
    print(f"🤖 LLM Model:   claude-3-5-haiku-20241022")
    print(f"🔤 Embed Model: nomic-embed-text")
    print(f"🌐 API:         Anthropic Claude + Ollama Embeddings")
    print(f"📦 GraphRAG:    2.7.0")
    print()
    print("Endpoints:")
    print("  GET  /health         - Health check")
    print("  GET  /stats          - Database statistics")
    print("  GET  /cost-estimate  - Cost estimation")
    print("  POST /build-index    - Build knowledge graph index")
    print("  POST /query          - Query knowledge graph")
    print()
    print("⚠️  NOTE: Indexing will use Claude API and incur costs")
    print("💳 Available: $250 Claude Code credits")
    print("🔄 Embeddings: Free via Ollama (nomic-embed-text)")
    print()

    # Check Claude setup
    if not verify_claude_setup():
        logger.error("❌ Claude setup failed. Please set ANTHROPIC_API_KEY environment variable.")
        print("\nTo use this service:")
        print("1. Set ANTHROPIC_API_KEY environment variable with your Claude API key")
        print("2. Ensure Ollama is running with nomic-embed-text model")
        print("3. Restart the service")
        sys.exit(1)

    # Check Ollama setup
    if not verify_ollama_setup():
        logger.error("❌ Ollama setup failed. Please ensure Ollama is running and nomic-embed-text is available.")
        print("\nTo fix Ollama setup:")
        print("1. Start Ollama: ollama serve")
        print("2. Pull model: ollama pull nomic-embed-text")
        print("3. Restart the service")
        sys.exit(1)

    if not initialize_workspace():
        logger.error("❌ Failed to initialize GraphRAG workspace.")
        sys.exit(1)

    logger.info("✅ GraphRAG-Claude service initialized successfully!")

    # Start Flask server
    app.run(host='0.0.0.0', port=8001, debug=False)
