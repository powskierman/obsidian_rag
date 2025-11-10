# Transferring Graph Building Between Machines

## ✅ Yes, Processed Chunks Are Saved!

The improved graph builder saves progress in multiple ways:

### 1. **Checkpoint Files** (Every 10 chunks)
- Location: `graph_data/graph_checkpoint_*.pkl`
- Created: Every `batch_size` chunks (default: 10)
- Contains: Full graph + stats + processed_chunks

### 2. **Final Graph File** (On completion)
- Location: `graph_data/knowledge_graph_full.pkl`
- Contains: Complete graph + stats + processed_chunks

### 3. **Processed Chunks Tracking**
- Saved in: `processed_chunks` set (chunk hashes)
- Prevents: Re-processing the same chunks
- Enables: Resume from where you left off

---

## How to Transfer Between Machines

### Step 1: Stop the Process on MacBook

**Graceful stop:**
- Press `Ctrl+C` once (let current chunk finish)
- Wait for checkpoint to save
- Process will exit cleanly

**Or force stop:**
- Press `Ctrl+C` twice (force kill)
- Last checkpoint should still be saved

### Step 2: Transfer Files to Mac Mini

**Files to transfer:**
```bash
# Main graph file (if exists)
graph_data/knowledge_graph_full.pkl

# Latest checkpoint (most recent)
graph_data/graph_checkpoint_*.pkl  # Get the highest number

# Or transfer entire graph_data directory
graph_data/
```

**Transfer methods:**
1. **iCloud** (if using iCloud Drive):
   - Files are already synced if in iCloud folder
   - Just wait for sync to complete

2. **Manual copy:**
   ```bash
   # On MacBook
   tar -czf graph_backup.tar.gz graph_data/
   
   # Transfer to Mac Mini (via AirDrop, USB, network, etc.)
   
   # On Mac Mini
   tar -xzf graph_backup.tar.gz
   ```

3. **Network copy:**
   ```bash
   # On Mac Mini
   scp -r user@macbook:/path/to/obsidian_rag/graph_data ./
   ```

### Step 3: Resume on Mac Mini

**Option A: Resume from checkpoint**
```bash
# Find latest checkpoint
ls -t graph_data/graph_checkpoint_*.pkl | head -1

# Resume using that checkpoint
python retry_failed_chunks.py
# When prompted for graph file, enter the checkpoint path
```

**Option B: Resume from main graph**
```bash
# If knowledge_graph_full.pkl exists
python retry_failed_chunks.py
# Press Enter for default (will use knowledge_graph_full.pkl)
```

**The script will:**
1. ✅ Load existing graph (preserves all entities/relationships)
2. ✅ Load processed_chunks set (knows what's been done)
3. ✅ Skip already-processed chunks
4. ✅ Continue from where you left off

---

## What Gets Preserved

### ✅ Preserved:
- **All entities** (nodes) - 23,926+ entities
- **All relationships** (edges) - 35,030+ relationships
- **Processed chunks** - Hashes of completed chunks
- **Stats** - Chunks processed, errors, retries
- **Graph structure** - Complete NetworkX graph

### ⚠️ Not Preserved:
- **In-progress chunk** - Current chunk being processed (will be retried)
- **Failed chunks list** - Will be rebuilt if needed

---

## Example Workflow

### On MacBook:
```bash
# Start processing
python retry_failed_chunks.py

# ... processes 1000 chunks ...

# Stop (Ctrl+C)
# Latest checkpoint: graph_data/graph_checkpoint_1000.pkl
```

### Transfer:
```bash
# Copy to Mac Mini (via iCloud, network, etc.)
# graph_data/graph_checkpoint_1000.pkl
# OR entire graph_data/ directory
```

### On Mac Mini:
```bash
# Resume
python retry_failed_chunks.py

# Script will:
# 1. Load graph_checkpoint_1000.pkl (or knowledge_graph_full.pkl)
# 2. See 1000 chunks already processed
# 3. Continue with remaining 6,808 chunks
```

---

## Important Notes

### 1. **Checkpoint Frequency**
- Default: Every 10 chunks
- Can be changed in code: `batch_size=10`
- More frequent = more checkpoints = safer

### 2. **Latest Checkpoint**
- Checkpoints are numbered: `graph_checkpoint_10.pkl`, `graph_checkpoint_20.pkl`, etc.
- Use the **highest number** = most recent progress

### 3. **iCloud Sync**
- If your project is in iCloud Drive, files sync automatically
- Wait for sync to complete before resuming on Mac Mini
- Check: `ls -l graph_data/` to verify files are synced

### 4. **Path Differences**
- MacBook and Mac Mini might have different paths
- Script uses relative paths, so should work fine
- If issues, use absolute paths

---

## Verification

### Before transferring, verify on MacBook:
```bash
# Check latest checkpoint
ls -lt graph_data/graph_checkpoint_*.pkl | head -1

# Verify it's complete
python3 -c "
import pickle
from pathlib import Path
checkpoints = sorted(Path('graph_data').glob('graph_checkpoint_*.pkl'))
if checkpoints:
    latest = checkpoints[-1]
    with open(latest, 'rb') as f:
        data = pickle.load(f)
    print(f'Latest checkpoint: {latest.name}')
    print(f'  Nodes: {data[\"graph\"].number_of_nodes()}')
    print(f'  Edges: {data[\"graph\"].number_of_edges()}')
    print(f'  Chunks processed: {data[\"stats\"].get(\"chunks_processed\", 0)}')
    if 'processed_chunks' in data:
        print(f'  Processed chunks tracked: {len(data[\"processed_chunks\"])}')
"
```

### After transferring, verify on Mac Mini:
```bash
# Same verification script
# Should show same numbers
```

---

## Troubleshooting

### Issue: "Graph file not found"
**Solution:** Make sure you copied the checkpoint or graph file

### Issue: "All chunks appear new"
**Solution:** The checkpoint might not have `processed_chunks`. The script will still work, just processes all chunks (which is safe - merges duplicates).

### Issue: "Different chunk count"
**Solution:** Different machines might have slightly different file counts. This is normal. The script handles it.

---

## Summary

✅ **Yes, processed chunks are saved!**
- Checkpoints every 10 chunks
- `processed_chunks` set tracks what's done
- Can resume on different machine
- All entities/relationships preserved

**Just transfer the `graph_data/` directory and resume!**


