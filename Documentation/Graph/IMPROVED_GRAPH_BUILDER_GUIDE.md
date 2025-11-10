# Improved Graph Builder - Guide

## Overview

The improved graph builder (`claude_graph_builder_improved.py`) provides:

✅ **Better Error Handling**
- Multiple JSON parsing strategies
- Automatic retry logic (up to 3 attempts per chunk)
- Exponential backoff on retries

✅ **Maintains Existing Data**
- Loads your existing graph
- Only processes chunks that failed or weren't processed
- Merges new data with existing graph

✅ **Tracks Failed Chunks**
- Saves failed chunks to `graph_data/failed_chunks.pkl`
- Can retry them later with better settings (e.g., using Sonnet)

✅ **Better Reliability**
- Option to use Claude Sonnet for more reliable JSON (more expensive)
- Improved JSON parsing with 6 different recovery strategies
- Better handling of malformed responses

## Quick Start: Retry Failed Chunks

### Option 1: Retry with Haiku (Cheaper)

```bash
python retry_failed_chunks.py
```

This will:
1. Load your existing `graph_data/knowledge_graph_full.pkl`
2. Find chunks that weren't successfully processed
3. Retry them with improved error handling
4. Merge results back into your graph

**Cost:** ~$0.0014 per chunk (Haiku)

### Option 2: Retry with Sonnet (More Reliable)

```bash
python retry_failed_chunks.py
# When prompted, answer "yes" to "Use Claude Sonnet"
```

**Cost:** ~$0.003 per chunk (Sonnet) - but much better success rate

### Option 3: Retry Only Previously Failed Chunks

If you have `graph_data/failed_chunks.pkl` from a previous run:

```python
from claude_graph_builder_improved import ImprovedClaudeGraphBuilder
import os

builder = ImprovedClaudeGraphBuilder(
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
    model="claude-sonnet-4-5-20250929",  # Use Sonnet for better results
    max_retries=3
)

# Load existing graph
builder.load_graph("graph_data/knowledge_graph_full.pkl")

# Retry failed chunks
builder.retry_failed_chunks(
    failed_chunks_file="graph_data/failed_chunks.pkl",
    use_sonnet=True  # Use Sonnet for retries
)

# Save updated graph
builder.save_graph("graph_data/knowledge_graph_full.pkl")
```

## What Gets Improved

### Current Status
- **6,058 chunks processed**
- **4,113 errors (67.9% error rate)**
- **1,945 successful chunks**
- **23,926 entities, 35,030 relationships**

### After Retry (Expected)
- **More chunks successfully processed**
- **Lower error rate (target: <30%)**
- **More entities and relationships**
- **Better coverage of your knowledge base**

## Error Recovery Strategies

The improved builder uses 6 strategies to recover from JSON errors:

1. **Direct JSON parse** - Try parsing as-is
2. **Remove markdown** - Strip ```json code blocks
3. **Extract JSON object** - Find `{...}` in text
4. **Fix common issues** - Fix trailing commas, unclosed strings
5. **Extract partial data** - Salvage entities/relationships separately
6. **Salvage partial JSON** - Extract largest valid JSON object

## Cost Estimates

### Retry All Failed Chunks (4,113 chunks)

**With Haiku:**
- Cost: ~$5.76
- Success rate: ~60-70% (estimated)
- Remaining failures: ~1,200-1,600 chunks

**With Sonnet:**
- Cost: ~$12.34
- Success rate: ~85-95% (estimated)
- Remaining failures: ~200-600 chunks

### Recommendation

1. **First pass:** Retry with Haiku (cheaper, still good improvement)
2. **Second pass:** Retry remaining failures with Sonnet (if needed)

## Usage Examples

### Example 1: Retry Failed Chunks from Existing Graph

```bash
# Make sure ANTHROPIC_API_KEY is set
export ANTHROPIC_API_KEY=your-key-here

# Run retry script
python retry_failed_chunks.py

# Follow prompts:
# - ChromaDB path: (press Enter for default)
# - Vault path: (press Enter for default)
# - Graph file: (press Enter for default)
# - Use Sonnet: no (for first pass, yes for second pass)
```

### Example 2: Use Improved Builder for New Builds

```python
from claude_graph_builder_improved import ImprovedClaudeGraphBuilder
from build_knowledge_graph import get_chunks_from_filesystem
import os

# Initialize with Sonnet for better reliability
builder = ImprovedClaudeGraphBuilder(
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
    model="claude-sonnet-4-5-20250929",  # More reliable
    max_retries=3
)

# Get chunks
chunks = get_chunks_from_filesystem(
    chroma_db_path="/path/to/chroma_db",
    test_mode=False
)

# Build graph with improved error handling
builder.build_graph_from_chunks(chunks, batch_size=10)

# Save
builder.save_graph("graph_data/knowledge_graph_full_improved.pkl")
```

## Monitoring Progress

The improved builder provides detailed progress:

```
Processing chunk 1/100... ✅ (5 entities, 3 relationships)
Processing chunk 2/100... ⚠️  Attempt 1/3 failed: JSON error
   Retrying in 1s...
Processing chunk 2/100... ✅ (4 entities, 2 relationships)
...
✅ Processing complete!
   Successful: 95
   Errors: 5
   Retries: 3
   Successful retries: 2
```

## Files Created

- `graph_data/knowledge_graph_full.pkl` - Updated graph (overwrites existing)
- `graph_data/knowledge_graph_full.json` - JSON export
- `graph_data/failed_chunks.pkl` - Chunks that still failed (can retry later)
- `graph_data/graph_checkpoint_*.pkl` - Progress checkpoints

## Next Steps

1. **Run retry script** to improve your graph
2. **Check results** - see how many chunks were successfully retried
3. **If needed, retry again** with Sonnet for remaining failures
4. **Use the improved graph** - it should have better coverage

## Troubleshooting

### "No chunks found"
- Make sure ChromaDB path or vault path is correct
- Check that paths exist

### "Graph file not found"
- Make sure `graph_data/knowledge_graph_full.pkl` exists
- Or provide the correct path when prompted

### Still high error rate
- Try using Sonnet instead of Haiku
- Check your API key has sufficient credits
- Some chunks may be genuinely problematic (very short, malformed, etc.)

## Benefits

✅ **Maintains your existing 23,926 entities and 35,030 relationships**  
✅ **Adds more entities from previously failed chunks**  
✅ **Better error recovery means fewer failures**  
✅ **Can retry multiple times with different settings**  
✅ **Tracks what's been processed to avoid duplicates**


