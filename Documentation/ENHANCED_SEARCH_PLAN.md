# Enhanced Search Sections Implementation Plan

## Goal
Add three clearly labeled sections to search results:
1. **📚 Vault Knowledge** - Information from RAG/vector search
2. **🧠 LLM Knowledge** - General knowledge from the LLM's training data  
3. **🌐 Web Search** - Real-time web search (Gemini & Claude only)

---

## Current State
- Single response combining vault context with LLM generation
- No separate sections for different information sources
- No web search capability

---

## Proposed Implementation

### Section 1: Vault Knowledge (Use Existing RAG)
```python
# Already working - retrieve from vault, generate with context
vault_answer = llm_generate(prompt, context=vault_docs)
```

### Section 2: LLM General Knowledge
```python
# Second call WITHOUT vault context
general_knowledge = llm_generate(
    f"Based solely on your training data, answer: {prompt}"
)
```

### Section 3: Web Search
- **Gemini**: Use grounding with Google Search
- **Claude**: Integrate with Tavily or similar search API
- **Ollama**: Show "⚠️ Web search not available with Ollama"

---

## Questions Before Implementation

### 1. Web Search - How was this previously done?
- Was it using Tavily API?
- Google Custom Search?
- SearXNG?
- Gemini's built-in grounding?
- Something else?

### 2. LLM Knowledge Section - What should it contain?
- **Option A**: Pure general knowledge (no vault context at all)
- **Option B**: Supplemental information to vault answer
- **Option C**: Alternative perspective on the same question

### 3. Performance Considerations
Making 3 separate API calls will be slower:
- Vault + LLM answer: ~2-5 seconds
- General knowledge: ~2-5 seconds  
- Web search: ~2-5 seconds
- **Total**: ~6-15 seconds per query

Is this acceptable, or should some sections be:
- Optional (toggle on/off)?
- Cached?
- Parallel processed?

---

## Technical Approach

### Response Structure
```markdown
## 📚 Vault Knowledge
[Answer based on your Obsidian notes]

**Sources:**
- note1.md
- note2.md

---

## 🧠 LLM Knowledge
[General knowledge from LLM training]

---

## 🌐 Web Search
[Real-time results from web]
*Note: Only available with Gemini Pro and Claude Sonnet*
```

### Code Changes Needed
**File**: `src/ui/streamlit_ui_docker.py`

1. Restructure response generation into 3 sections
2. Add second LLM call for general knowledge
3. Implement web search integration
4. Format output with clear section headers

---

## Next Steps
1. Get answers to questions above
2. Implement changes on `enhanced-search-sections` branch
3. Test with all 3 pr oviders
4. Review and merge

---

## Please Answer
1. How was web search previously implemented?
2. What should LLM Knowledge section show?
3. Is 3x slower acceptable or need optimization?
