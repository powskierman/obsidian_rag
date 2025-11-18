#!/usr/bin/env python3
"""
Helper script to find and display the latest checkpoint file
"""

from pathlib import Path
import sys

def find_latest_checkpoint(graph_data_dir: Path = None) -> str:
    """Find the latest checkpoint file"""
    if graph_data_dir is None:
        graph_data_dir = Path("graph_data")
    
    if not graph_data_dir.exists():
        return None
    
    # Find all checkpoint files
    checkpoints = sorted(graph_data_dir.glob("graph_checkpoint_*.pkl"))
    
    if not checkpoints:
        return None
    
    # Return the latest (highest number)
    return str(checkpoints[-1])

if __name__ == "__main__":
    graph_data_dir = Path("graph_data")
    
    if not graph_data_dir.exists():
        print("❌ graph_data directory not found!")
        sys.exit(1)
    
    # Find all checkpoints
    checkpoints = list(graph_data_dir.glob("graph_checkpoint_*.pkl"))
    
    if not checkpoints:
        print("❌ No checkpoint files found in graph_data/")
        sys.exit(1)
    
    # Sort numerically by chunk number (not alphabetically)
    def get_chunk_number(checkpoint_path):
        try:
            name = checkpoint_path.stem.replace("graph_checkpoint_", "")
            return int(name)
        except (ValueError, AttributeError):
            return 0
    
    checkpoints = sorted(checkpoints, key=get_chunk_number)
    
    print("📂 Available checkpoint files:")
    print("=" * 60)
    
    for checkpoint in checkpoints:
        # Extract chunk number from filename
        chunk_num = checkpoint.stem.replace("graph_checkpoint_", "")
        size_mb = checkpoint.stat().st_size / (1024 * 1024)
        mtime = checkpoint.stat().st_mtime
        from datetime import datetime
        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"  {checkpoint.name}")
        print(f"    Chunks: {chunk_num}")
        print(f"    Size: {size_mb:.1f} MB")
        print(f"    Modified: {mtime_str}")
        print()
    
    # Find latest checkpoint using same logic as retry_failed_chunks.py
    def get_chunk_number(checkpoint_path):
        try:
            name = checkpoint_path.stem.replace("graph_checkpoint_", "")
            return int(name)
        except (ValueError, AttributeError):
            return 0
    
    # Sort by modification time (most recent first)
    checkpoints_by_time = sorted(checkpoints, key=lambda p: p.stat().st_mtime, reverse=True)
    latest = checkpoints_by_time[0] if checkpoints_by_time else None
    
    if latest:
        latest_path = Path(latest)
        chunk_num = latest_path.stem.replace("graph_checkpoint_", "")
        from datetime import datetime
        mtime = datetime.fromtimestamp(latest_path.stat().st_mtime)
        print("=" * 60)
        print(f"✅ Latest checkpoint: {latest_path.name}")
        print(f"   This checkpoint will be auto-selected by retry_failed_chunks.py")
        print(f"   Contains data up to chunk {chunk_num}")
        print(f"   Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        print(f"   Full path: {latest_path.absolute()}")
        print()
        print("💡 To use this checkpoint manually, when prompted for graph file, enter:")
        print(f"   {latest_path}")

