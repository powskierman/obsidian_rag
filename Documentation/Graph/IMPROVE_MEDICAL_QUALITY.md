# Improving Medical/Lymphoma Graph Quality

## Current Situation

**Good News:**
- ✅ 117 medical/lymphoma-related entities found in graph
- ✅ CAR-T Therapy: 54 connections
- ✅ Cancer: 35 connections

**Problem:**
- ⚠️ Quality is "lacking" - minimal lymphoma information
- ⚠️ 67.9% error rate means many medical chunks failed
- ⚠️ Chunk boundaries may have split important medical information

---

## Why Quality Might Be Better with Vault Files

### ChromaDB Chunking (Previous):
- **Method**: `smart_chunk_document()` with 200-char overlap
- **Size**: Max 1000 chars per chunk
- **Strategy**: Sentence-aware, tries to preserve context
- **Problem**: 
  - Many chunks failed (67.9% error rate)
  - Medical information might have been split awkwardly
  - Some files might not have been indexed properly

### Vault File Chunking (Current):
- **Method**: Simple paragraph-based chunking
- **Size**: Max 1000 chars per chunk
- **Strategy**: Splits on `\n\n` (paragraph breaks)
- **Advantages**:
  - ✅ Processes ALL files (not just what was in ChromaDB)
  - ✅ Better error handling (retry logic)
  - ✅ Can use Sonnet for better extraction
  - ✅ Different boundaries might capture complete medical concepts

### Key Differences:

| Aspect | ChromaDB Chunks | Vault File Chunks |
|--------|----------------|-------------------|
| **Overlap** | 200 chars | None |
| **Boundaries** | Sentence-aware | Paragraph-based |
| **Coverage** | Only indexed files | All vault files |
| **Error Handling** | Failed silently | Retry logic |
| **Medical Focus** | No prioritization | Can prioritize |

---

## Why Quality Should Improve

### 1. **Better Error Recovery**
- Improved builder has retry logic (3 attempts)
- Better JSON parsing (6 recovery strategies)
- Can use Sonnet for medical content (more reliable)

### 2. **Complete File Coverage**
- Vault files include ALL your medical notes
- ChromaDB might have missed some files
- Different chunk boundaries capture complete concepts

### 3. **Medical-Specific Improvements**
- Can prioritize medical files
- Can use better models for medical content
- Can adjust chunking for medical documents

---

## Recommendations for Better Medical Quality

### Option 1: Use Sonnet for Medical Files (Recommended)

Sonnet is more reliable and better at extracting medical entities:

```python
# In retry script, use Sonnet for better quality
python retry_failed_chunks.py
# Answer "yes" to "Use Claude Sonnet"
```

**Cost**: ~$12 for all chunks, but much better success rate (~85-95% vs 32%)

### Option 2: Prioritize Medical Files

Create a script that processes medical files first with better settings:

```python
# Process medical files with Sonnet
# Then process other files with Haiku
```

### Option 3: Improve Chunking for Medical Content

Medical documents often have:
- Structured sections (Results, Treatment, etc.)
- Important details that shouldn't be split
- Temporal information (scan dates, progression)

Better chunking strategy:
- Preserve complete sections
- Keep related information together
- Don't split mid-sentence for medical data

---

## Expected Improvements

### Current Graph:
- 117 medical entities
- Many failed chunks (67.9% error rate)
- Incomplete coverage

### After Improved Processing:
- **More medical entities** (from previously failed chunks)
- **Better relationships** (complete context preserved)
- **More detailed information** (Sonnet extracts better)
- **Temporal relationships** (scan progression, treatment timeline)

---

## Action Plan

### Immediate (Current Run):
1. ✅ Let current run complete (processing all chunks)
2. ✅ Improved error handling should catch more medical info
3. ✅ Different chunk boundaries may capture complete concepts

### Next Steps (If Quality Still Lacking):

1. **Retry with Sonnet**:
   ```bash
   python retry_failed_chunks.py
   # Use Sonnet for better quality
   ```

2. **Focus on Medical Files**:
   - Process medical directory first
   - Use Sonnet for medical content
   - Use Haiku for other content

3. **Improve Chunking**:
   - Create medical-aware chunking
   - Preserve complete sections
   - Better handling of structured medical data

---

## Testing Quality

After processing, test with queries like:
- "What are my PET scan results?"
- "How has my lymphoma treatment progressed?"
- "What treatments have I received?"
- "What are the relationships between my scans?"

Compare results to see if quality improved!


