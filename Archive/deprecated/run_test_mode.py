#!/usr/bin/env python3
"""
Helper script to run test mode non-interactively
Usage: export ANTHROPIC_API_KEY="your-key" && python run_test_mode.py

Make sure to activate venv first:
  source venv/bin/activate
  python run_test_mode.py
"""

import os
import sys
from pathlib import Path

# Ensure we're using the venv Python
venv_python = Path(__file__).parent / "venv" / "bin" / "python"
if venv_python.exists() and sys.executable != str(venv_python):
    print("⚠️  Warning: Not using venv Python. Please run:")
    print(f"   source venv/bin/activate")
    print(f"   python run_test_mode.py")
    print(f"\nOr use: {venv_python} run_test_mode.py")
    sys.exit(1)

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_knowledge_graph import build_graph_from_vault

def main():
    # Get API key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY environment variable not set")
        print("\nPlease set it with:")
        print('  export ANTHROPIC_API_KEY="sk-ant-..."')
        sys.exit(1)
    
    # Default paths
    default_chroma_path = "/Users/michel/Library/Mobile Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/chroma_db"
    default_vault_path = "/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel"
    
    # Use defaults
    chroma_path = default_chroma_path if Path(default_chroma_path).exists() else None
    vault_path = default_vault_path if Path(default_vault_path).exists() else None
    
    if not chroma_path and not vault_path:
        print("❌ Neither ChromaDB nor Vault path exists")
        print(f"   ChromaDB: {default_chroma_path}")
        print(f"   Vault: {default_vault_path}")
        sys.exit(1)
    
    print("=" * 70)
    print("🧪 RUNNING TEST MODE - 50 chunks")
    print("=" * 70)
    print(f"ChromaDB: {chroma_path if chroma_path else 'Not found'}")
    print(f"Vault: {vault_path if vault_path else 'Not found'}")
    print("\nThis will:")
    print("  - Process 50 chunks")
    print("  - Take ~2-3 minutes")
    print("  - Cost ~$0.50")
    print("  - Create knowledge_graph_test.pkl")
    print("\nStarting...\n")
    
    # Run test mode
    try:
        build_graph_from_vault(
            api_key=api_key,
            test_mode=True,
            n_test_chunks=50,
            chroma_db_path=chroma_path,
            vault_path=vault_path
        )
        print("\n" + "=" * 70)
        print("✅ TEST MODE COMPLETE!")
        print("=" * 70)
        print("\nNext steps:")
        print("  1. Review knowledge_graph_test.pkl")
        print("  2. Check knowledge_graph_test.json for visualization")
        print("  3. Run interactive queries:")
        print("     python build_knowledge_graph.py")
        print("     (Choose option 4)")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

