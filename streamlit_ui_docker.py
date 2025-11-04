#!/usr/bin/env python3
"""
Enhanced Streamlit UI for Obsidian RAG - Docker Version
Integrates ChromaDB vector search + LightRAG knowledge graphs
"""

import streamlit as st
import requests
from datetime import datetime
import json
import os

# Service URLs (configurable via environment)
EMBEDDING_SERVICE = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
LIGHTRAG_SERVICE = os.getenv("LIGHTRAG_SERVICE_URL", "http://localhost:8001")
GRAPHRAG_SERVICE = os.getenv("GRAPHRAG_SERVICE_URL", "http://localhost:8003")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")

st.set_page_config(
    page_title="Obsidian RAG",
    page_icon="🧠",
    layout="wide"
)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'search_mode' not in st.session_state:
    st.session_state.search_mode = 'vector'

# Sidebar configuration
with st.sidebar:
    st.title("🧠 Obsidian RAG")
    st.markdown("Hybrid AI-powered knowledge retrieval")
    
    st.markdown("---")
    
    # Search Mode Selection
    st.subheader("🔍 Search Mode")
    search_mode = st.radio(
        "Choose search method:",
        ["vector", "graph-naive", "graph-local", "graph-global", "graph-hybrid", "graphrag-local", "graphrag-global"],
        index=0,
        help="""
        - **vector**: Fast semantic search (ChromaDB)
        - **graph-naive**: Simple graph traversal (LightRAG)
        - **graph-local**: Local entity exploration (LightRAG)
        - **graph-global**: Global knowledge synthesis (LightRAG)
        - **graph-hybrid**: Best of both worlds (LightRAG)
        - **graphrag-local**: Entity-focused search (GraphRAG-Local-Ollama)
        - **graphrag-global**: Community-based search (GraphRAG-Local-Ollama)
        """
    )
    st.session_state.search_mode = search_mode

    st.markdown("---")

    # Model Selection
    st.subheader("🤖 Model Selection")

    # Get available models from Ollama
    @st.cache_data(ttl=60)  # Cache for 1 minute
    def get_available_models():
        try:
            response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                return [model['name'] for model in models]
        except:
            pass
        return ['llama3.1:8b', 'qwen2.5-coder:14b', 'nomic-embed-text']  # fallback

    available_models = get_available_models()

    # Filter models (exclude embedding models for LLM selection)
    llm_models = [m for m in available_models if 'embed' not in m.lower()]
    embed_models = [m for m in available_models if 'embed' in m.lower()]

    # LLM Model Selection
    default_llm = 'llama3.1:8b' if 'llama3.1:8b' in llm_models else llm_models[0] if llm_models else 'llama3.1:8b'
    selected_llm = st.selectbox(
        "💬 Language Model:",
        llm_models,
        index=llm_models.index(default_llm) if default_llm in llm_models else 0,
        help="Choose the LLM for text generation and reasoning"
    )

    # Embedding Model Selection
    default_embed = 'nomic-embed-text:latest' if 'nomic-embed-text:latest' in embed_models else embed_models[0] if embed_models else 'nomic-embed-text'
    selected_embed = st.selectbox(
        "🔤 Embedding Model:",
        embed_models + ['nomic-embed-text'],  # Add fallback
        index=embed_models.index(default_embed) if default_embed in embed_models else 0,
        help="Choose the embedding model for vector search"
    )

    # Store in session state
    st.session_state.selected_llm = selected_llm
    st.session_state.selected_embed = selected_embed

    # Model info
    with st.expander("ℹ️ Model Info"):
        st.text(f"LLM: {selected_llm}")
        st.text(f"Embeddings: {selected_embed}")
        st.text(f"Available: {len(available_models)} models")

    st.markdown("---")

    # Service Status
    st.subheader("📊 Services")
    
    # Check embedding service
    try:
        stats = requests.get(f'{EMBEDDING_SERVICE}/stats', timeout=2).json()
        st.success(f"✅ Vector DB: {stats.get('total_documents', 0):,} chunks")
    except:
        st.error("⚠️ Vector service offline")
    
    # Check LightRAG service
    try:
        lightrag_stats = requests.get(f'{LIGHTRAG_SERVICE}/stats', timeout=2).json()
        if lightrag_stats.get('database_exists'):
            st.success("✅ Knowledge Graph: Active")
        else:
            st.warning("⚠️ Graph not indexed")
            if st.button("🔄 Index Vault for Graph", key="lightrag_index"):
                with st.spinner("Building knowledge graph..."):
                    response = requests.post(f'{LIGHTRAG_SERVICE}/index-vault', json={})
                    if response.status_code == 200:
                        st.success("✅ Graph indexed!")
                        st.rerun()
    except:
        st.error("⚠️ Graph service offline")

    # Check GraphRAG service
    try:
        graphrag_stats = requests.get(f'{GRAPHRAG_SERVICE}/stats', timeout=2).json()
        artifacts = graphrag_stats.get('indexed_artifacts', 0)
        if artifacts > 0:
            st.success(f"✅ GraphRAG-Local: {artifacts} artifacts")
        else:
            st.warning("⚠️ GraphRAG not indexed")
            if st.button("🔄 Index Vault for GraphRAG", key="graphrag_index"):
                with st.spinner("Building GraphRAG knowledge graph..."):
                    response = requests.post(f'{GRAPHRAG_SERVICE}/build-index', json={})
                    if response.status_code == 200:
                        st.success("✅ GraphRAG indexed!")
                        st.rerun()
    except:
        st.error("⚠️ GraphRAG service offline")
    
    # Check Ollama
    try:
        ollama_response = requests.get(f'{OLLAMA_HOST}/api/tags', timeout=2)
        if ollama_response.status_code == 200:
            models = ollama_response.json().get('models', [])
            st.success(f"✅ Ollama: {len(models)} models")
        else:
            st.warning("⚠️ Ollama unavailable")
    except:
        st.error("⚠️ Ollama offline")
    
    st.markdown("---")
    
    # Settings
    st.subheader("⚙️ Settings")
    
    num_sources = st.slider("Sources", 1, 20, 5)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1)
    show_sources = st.checkbox("Show Sources", value=True)
    
    st.markdown("---")
    
    # Actions
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Export"):
            if st.session_state.messages:
                export_data = {
                    "timestamp": datetime.now().isoformat(),
                    "model": st.session_state.get('selected_llm', 'llama3.1:8b'),
                    "search_mode": search_mode,
                    "messages": st.session_state.messages
                }
                st.download_button(
                    "Download JSON",
                    data=json.dumps(export_data, indent=2),
                    file_name=f"rag_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
    
    with col2:
        if st.button("🗑️ Clear"):
            st.session_state.messages = []
            st.rerun()

# Main chat interface
st.title("💬 Chat with Your Knowledge Base")

# Display search mode indicator
mode_emoji = {
    'vector': '🔍',
    'graph-naive': '🌐',
    'graph-local': '📍',
    'graph-global': '🌍',
    'graph-hybrid': '⚡',
    'graphrag-local': '🧠',
    'graphrag-global': '🌌'
}
st.caption(f"{mode_emoji.get(search_mode, '🔍')} Using: **{search_mode}** search")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        if message["role"] == "assistant" and "sources" in message and show_sources:
            with st.expander("📚 Sources", expanded=False):
                for source in message["sources"]:
                    if "filename" in source:
                        relevance = source.get("relevance", 0)
                        st.write(f"**{source['filename']}** - {relevance:.0f}% relevant")
                        st.caption(source.get('filepath', ''))

# Chat input
if prompt := st.chat_input("Ask about your notes..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Generate response
    with st.chat_message("assistant"):
        try:
            sources_list = []
            
            # Step 1: Retrieve context based on search mode
            if search_mode == 'vector':
                # Use vector search (ChromaDB)
                with st.spinner("🔍 Searching vector database..."):
                    query_params = {
                        "query": prompt,
                        "n_results": num_sources,
                        "reranking": True,
                        "deduplicate": True
                    }
                    
                    vault_response = requests.post(
                        f'{EMBEDDING_SERVICE}/query',
                        json=query_params,
                        timeout=30
                    )
                    
                    if vault_response.status_code != 200:
                        st.error("Vector search failed")
                        st.stop()
                    
                    results = vault_response.json()
                    documents = results.get('documents', [[]])[0]
                    metadatas = results.get('metadatas', [[]])[0]
                    distances = results.get('distances', [[]])[0]
                    
                    # Check if we actually have documents
                    if not documents or len(documents) == 0:
                        st.warning("No matching documents found in your vault")
                        st.stop()
                    
                    context_parts = []
                    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                        # Handle negative distances (higher is better)
                        relevance = abs(dist) * 100 if dist < 0 else (1 - dist) * 100
                        relevance = min(100, max(0, relevance))  # Clamp between 0-100
                        filename = meta.get('filename', 'unknown')
                        filepath = meta.get('filepath', 'unknown')
                        
                        context_parts.append(f"Source {i} - {filename} ({relevance:.0f}% relevant):\n{doc}")
                        sources_list.append({
                            "filename": filename,
                            "filepath": filepath,
                            "relevance": relevance
                        })
                    
                    context_text = "\n\n---\n\n".join(context_parts)
            
            elif search_mode.startswith('graphrag-'):
                # Use GraphRAG-Local-Ollama search
                graphrag_mode = 'local' if search_mode == 'graphrag-local' else 'global'
                progress_text = f"🧠 Querying GraphRAG ({graphrag_mode} mode)..."
                if graphrag_mode == 'global':
                    progress_text += " This may take several minutes for community-based analysis."

                with st.spinner(progress_text):
                    try:
                        graphrag_response = requests.post(
                            f'{GRAPHRAG_SERVICE}/query',
                            json={
                                "query": prompt,
                                "mode": graphrag_mode
                            },
                            timeout=300  # Increased timeout for GraphRAG processing
                        )

                        if graphrag_response.status_code != 200:
                            st.error("GraphRAG query failed")
                            st.stop()

                        graphrag_result = graphrag_response.json()
                        context_text = graphrag_result.get('result', '')
                        sources_list = [{"filename": "GraphRAG Knowledge Graph", "filepath": "GraphRAG-Local-Ollama", "relevance": 100}]

                    except requests.exceptions.Timeout:
                        st.error("⏱️ GraphRAG query timed out. Try using 'graphrag-local' mode for faster results, or simplify your query.")
                        st.stop()
                    except requests.exceptions.RequestException as e:
                        st.error(f"GraphRAG query failed: {str(e)}")
                        st.stop()

            else:
                # Use LightRAG graph search
                graph_mode = search_mode.replace('graph-', '')
                progress_text = f"🌐 Querying knowledge graph ({graph_mode} mode)..."
                if graph_mode in ['global', 'hybrid']:
                    progress_text += " This may take several minutes for complex analysis."

                with st.spinner(progress_text):
                    try:
                        graph_response = requests.post(
                            f'{LIGHTRAG_SERVICE}/query',
                            json={
                                "query": prompt,
                                "mode": graph_mode
                            },
                            timeout=300  # Increased to 5 minutes for graph processing
                        )

                        if graph_response.status_code != 200:
                            st.error("Graph query failed")
                            st.stop()

                        graph_result = graph_response.json()
                        context_text = graph_result.get('result', '')
                        sources_list = [{"filename": "Knowledge Graph", "filepath": "LightRAG", "relevance": 100}]

                    except requests.exceptions.Timeout:
                        st.error("⏱️ Graph query timed out. Try using 'graph-local' mode for faster results, or simplify your query.")
                        st.stop()
                    except requests.exceptions.RequestException as e:
                        st.error(f"Graph query failed: {str(e)}")
                        st.stop()
            
            if not context_text or context_text.strip() == "":
                st.warning("No relevant information found")
                st.stop()
            
            # Step 2: Generate response with LLM
            selected_model = st.session_state.get('selected_llm', 'llama3.1:8b')
            with st.spinner(f"💭 Thinking with {selected_model}..."):
                system_prompt = f"""You are an AI assistant helping Michel understand his Obsidian knowledge base.

Context from notes:
{context_text}

User question: {prompt}

Provide a thorough, accurate answer that:
- References specific information from the context
- Is medically accurate when discussing health topics
- Includes technical details when relevant
- Is supportive and encouraging
- Cites which sources you used

Answer:"""

                ollama_response = requests.post(
                    f'{OLLAMA_HOST}/api/generate',
                    json={
                        'model': selected_model,
                        'prompt': system_prompt,
                        'stream': False,
                        'options': {
                            'temperature': temperature,
                            'num_ctx': 65536
                        }
                    },
                    timeout=180
                )
                
                if ollama_response.status_code != 200:
                    st.error("Failed to generate response")
                    st.stop()
                
                response_text = ollama_response.json().get('response', '')
            
            # Display response
            st.markdown(response_text)
            
            # Show sources
            if show_sources and sources_list:
                with st.expander("📚 Sources Used", expanded=False):
                    for source in sources_list:
                        st.write(f"**{source['filename']}** - {source['relevance']:.0f}% relevant")
                        if 'filepath' in source:
                            st.caption(source['filepath'])
            
            # Save to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_text,
                "sources": sources_list,
                "search_mode": search_mode
            })
        
        except requests.exceptions.Timeout:
            st.error("⏱️ Request timed out")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            import traceback
            with st.expander("🐛 Debug"):
                st.code(traceback.format_exc())

# Footer
st.markdown("---")
st.caption("💡 Choose between fast vector search or intelligent graph reasoning. All data stays local.")



