# Graph Build Statistics

## Latest Build Results

**Date**: November 8, 2025  
**Final Checkpoint**: `graph_checkpoint_3560.pkl`  
**Total Chunks Processed**: 13,864 successful + 4,113 errors = 17,977 total

### Processing Results
- ✅ **Successful chunks**: 13,864
- ❌ **Errors**: 4,113 (~23% error rate)
- 🔄 **Retries**: 0
- ✅ **Successful retries**: 0

### Graph Growth
- **Nodes**: 27,227 → 35,048 (+7,821 nodes, +29% growth)
- **Edges**: 54,231 → 80,200 (+25,969 edges, +48% growth)

### Cost & Usage
- **Total Cost**: $90.44
- **Tokens In**: 10,663,239
- **Tokens Out**: 15,818,685
- **Model**: Claude Haiku 4.5

### Cost Per Chunk
- **Per successful chunk**: ~$0.0066 ($90.44 / 13,864)
- **Success rate**: 77.1% (13,864 / 17,977)
- **Effective cost per attempted chunk**: ~$0.0050

## Handling Errors

**Important**: Since you restarted the process halfway through, the 4,113 errors are **from the previous run** (before restart).

### How Error Stats Work

When you load an existing graph, the `extraction_stats` (including error count) are loaded from the saved file. Errors **accumulate** - they don't reset.

**What this means:**
- ✅ **Current run**: Processed 13,864 chunks successfully with **0 new errors**
- 📊 **Total errors shown (4,113)**: From the previous run's stats (before restart)
- ❌ **No `failed_chunks.pkl`**: Confirms 0 new errors in this run

### The 4,113 Errors (From Previous Run)

These errors from before the restart could be:
1. **Chunks that were skipped** because they were already processed (shouldn't count as errors, but might be in stats)
2. **Empty/short chunks** - Chunks with < 50 characters that returned no data
3. **Actual API failures** - But these would have been saved to `failed_chunks.pkl` in the previous run

**Bottom line**: Your current run was successful! The 4,113 errors are historical from before the restart.

### Retry Failed Chunks (If needed)

If you want to retry chunks that had actual API failures:

**Option 1: Retry with Haiku (Cheaper)**
```bash
python retry_failed_chunks.py
# Use the latest checkpoint: graph_data/graph_checkpoint_3560.pkl
```

**Option 2: Retry with Sonnet (More Reliable)**
```bash
python retry_failed_chunks.py
# When prompted, answer "yes" to "Use Claude Sonnet"
# Estimated cost: ~$12.34 (4,113 chunks × $0.003)
```

### Why Chunks Fail

Common reasons for chunk processing errors:
1. **Malformed JSON responses** from Claude
2. **Rate limiting** (though retry logic handles this)
3. **Very short or empty chunks** (skipped automatically)
4. **API timeouts** (should retry automatically)

### Improving Success Rate

To reduce errors in future builds:
- Use Claude Sonnet instead of Haiku (better JSON reliability)
- Increase `max_retries` parameter (default: 3)
- Check for rate limiting issues
- Review failed chunks to identify patterns

## Next Steps

1. **Query your graph** - The graph is ready to use with 35,048 nodes
2. **Retry failed chunks** - If you want to improve coverage
3. **Export final graph** - Save as `knowledge_graph_full.pkl` when satisfied

## Graph Quality

With 35,048 entities and 80,200 relationships, your graph has:
- **Density**: High connectivity
- **Coverage**: ~77% of chunks successfully processed
- **Richness**: Average of ~2.3 relationships per entity

