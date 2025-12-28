# Knowledge Graph Quality Guide

**Last Updated**: December 28, 2025

This guide consolidates all recommendations for improving knowledge graph quality across medical, technical, and general knowledge domains.

---

## Overview

Your knowledge graph quality depends on three key factors:
1. **Entity extraction success rate** - How many chunks successfully extract entities
2. **Chunking strategy** - How text is split (preserves context vs splits concepts)
3. **Model quality** - Which LLM is used for extraction (Haiku vs Sonnet)

---

## Medical/Health Content Quality

### Current Status (Example Metrics)

**Typical Medical Graph**:
- 117 medical/lymphoma-related entities
- CAR-T Therapy: 54 connections
- Cancer: 35 connections
- **Challenge**: May miss detailed medical context

### Why Medical Content Quality Matters

Medical documents often contain:
- **Structured sections** (Results, Treatment, Discussion)
- **Critical details** that shouldn't be split (scan measurements, dosages)
- **Temporal information** (scan dates, treatment progression)
- **Relationships** between symptoms, treatments, and outcomes

### Improving Medical Quality

#### Option 1: Use Claude Sonnet for Medical Files (Recommended)

Sonnet is more reliable at extracting medical entities:

```bash
# During graph building, use Sonnet for better quality
python build_knowledge_graph.py
# Select Sonnet model when prompted

# Or retry failed chunks with Sonnet
python retry_failed_chunks.py
# Answer "yes" to "Use Claude Sonnet"
```

**Benefits**:
- Better entity extraction (~85-95% vs ~65% success rate)
- More accurate medical relationships
- Better understanding of temporal progression

**Cost**: Higher (~$12 vs $1.50 for full vault), but much better medical context

#### Option 2: Prioritize Medical Files

Process medical files first with better settings:

1. Identify medical directories
2. Process with Sonnet first
3. Process other content with Haiku

**Benefits**:
- Ensures medical content gets best model
- Reduces cost (only medical files use Sonnet)

#### Option 3: Improve Chunking for Medical Content

**Current Chunking**:
- 1000 characters max per chunk
- 200 character overlap
- Smart boundaries (paragraphs, headers, sentences)

**Medical-Specific Improvements**:
- Preserve complete sections (Results, Treatment)
- Keep related information together (scan + interpretation)
- Don't split mid-sentence for medical data
- Preserve temporal sequences (1st scan → 2nd scan → 3rd scan)

### Testing Medical Quality

After processing, test with queries:
- "What are my PET scan results?"
- "How has my lymphoma treatment progressed?"
- "What treatments have I received?"
- "What are the relationships between my scans?"

Compare results to assess quality improvement.

---

## General Graph Quality Improvements

### Understanding Error Rates

**High Error Rate (>50%)**:
- Many chunks failed to extract entities
- Likely cause: Model timeout, API errors, or poor chunk boundaries
- Solution: Retry with better error handling, use Sonnet

**Medium Error Rate (20-50%)**:
- Some chunks failed
- Likely cause: Ambiguous text, code snippets, fragments
- Solution: Retry failed chunks, acceptable for mixed content

**Low Error Rate (<20%)**:
- Most chunks succeeded
- Good quality extraction
- Solution: No action needed

### Chunking Strategy Comparison

| Aspect | Simple Chunking | Smart Chunking (Current) |
|--------|----------------|--------------------------|
| **Boundaries** | Paragraph breaks only | Headers, paragraphs, sentences |
| **Overlap** | None | 200 characters |
| **Context Preservation** | Poor | Good |
| **Medical Suitability** | Poor | Good |
| **Technical Suitability** | Acceptable | Excellent |

**Current System Uses**: Smart chunking with 200-char overlap

### Vault Files vs ChromaDB Chunks

#### ChromaDB-based Building:
- **Method**: Pre-indexed chunks from vector database
- **Coverage**: Only files indexed in ChromaDB
- **Error Handling**: Failed chunks are lost
- **Success Rate**: Variable (depends on initial indexing)

#### Vault File-based Building (Current):
- **Method**: Direct file processing with smart chunking
- **Coverage**: ALL vault markdown files
- **Error Handling**: Retry logic (3 attempts per chunk)
- **Success Rate**: Higher (better error recovery)
- **Advantages**:
  - ✅ Processes all files (not just indexed)
  - ✅ Better error handling with retries
  - ✅ Can use different models for different content
  - ✅ Smart chunking with overlap

---

## Missing Data Troubleshooting

### Issue: Medical/Technical Data Not in Graph

**Why This Happens**:
1. Graph was built from subset of chunks
2. Specific files may not have been processed
3. Entity extraction failed for those chunks
4. Chunk boundaries split important concepts

### Solutions

#### Option 1: Use Vector Search (Immediate)

The data **IS** in ChromaDB vector database:

1. Switch to **"vector"** search mode
2. Ask your question
3. Vector search will find the relevant files

**Why this works**: Vector search uses semantic similarity, doesn't depend on entity extraction.

#### Option 2: Resume Graph Building

Add missing chunks to existing graph:

```bash
python build_knowledge_graph.py
# Choose option: Resume building
# Processes chunks that weren't included before
```

**Note**: Costs additional API credits, but adds missing entities.

#### Option 3: Hybrid Approach (Best)

1. Use **"vector"** search to find relevant notes
2. Use **"graph"** search to understand relationships
3. Use **"hybrid"** mode to combine both strengths

#### Option 4: Rebuild with Content Focus

If specific content is critical:

1. Identify files containing that content
2. Ensure those files are prioritized during building
3. Consider using Sonnet for those files

---

## Model Selection for Quality

### Claude Haiku 3.5
- **Speed**: Fast
- **Cost**: Low (~$1.50 for 1600 notes)
- **Success Rate**: ~65%
- **Best for**: General content, technical docs, large vaults
- **Quality**: Good for most content

### Claude Sonnet 3.5
- **Speed**: Medium
- **Cost**: Higher (~$12 for 1600 notes)
- **Success Rate**: ~85-95%
- **Best for**: Medical content, complex relationships, critical data
- **Quality**: Excellent, more accurate entity extraction

### Recommendation

**Hybrid Approach**:
1. Use **Haiku** for general content (cost-effective)
2. Use **Sonnet** for medical/critical files (quality)
3. Best balance of cost and quality

---

## Improving Existing Graphs

### If Quality Is Lacking

**Step 1: Identify Issues**
- Test queries to see what's missing
- Check error rate from build logs
- Identify specific content gaps

**Step 2: Retry Failed Chunks**

```bash
python retry_failed_chunks.py
# Choose Sonnet for better quality
```

This processes chunks that failed during initial build.

**Step 3: Process Specific Content**

If specific files/topics are missing:
1. Identify those files
2. Extract chunks from those files
3. Process with Sonnet
4. Merge into existing graph

**Step 4: Rebuild if Necessary**

For major quality issues:

```bash
# Backup current graph
cp graph_data/knowledge_graph_full.pkl graph_data/knowledge_graph_backup.pkl

# Rebuild with better settings
rm graph_data/knowledge_graph_full.pkl
python build_knowledge_graph.py
# Use Sonnet for better quality
```

---

## Quality Metrics

### Good Quality Graph

- **Entity count**: 5,000+ entities for 1,600 notes
- **Relationship count**: 10,000+ edges
- **Error rate**: <20%
- **Query success**: Finds relevant information consistently
- **Temporal relationships**: Can trace progression over time

### Poor Quality Graph

- **Entity count**: Low (<2,000 for 1,600 notes)
- **Relationship count**: Low (<3,000 edges)
- **Error rate**: >50%
- **Query success**: Missing obvious information
- **Temporal relationships**: Fragmented, incomplete

### Measuring Quality

**Test Queries**:
1. Ask about recent events → Should find recent notes
2. Ask about relationships → Should trace connections
3. Ask about progression → Should show timeline
4. Ask about specific topics → Should find all relevant content

**Good Results**:
- ✅ Finds all relevant entities
- ✅ Shows meaningful relationships
- ✅ Includes temporal context
- ✅ Cites specific note names

**Poor Results**:
- ❌ Misses obvious information
- ❌ Generic responses
- ❌ No temporal context
- ❌ Vague answers

---

## Expected Improvements

### After Better Error Handling

**Before**:
- 67.9% error rate (many failures)
- Missing entities from failed chunks
- Incomplete relationships

**After** (with retry logic):
- <20% error rate
- More entities extracted
- Better relationship coverage

### After Better Chunking

**Before** (simple chunking):
- Split concepts mid-paragraph
- No overlap, lost context
- Medical information fragmented

**After** (smart chunking):
- Natural boundaries (headers, sentences)
- 200-char overlap preserves context
- Complete medical concepts kept together

### After Using Sonnet

**Before** (Haiku only):
- ~65% success rate
- Some medical nuances missed
- Acceptable for general content

**After** (Sonnet for medical):
- ~85-95% success rate for critical content
- Better medical entity extraction
- More accurate relationships

---

## Action Plan for Quality Improvement

### Immediate Steps

1. **Let current build complete** (if in progress)
2. **Check error rate** from logs
3. **Test with queries** to identify gaps

### If Error Rate >50%

1. **Retry failed chunks**:
   ```bash
   python retry_failed_chunks.py
   ```
2. **Use Sonnet** for better success rate
3. **Verify improvements** with test queries

### If Medical Quality Lacking

1. **Identify medical files**
2. **Retry with Sonnet**:
   ```bash
   python retry_failed_chunks.py
   # Select Sonnet model
   ```
3. **Test medical queries** to verify

### If Complete Rebuild Needed

1. **Backup existing graph**
2. **Use Sonnet for entire vault** (costly but highest quality)
3. **Or use hybrid**: Sonnet for medical, Haiku for other
4. **Verify with comprehensive test queries**

---

## Summary

### Key Factors for Quality

1. ✅ **Low error rate** (<20%) - More entities extracted
2. ✅ **Smart chunking** (overlap + natural boundaries) - Context preserved
3. ✅ **Appropriate model** (Sonnet for critical content) - Better extraction
4. ✅ **Complete coverage** (all vault files processed) - Nothing missed

### Best Practices

1. **Use smart chunking** with 200-char overlap
2. **Implement retry logic** for failed chunks
3. **Choose model by content type** (Haiku for general, Sonnet for medical)
4. **Test quality** with representative queries
5. **Iterate**: Retry failed chunks, improve as needed

### Expected Quality

With proper configuration:
- **Error rate**: <20%
- **Entity extraction**: 90%+ of important entities
- **Relationships**: Meaningful connections
- **Query success**: Finds relevant information consistently

---

## Related Documentation

- [IMPROVED_GRAPH_BUILDER_GUIDE.md](IMPROVED_GRAPH_BUILDER_GUIDE.md) - Graph building process
- [GRAPH_DATA_FLOW.md](GRAPH_DATA_FLOW.md) - System architecture
- [BUILD_STATISTICS.md](BUILD_STATISTICS.md) - Current graph statistics
- [TRANSFER_BETWEEN_MACHINES.md](TRANSFER_BETWEEN_MACHINES.md) - Moving graphs

---

**Last Updated**: December 28, 2025
**Version**: 1.0 (Consolidated from 3 previous guides)
