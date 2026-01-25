#!/usr/bin/env python3
"""
Verify Vector Database Completeness

This script compares the files in your Obsidian vault against the documents
indexed in ChromaDB to identify:
- Files that should be indexed but are missing
- Files that failed to index
- Overall indexing coverage statistics
"""

import os
import sys
import json
import requests
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add src to path for imports
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from indexing.index_vault import should_process, get_cache_path, load_index_cache

SUPPORTED_EXTENSIONS = {".md", ".pdf"}


def get_vault_files(vault_path: Path) -> dict:
    """
    Scan vault and return dict of files that should be indexed.
    Returns: {relative_path: {filepath, size, modified, extension}}
    """
    vault_files = {}
    
    for root, dirs, files in os.walk(vault_path):
        for name in files:
            filepath = Path(root) / name
            
            if not should_process(filepath):
                continue
            
            try:
                rel_path = str(filepath.relative_to(vault_path))
                file_stats = filepath.stat()
                
                vault_files[rel_path] = {
                    "filepath": str(filepath),
                    "size": file_stats.st_size,
                    "modified": datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                    "extension": filepath.suffix.lower()
                }
            except Exception as e:
                print(f"  ⚠️  Error processing {filepath}: {e}")
    
    return vault_files


def get_indexed_files(embedding_service_url: str) -> dict:
    """
    Query embedding service to get all indexed files.
    Returns: {filepath: {chunks, size_estimate}}
    """
    try:
        # Get stats from embedding service
        response = requests.get(
            f"{embedding_service_url}/stats",
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to get stats from embedding service: {response.status_code}")
            return {}
        
        stats = response.json()
        
        # Try to get detailed file list if available
        # This assumes the embedding service has a way to list all unique filepaths
        # If not available, we'll need to query ChromaDB directly
        
        indexed_files = {}
        
        # Parse from stats if available
        if "files" in stats:
            for file_info in stats["files"]:
                filepath = file_info.get("filepath")
                if filepath:
                    indexed_files[filepath] = {
                        "chunks": file_info.get("chunks", 0),
                        "size_estimate": file_info.get("size", 0)
                    }
        
        return indexed_files
        
    except Exception as e:
        print(f"❌ Error querying embedding service: {e}")
        return {}


def get_indexed_files_from_cache(cache_path: Path) -> dict:
    """
    Load indexed files from the incremental cache.
    Returns: {filepath: {hash, modified, size_bytes}}
    """
    cache = load_index_cache(cache_path)
    return cache


def verify_completeness(vault_path: Path, embedding_service_url: str) -> dict:
    """
    Main verification function.
    Returns comprehensive report dict.
    """
    print("=" * 80)
    print("VECTOR DATABASE COMPLETENESS VERIFICATION")
    print("=" * 80)
    print()
    
    # Step 1: Get all files from vault
    print("📂 Scanning Obsidian vault...")
    vault_files = get_vault_files(vault_path)
    print(f"   Found {len(vault_files)} files that should be indexed")
    print()
    
    # Step 2: Get indexed files from cache (more reliable than API)
    cache_path = get_cache_path(vault_path)
    print(f"📋 Loading index cache from: {cache_path}")
    indexed_files = get_indexed_files_from_cache(cache_path)
    print(f"   Found {len(indexed_files)} files in cache")
    print()
    
    # Step 3: Compare
    print("🔍 Comparing vault files against indexed files...")
    
    missing_files = []
    indexed_set = set(indexed_files.keys())
    vault_set = set(vault_files.keys())
    
    for rel_path in vault_files:
        if rel_path not in indexed_set:
            missing_files.append({
                "filepath": rel_path,
                "size": vault_files[rel_path]["size"],
                "modified": vault_files[rel_path]["modified"],
                "extension": vault_files[rel_path]["extension"]
            })
    
    # Files in cache but not in vault (orphaned)
    orphaned_files = []
    for rel_path in indexed_files:
        if rel_path not in vault_set:
            orphaned_files.append({
                "filepath": rel_path,
                "hash": indexed_files[rel_path].get("hash"),
                "modified": indexed_files[rel_path].get("modified")
            })
    
    # Statistics by file type
    stats_by_type = defaultdict(lambda: {"total": 0, "indexed": 0, "missing": 0})
    
    for rel_path, info in vault_files.items():
        ext = info["extension"]
        stats_by_type[ext]["total"] += 1
        if rel_path in indexed_set:
            stats_by_type[ext]["indexed"] += 1
        else:
            stats_by_type[ext]["missing"] += 1
    
    # Build report
    report = {
        "timestamp": datetime.now().isoformat(),
        "vault_path": str(vault_path),
        "cache_path": str(cache_path),
        "summary": {
            "total_vault_files": len(vault_files),
            "total_indexed_files": len(indexed_files),
            "missing_files": len(missing_files),
            "orphaned_files": len(orphaned_files),
            "coverage_percentage": round((len(indexed_files) / len(vault_files) * 100), 2) if vault_files else 0
        },
        "stats_by_type": dict(stats_by_type),
        "missing_files": missing_files,
        "orphaned_files": orphaned_files
    }
    
    return report


def print_report(report: dict):
    """Print human-readable report."""
    print()
    print("=" * 80)
    print("VERIFICATION REPORT")
    print("=" * 80)
    print()
    
    summary = report["summary"]
    
    print("📊 SUMMARY")
    print(f"   Total files in vault:     {summary['total_vault_files']}")
    print(f"   Total indexed files:      {summary['total_indexed_files']}")
    print(f"   Missing from index:       {summary['missing_files']}")
    print(f"   Orphaned in index:        {summary['orphaned_files']}")
    print(f"   Coverage:                 {summary['coverage_percentage']}%")
    print()
    
    # Stats by type
    if report["stats_by_type"]:
        print("📈 BREAKDOWN BY FILE TYPE")
        for ext, stats in sorted(report["stats_by_type"].items()):
            coverage = round((stats["indexed"] / stats["total"] * 100), 1) if stats["total"] > 0 else 0
            print(f"   {ext:6s}: {stats['indexed']:4d}/{stats['total']:4d} indexed ({coverage:5.1f}% coverage)")
        print()
    
    # Missing files
    if report["missing_files"]:
        print(f"❌ MISSING FILES ({len(report['missing_files'])})")
        # Show first 20
        for item in report["missing_files"][:20]:
            size_kb = item["size"] / 1024
            print(f"   • {item['filepath']} ({size_kb:.1f} KB)")
        
        if len(report["missing_files"]) > 20:
            print(f"   ... and {len(report['missing_files']) - 20} more")
        print()
    else:
        print("✅ No missing files - all vault files are indexed!")
        print()
    
    # Orphaned files
    if report["orphaned_files"]:
        print(f"🗑️  ORPHANED FILES ({len(report['orphaned_files'])})")
        print("   (These are in the index but no longer exist in the vault)")
        for item in report["orphaned_files"][:10]:
            print(f"   • {item['filepath']}")
        
        if len(report["orphaned_files"]) > 10:
            print(f"   ... and {len(report['orphaned_files']) - 10} more")
        print()
    
    print("=" * 80)


def save_report(report: dict, output_path: Path):
    """Save report as JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"📄 Full report saved to: {output_path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Verify vector database completeness against Obsidian vault"
    )
    parser.add_argument(
        "vault_path",
        nargs="?",
        help="Path to Obsidian vault (default: from OBSIDIAN_VAULT_PATH env)"
    )
    parser.add_argument(
        "--url",
        default=os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000"),
        help="Embedding service URL"
    )
    parser.add_argument(
        "--output",
        default="vector_db_verification_report.json",
        help="Output JSON report path"
    )
    
    args = parser.parse_args()
    
    # Get vault path
    vault_path = args.vault_path or os.getenv("OBSIDIAN_VAULT_PATH")
    if not vault_path:
        print("❌ No vault path specified. Use argument or set OBSIDIAN_VAULT_PATH")
        sys.exit(1)
    
    vault_path = Path(vault_path)
    if not vault_path.exists():
        print(f"❌ Vault path does not exist: {vault_path}")
        sys.exit(1)
    
    # Run verification
    report = verify_completeness(vault_path, args.url)
    
    # Print report
    print_report(report)
    
    # Save report
    output_path = Path(args.output)
    save_report(report, output_path)
    
    # Exit code based on coverage
    coverage = report["summary"]["coverage_percentage"]
    if coverage < 95:
        print()
        print(f"⚠️  WARNING: Coverage is below 95% ({coverage}%)")
        print("   Consider running incremental indexing to catch up:")
        print("   python src/indexing/index_vault.py --refresh")
        sys.exit(1)
    elif coverage < 100:
        print()
        print(f"ℹ️  Coverage is good but not perfect ({coverage}%)")
        sys.exit(0)
    else:
        print()
        print("✅ Perfect coverage - all files are indexed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
