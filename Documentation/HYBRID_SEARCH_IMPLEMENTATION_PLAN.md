# Hybrid Search Mode Implementation Plan

## Problem Statement

Currently, the Obsidian RAG system has two separate search modes:
- **Vector Search**: Returns detailed document content but lacks relationship context
- **Graph Search**: Shows entity relationships but missing actual document content

**User observation**: Vector search provides much more detailed and relevant results because it retrieves full text chunks, while graph search only returns entity/relationship summaries.

## Goal

Implement a **hybrid search mode** that combines the strengths of both approaches:
1. Use graph search to identify relevant entities and relationships
2. Extract key entities from graph results
3. Enhance vector search query with these entities
4. Return rich document content guided by graph relationships

## User Review Required

> [!IMPORTANT]
> **Search Mode Addition**
> 
> This will add a third search mode option: `hybrid`. The existing `vector` and `graph-claude` modes will remain unchanged.

> [!NOTE]
> **Performance Consideration**
> 
> Hybrid mode will make TWO API calls (graph + vector) so queries will take slightly longer than individual modes. Estimated: 2-5 seconds total.

## Proposed Changes

### 1. Streamlit UI Updates

#### [MODIFY] [streamlit_ui_docker.py](file:///Volumes/Users/Michel/Library/Mobile%20Documents/com~apple~CloudDocs/ai/RAG/obsidian_rag/streamlit_ui_docker.py)

**Changes to make:**

1. **Add hybrid mode to search options** (lines 55-62)
   ```python
   search_mode = st.radio(
       "Choose search method:",
       ["vector", "graph-claude", "hybrid"],  # Add hybrid
       index=0,
       help="""
       - **vector**: Fast semantic search (ChromaDB) 🔍
       - **graph-claude**: Knowledge graph relationships 🧠
       - **hybrid**: Best of both - graph-guided vector search 🔗
       """
   )
   ```

2. **Add hybrid emoji to mode indicators** (lines 235-238)
   ```python
   mode_emoji = {
       'vector': '🔍',
       'graph-claude': '🧠',
       'hybrid': '🔗'  # Add hybrid emoji
   }
   ```

3. **Implement hybrid search logic** (after line 327, before line 328)
   ```python
   elif search_mode == 'hybrid':
       # Hybrid: Graph-guided vector search
       with st.spinner("🔗 Performing hybrid search..."):
           # Step 1: Query graph for entities
           try:
               graph_response = requests.post(
                   f'{CLAUDE_GRAPH_SERVICE}/query',
                   json={"query": prompt, "max_entities": 20},
                   timeout=30
               )
               
               if graph_response.status_code == 200:
                   graph_result = graph_response.json()
                   graph_context = graph_result.get('answer', '')
                   
                   # Step 2: Extract entities from graph response
                   entities = extract_entities_from_graph(graph_context)
                   
                   # Step 3: Enhanced vector search with entities
                   enhanced_query = f"{prompt} {' '.join(entities)}"
                   
                   query_params = {
                       "query": enhanced_query,
                       "n_results": num_sources,
                       "reranking": True,
                       "deduplicate": True
                   }
                   
                   vault_response = requests.post(
                       f'{EMBEDDING_SERVICE}/query',
                       json=query_params,
                       timeout=30
                   )
                   
                   # Process vector results (same as vector mode)
                   results = vault_response.json()
                   documents = results.get('documents', [[]])[0]
                   metadatas = results.get('metadatas', [[]])[0]
                   distances = results.get('distances', [[]])[0]
                   
                   context_parts = []
                   for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                       relevance = abs(dist) * 100 if dist < 0 else (1 - dist) * 100
                       relevance = min(100, max(0, relevance))
                       filename = meta.get('filename', 'unknown')
                       filepath = meta.get('filepath', 'unknown')
                       snippet = doc[:200] + "..." if len(doc) > 200 else doc
                       
                       context_parts.append(f"Source {i} - {filename} ({relevance:.0f}% relevant):\n{doc}")
                       sources_list.append({
                           "filename": filename,
                           "filepath": filepath,
                           "relevance": relevance,
                           "snippet": snippet
                       })
                   
                   # Add graph context as additional source
                   context_parts.insert(0, f"Graph Context:\n{graph_context}")
                   sources_list.insert(0, {
                       "filename": "Knowledge Graph",
                       "filepath": "Graph Relationships",
                       "relevance": 100
                   })
                   
                   context_text = "\n\n---\n\n".join(context_parts)
               else:
                   # Fallback to vector-only if graph fails
                   st.warning("Graph unavailable, using vector search only")
                   # ... (same as vector search)
           except Exception as e:
               st.warning(f"Hybrid search error: {e}, falling back to vector")
               # ... (same as vector search)
   ```

4. **Add entity extraction helper function** (after line 22, before main code)
   ```python
   def extract_entities_from_graph(graph_text: str) -> list:
       """Extract key entities from graph response text."""
       import re
       
       # Extract capitalized phrases (likely entities)
       entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', graph_text)
       
       # Common words to filter out
       stopwords = {'The', 'This', 'That', 'These', 'Those', 'There', 'Here', 
                    'When', 'Where', 'What', 'How', 'Why', 'Based', 'Your'}
       
       # Filter and deduplicate
       entities = [e for e in entities if e not in stopwords]
       entities = list(set(entities))[:10]  # Top 10 unique entities
       
       return entities
   ```

---

## Verification Plan

### Automated Tests

**No existing automated tests found** for the Streamlit UI. The UI is primarily tested manually through user interaction.

### Manual Verification

#### Test 1: Hybrid Mode Selection
1. Start Docker services: `./Scripts/docker_start.sh`
2. Open Streamlit UI: http://localhost:8501
3. In sidebar, verify "Search Mode" shows three options:
   - vector
   - graph-claude  
   - **hybrid** (new)
4. Select "hybrid" mode
5. Verify mode indicator shows: "🔗 Using: **hybrid** search"

**Expected**: Hybrid option appears and can be selected

#### Test 2: Hybrid Search Functionality
1. With hybrid mode selected
2. Enter query: "Tell me about my lymphoma journey"
3. Observe spinner: "🔗 Performing hybrid search..."
4. Wait for response (2-5 seconds)
5. Verify response includes:
   - Detailed document content (like vector search)
   - Entity relationships (from graph)
6. Check "📚 Sources Used" expander
7. Verify first source is "Knowledge Graph" 
8. Verify remaining sources are document chunks with filenames

**Expected**: Response combines graph context with detailed document content

#### Test 3: Hybrid vs Individual Modes Comparison
1. Ask same question in all three modes:
   - Vector: "Tell me about my lymphoma journey"
   - Graph: "Tell me about my lymphoma journey"  
   - Hybrid: "Tell me about my lymphoma journey"
2. Compare responses:
   - Vector: Detailed content, no relationship context
   - Graph: Relationships only, sparse details
   - Hybrid: Both detailed content AND relationships

**Expected**: Hybrid provides richer response than either mode alone

#### Test 4: Hybrid Fallback Behavior
1. Stop graph service: `docker-compose stop graph-service`
2. Select hybrid mode
3. Enter any query
4. Verify warning appears: "Graph unavailable, using vector search only"
5. Verify search still works (falls back to vector)
6. Restart graph: `docker-compose start graph-service`

**Expected**: Graceful degradation when graph service unavailable

#### Test 5: Entity Extraction Quality
1. Use hybrid mode with medical query: "What are my PET scan results?"
2. Check if entities like "PET Scan", "DLBCL", "SUV" are extracted
3. Verify vector search returns relevant documents about these entities

**Expected**: Entity extraction identifies key medical terms and improves vector retrieval

---

## Implementation Steps

1. ✅ Add `extract_entities_from_graph()` helper function
2. ✅ Update search mode radio button to include "hybrid"
3. ✅ Add hybrid emoji to mode indicators
4. ✅ Implement hybrid search logic block
5. ✅ Test all three modes with lymphoma query
6. ✅ Verify fallback behavior
7. ✅ Document usage in UI

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Slower queries (2 API calls) | Show clear progress spinner, set reasonable timeouts |
| Graph service down | Fallback to vector-only search with warning |
| Poor entity extraction | Use regex + stopword filtering, limit to top 10 |
| Duplicate information | Deduplicate vector results, clearly label graph context |

---

## Future Enhancements (Not in This PR)

- Cache graph results for common queries
- Smarter entity extraction using NER
- Weighted combination of graph + vector scores
- User-configurable hybrid parameters

---

**Ready for implementation**: All changes are localized to `streamlit_ui_docker.py`. No database migrations or service changes needed.
