#!/usr/bin/env python3
"""
Unified GraphRAG Service - Functional Implementation
Integrates Microsoft GraphRAG with Ollama for local knowledge graph queries
"""

import os
import json
import logging
import asyncio
from pathlib import Path
from flask import Flask, request, jsonify
from typing import List, Dict, Any, Optional
import subprocess
import shutil

# Apply Ollama patches BEFORE importing GraphRAG
try:
    from graphrag_local_patch import apply_all_patches, verify_models
    PATCHES_APPLIED = apply_all_patches()
    if not PATCHES_APPLIED:
        logging.warning("GraphRAG patches not applied - some features may not work")
except ImportError:
    logging.warning("graphrag_local_patch not available - using fallback mode")
    PATCHES_APPLIED = False

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
WORKING_DIR = os.getenv("GRAPHRAG_DIR", "./graphrag_db")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-coder:14b")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
VAULT_PATH = os.getenv("VAULT_PATH", "/app/vault")
SUPPORTED_EXTENSIONS = {".md", ".pdf"}

# Global state
is_initialized = False
settings_path = None


def check_graphrag_available():
    """Check if GraphRAG CLI is available"""
    try:
        result = subprocess.run(
            ['graphrag', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


GRAPHRAG_AVAILABLE = check_graphrag_available()


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


def initialize_graphrag_workspace():
    """Initialize GraphRAG workspace with Ollama configuration"""
    global is_initialized, settings_path

    try:
        # Create working directory structure
        os.makedirs(WORKING_DIR, exist_ok=True)
        os.makedirs(os.path.join(WORKING_DIR, "input"), exist_ok=True)
        os.makedirs(os.path.join(WORKING_DIR, "output"), exist_ok=True)
        os.makedirs(os.path.join(WORKING_DIR, "cache"), exist_ok=True)

        settings_path = Path(WORKING_DIR) / "settings.yaml"

        # Initialize if settings don't exist
        if not settings_path.exists() and GRAPHRAG_AVAILABLE:
            logger.info("Initializing GraphRAG workspace...")
            result = subprocess.run(
                ['graphrag', 'init', '--root', WORKING_DIR],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"GraphRAG init failed: {result.stderr}")
                # Create minimal settings file manually
                create_minimal_settings()
        elif not settings_path.exists():
            # Create minimal settings file
            create_minimal_settings()

        # Update settings for Ollama
        update_settings_for_ollama()

        is_initialized = True
        logger.info(f"✅ GraphRAG workspace initialized at {WORKING_DIR}")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize GraphRAG workspace: {e}")
        return False


def create_minimal_settings():
    """Create minimal settings.yaml file"""
    import yaml

    settings = {
        "llm": {
            "api_type": "openai_chat",
            "api_base": f"{OLLAMA_HOST}/v1",
            "api_key": "not_required",
            "model": LLM_MODEL,
            "max_tokens": 4000,
            "temperature": 0.1,
            "request_timeout": 180.0,
            "concurrent_requests": 1
        },
        "embeddings": {
            "api_type": "openai_embedding",
            "api_base": f"{OLLAMA_HOST}/v1",
            "api_key": "not_required",
            "model": EMBED_MODEL,
            "request_timeout": 180.0,
            "concurrent_requests": 1
        },
        "chunks": {
            "size": 1200,
            "overlap": 100
        },
        "entity_extraction": {
            "entity_types": [
                "person", "organization", "location", "event", "concept",
                "technology", "medical_condition", "treatment", "medication", "procedure"
            ]
        }
    }

    with open(settings_path, 'w') as f:
        yaml.dump(settings, f, default_flow_style=False)


def update_settings_for_ollama():
    """Update settings.yaml for Ollama integration"""
    import yaml

    if not settings_path.exists():
        return

    try:
        with open(settings_path, 'r') as f:
            settings = yaml.safe_load(f) or {}

        # Update LLM settings
        settings.setdefault("llm", {})
        settings["llm"].update({
            "api_type": "openai_chat",
            "api_base": f"{OLLAMA_HOST}/v1",
            "api_key": "not_required",
            "model": LLM_MODEL,
            "max_tokens": 4000,
            "temperature": 0.1,
            "request_timeout": 180.0,
            "concurrent_requests": 1
        })

        # Update embedding settings
        settings.setdefault("embeddings", {})
        settings["embeddings"].update({
            "api_type": "openai_embedding",
            "api_base": f"{OLLAMA_HOST}/v1",
            "api_key": "not_required",
            "model": EMBED_MODEL,
            "request_timeout": 180.0,
            "concurrent_requests": 1
        })

        # Ensure entity types include medical types
        settings.setdefault("entity_extraction", {})
        entity_types = settings["entity_extraction"].get("entity_types", [])
        medical_types = ["medical_condition", "treatment", "medication", "procedure"]
        for mt in medical_types:
            if mt not in entity_types:
                entity_types.append(mt)
        settings["entity_extraction"]["entity_types"] = entity_types

        # Write updated settings
        with open(settings_path, 'w') as f:
            yaml.dump(settings, f, default_flow_style=False)

        logger.info("✅ Settings updated for Ollama")

    except Exception as e:
        logger.error(f"Failed to update settings: {e}")


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "graphrag-unified",
        "initialized": is_initialized,
        "graphrag_available": GRAPHRAG_AVAILABLE,
        "patches_applied": PATCHES_APPLIED,
        "ollama_host": OLLAMA_HOST,
        "llm_model": LLM_MODEL,
        "embed_model": EMBED_MODEL,
        "working_dir": WORKING_DIR
    }), 200


@app.route('/stats', methods=['GET'])
def stats():
    """Get statistics about the knowledge graph"""
    try:
        db_path = Path(WORKING_DIR)
        exists = db_path.exists()

        stats_data = {
            "working_dir": str(WORKING_DIR),
            "database_exists": exists,
            "initialized": is_initialized,
            "llm_model": LLM_MODEL,
            "embed_model": EMBED_MODEL,
            "graphrag_available": GRAPHRAG_AVAILABLE,
            "patches_applied": PATCHES_APPLIED
        }

        if exists:
            # Count files
            files = list(db_path.rglob("*"))
            stats_data["total_files"] = len(files)

            # Check for indexed artifacts
            output_dir = db_path / "output"
            if output_dir.exists():
                artifacts = list(output_dir.glob("*.parquet"))
                stats_data["indexed_artifacts"] = len(artifacts)
                stats_data["indexed"] = len(artifacts) > 0

        return jsonify(stats_data), 200

    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/index-vault', methods=['POST'])
def index_vault():
    """Index all markdown and PDF files from vault directory"""
    try:
        data = request.json or {}
        vault_path = data.get('vault_path', VAULT_PATH)

        if not GRAPHRAG_AVAILABLE:
            return jsonify({
                "error": "GraphRAG CLI not available. Install with: pip install graphrag",
                "status": "error"
            }), 500

        # Load markdown and PDF files
        notes = []
        vault_dir = Path(vault_path)

        if not vault_dir.exists():
            return jsonify({"error": f"Vault path not found: {vault_path}"}), 400

        logger.info(f"Scanning vault at {vault_path}...")
        vault_files = [
            path for path in vault_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        for vault_file in vault_files:
            try:
                if vault_file.suffix.lower() == ".pdf":
                    content = extract_pdf_text(vault_file)
                else:
                    with open(vault_file, "r", encoding="utf-8") as f:
                        content = f.read()

                content = content.strip()
                if content and len(content) > 50:  # Skip very short files
                    notes.append({
                        "content": content,
                        "filename": vault_file.name,
                        "filepath": str(vault_file.relative_to(vault_dir)),
                        "filetype": vault_file.suffix.lower().lstrip(".")
                    })
            except Exception as e:
                logger.warning(f"Could not read {vault_file}: {e}")

        if not notes:
            return jsonify({"error": "No markdown/PDF files found"}), 400

        logger.info(f"Found {len(notes)} markdown/PDF files to index")

        # Write documents to input directory
        input_dir = Path(WORKING_DIR) / "input"
        input_dir.mkdir(exist_ok=True)

        # Clear existing input files
        for existing_file in input_dir.glob("*.txt"):
            existing_file.unlink()

        # Write vault content to input files
        for i, note in enumerate(notes):
            # Sanitize filename for filesystem
            safe_filename = note['filepath'].replace('/', '_').replace('\\', '_')
            safe_filename = ''.join(c for c in safe_filename if c.isalnum() or c in ('_', '-', '.'))
            filename = f"{safe_filename}_{i}.txt"
            
            with open(input_dir / filename, 'w', encoding='utf-8') as f:
                f.write(f"# {note['filename']}\n\n{note['content']}")

        logger.info(f"Prepared {len(notes)} files for GraphRAG indexing")

        # Trigger indexing
        try:
            logger.info("Starting GraphRAG indexing pipeline...")
            result = subprocess.run(
                ['graphrag', 'index', '--root', WORKING_DIR],
                capture_output=True,
                text=True,
                timeout=1800,  # 30 minutes
                cwd=WORKING_DIR
            )

            if result.returncode == 0:
                logger.info("✅ GraphRAG indexing completed successfully")
                return jsonify({
                    "status": "success",
                    "files_indexed": len(notes),
                    "vault_path": vault_path,
                    "message": "Vault successfully indexed and knowledge graph built"
                }), 200
            else:
                logger.error(f"Indexing failed: {result.stderr}")
                return jsonify({
                    "status": "error",
                    "files_prepared": len(notes),
                    "vault_path": vault_path,
                    "error": result.stderr,
                    "stdout": result.stdout
                }), 500

        except subprocess.TimeoutExpired:
            return jsonify({
                "status": "error",
                "files_prepared": len(notes),
                "error": "Indexing timed out after 30 minutes"
            }), 500
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            return jsonify({
                "status": "error",
                "files_prepared": len(notes),
                "error": str(e)
            }), 500

    except Exception as e:
        logger.error(f"Index vault error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/build-index', methods=['POST'])
def build_index():
    """Build the knowledge graph index from input directory"""
    try:
        if not GRAPHRAG_AVAILABLE:
            return jsonify({
                "error": "GraphRAG CLI not available",
                "status": "error"
            }), 500

        input_dir = Path(WORKING_DIR) / "input"
        if not input_dir.exists() or not list(input_dir.glob("*.txt")):
            return jsonify({
                "error": "No input files found. Run /index-vault first.",
                "status": "error"
            }), 400

        logger.info("Starting GraphRAG indexing pipeline...")
        result = subprocess.run(
            ['graphrag', 'index', '--root', WORKING_DIR],
            capture_output=True,
            text=True,
            timeout=1800,
            cwd=WORKING_DIR
        )

        if result.returncode == 0:
            return jsonify({
                "status": "success",
                "message": "Knowledge graph index built successfully",
                "output": result.stdout
            }), 200
        else:
            logger.error(f"Indexing failed: {result.stderr}")
            return jsonify({
                "status": "error",
                "error": "Indexing failed",
                "details": result.stderr,
                "stdout": result.stdout
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            "status": "error",
            "error": "Indexing timed out after 30 minutes"
        }), 500
    except Exception as e:
        logger.error(f"Index building error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/query', methods=['POST'])
def query_graph():
    """Query the knowledge graph using GraphRAG"""
    try:
        data = request.json
        query_text = data.get('query')
        mode = data.get('mode', 'global')  # 'local' or 'global'

        if not query_text:
            return jsonify({"error": "No query provided"}), 400

        if not GRAPHRAG_AVAILABLE:
            return jsonify({
                "error": "GraphRAG CLI not available",
                "query": query_text,
                "mode": mode
            }), 500

        # Validate mode
        valid_modes = ['local', 'global']
        if mode not in valid_modes:
            return jsonify({
                "error": f"Invalid mode. Use: {valid_modes}",
                "query": query_text
            }), 400

        # Check if index exists
        output_dir = Path(WORKING_DIR) / "output"
        if not output_dir.exists() or not list(output_dir.glob("*.parquet")):
            return jsonify({
                "error": "No knowledge graph index found. Please run /index-vault or /build-index first.",
                "query": query_text,
                "mode": mode,
                "hint": "Call POST /index-vault to build the index"
            }), 400

        # Execute query
        logger.info(f"Executing GraphRAG {mode} query: {query_text}")
        try:
            result = subprocess.run(
                ['graphrag', 'query',
                 '--root', WORKING_DIR,
                 '--method', mode,
                 query_text],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes
                cwd=WORKING_DIR
            )

            if result.returncode == 0:
                response_text = result.stdout.strip()
                return jsonify({
                    "query": query_text,
                    "mode": mode,
                    "result": response_text,
                    "status": "success"
                }), 200
            else:
                logger.error(f"Query failed: {result.stderr}")
                return jsonify({
                    "query": query_text,
                    "mode": mode,
                    "result": f"Query failed: {result.stderr}",
                    "status": "error"
                }), 200  # Return 200 but with error in result

        except subprocess.TimeoutExpired:
            return jsonify({
                "query": query_text,
                "mode": mode,
                "result": "Query timed out after 5 minutes",
                "status": "error"
            }), 200
        except Exception as e:
            logger.error(f"Query execution error: {e}")
            return jsonify({
                "query": query_text,
                "mode": mode,
                "result": f"Query error: {str(e)}",
                "status": "error"
            }), 200

    except Exception as e:
        logger.error(f"Query error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logger.info(f"""
╔══════════════════════════════════════════════════════════╗
║       Unified GraphRAG Service - Ollama Integration     ║
╚══════════════════════════════════════════════════════════╝

📂 Working Dir: {WORKING_DIR}
🤖 LLM Model:   {LLM_MODEL}
🔤 Embed Model: {EMBED_MODEL}
🌐 Ollama Host: {OLLAMA_HOST}
📦 GraphRAG:    {'Available' if GRAPHRAG_AVAILABLE else 'Not Installed'}
🔧 Patches:     {'Applied' if PATCHES_APPLIED else 'Not Applied'}

Endpoints:
  GET  /health         - Health check
  GET  /stats          - Database statistics
  POST /index-vault    - Index Obsidian vault
  POST /build-index    - Build knowledge graph index
  POST /query          - Query knowledge graph

Starting server...
""")

    # Initialize workspace
    initialize_graphrag_workspace()

    # Verify models if patches are available
    if PATCHES_APPLIED:
        verify_models()

    app.run(host='0.0.0.0', port=8002, debug=False)







