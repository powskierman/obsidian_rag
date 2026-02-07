#!/usr/bin/env python3
"""
Check if the Knowledge Graph matches the current state of the Vault.
Compares the internal timestamp of the graph with the latest modification time in the vault.
"""

import sys
import os
import pickle
from pathlib import Path
from datetime import datetime

# Paths
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.getenv("OBSIDIAN_RAG_DATA_DIR", "/Users/michel/obsidian_rag_local_data")).expanduser()
GRAPH_PATH = Path(os.getenv("GRAPH_PATH", str(DATA_ROOT / "graph_data" / "knowledge_graph_full.pkl")))
# Try to find vault path dynamically or fallback to hardcoded
VAULT_PATH = Path(os.getenv("OBSIDIAN_VAULT_PATH", ""))
if not VAULT_PATH.exists():
     # Try relative default
     VAULT_PATH = REPO_ROOT / "vault"
     if not VAULT_PATH.exists():
         # Fallback to the user's path known from context if available, otherwise just warn
         VAULT_PATH = Path("/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/vault")

def get_latest_vault_mtime(vault_path: Path):
    """Find the most recent modification time in the vault."""
    latest_mtime = 0
    latest_file = None
    
    # We only care about supported extensions
    extensions = {'.md', '.pdf'}
    
    for root, dirs, files in os.walk(vault_path):
        for file in files:
            if Path(file).suffix.lower() in extensions:
                path = Path(root) / file
                try:
                    mtime = path.stat().st_mtime
                    if mtime > latest_mtime:
                        latest_mtime = mtime
                        latest_file = path
                except OSError:
                    continue
    return latest_mtime, latest_file

def check_status():
    print(f"🔍 Checking Graph Status...")
    print(f"   Graph Path: {GRAPH_PATH}")
    
    if not GRAPH_PATH.exists():
        print(f"❌ Graph file not found at {GRAPH_PATH}")
        return

    # 1. Load Graph Timestamp
    try:
        with open(GRAPH_PATH, 'rb') as f:
            data = pickle.load(f)
            
        if isinstance(data, dict):
            graph_ts_str = data.get('timestamp')
            stats = data.get('stats', {})
            count = stats.get('notes', 'N/A')
            if graph_ts_str:
                graph_ts = datetime.fromisoformat(graph_ts_str)
                print(f"   Graph Built: {graph_ts.strftime('%Y-%m-%d %H:%M:%S')} (Internal TS)")
                print(f"   Indexed Notes: {count}")
            else:
                 # Legacy dict but no timestamp? Fallback.
                 raise ValueError("No timestamp in dict")
        else:
            # Legacy format (raw graph object)
            raise ValueError("Legacy format")

    except Exception as e:
        # Fallback to file modification time
        print(f"⚠️  Graph metadata verification failed ({e}). Falling back to file modification time.")
        mtime = GRAPH_PATH.stat().st_mtime
        graph_ts = datetime.fromtimestamp(mtime)
        print(f"   Graph Built: {graph_ts.strftime('%Y-%m-%d %H:%M:%S')} (File Version)")

    # 2. Check Vault Freshness
    if not VAULT_PATH.exists():
         print(f"⚠️  Vault path not found: {VAULT_PATH}")
         print("   (Set OBSIDIAN_VAULT_PATH env var to fix)")
         return

    print(f"   Vault Path: {VAULT_PATH}")
    latest_mtime, latest_file = get_latest_vault_mtime(VAULT_PATH)
    
    if latest_mtime == 0:
        print("❌ Could not find any files in vault.")
        return

    vault_latest_ts = datetime.fromtimestamp(latest_mtime)
    print(f"   Latest Note: {vault_latest_ts.strftime('%Y-%m-%d %H:%M:%S')} ({latest_file.name})")

    # 3. Compare
    print("-" * 40)
    # Allow small buffer (e.g. 1 second) for clock skew if running blindly
    if graph_ts >= vault_latest_ts:
        print("✅ Graph is UP TO DATE.")
    else:
        diff = vault_latest_ts - graph_ts
        print(f"⚠️  Graph is STALE by {diff}.")
        print("   Recommend running: ./Scripts/run_indexing.sh")

if __name__ == "__main__":
    check_status()
