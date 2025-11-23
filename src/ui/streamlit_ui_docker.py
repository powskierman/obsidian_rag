#!/usr/bin/env python3
"""
Enhanced Streamlit UI for Obsidian RAG - Docker Version
Integrates ChromaDB vector search (Ollama) + Claude Haiku knowledge graph
"""

import streamlit as st
import requests
from datetime import datetime
import json
import os
import sys

# Ensure we can import from local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from deep_thinking.orchestrator import DeepThinkingRAG

# Service URLs (configurable via environment)
EMBEDDING_SERVICE = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
CLAUDE_GRAPH_SERVICE = os.getenv("CLAUDE_GRAPH_SERVICE_URL", "http://graph-service:8002")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
GPT_OSS_HOST = os.getenv("GPT_OSS_HOST", "http://host.docker.internal:12434/engines/llama.cpp")
USE_GPT_OSS = os.getenv("USE_GPT_OSS", "false").lower() == "true"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Detect GPT-OSS endpoint
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

# Detect GPT-OSS endpoint
def is_gpt_oss_endpoint(host: str) -> bool:
    """Check if host is GPT-OSS endpoint"""
    return "/engines/llama.cpp" in host or "/v1" in host or ":12434" in host

# Determine which LLM service to use
if USE_GPT_OSS or is_gpt_oss_endpoint(OLLAMA_HOST):
    LLM_HOST = GPT_OSS_HOST if USE_GPT_OSS else OLLAMA_HOST
    LLM_PROVIDER = "GPT-OSS"
else:
    LLM_HOST = OLLAMA_HOST
    LLM_PROVIDER = "Ollama"

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
    
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    
    # Search Mode Selection
    st.subheader("🔍 Search Mode")
    search_mode = st.radio(
        "Choose search method:",
        ["vector", "graph-claude", "hybrid", "Deep Thinking (Agentic)"],
        index=3,
        help="""
        - **vector**: Fast semantic search with Ollama (ChromaDB) 🔍
        - **graph-claude**: Claude Haiku-powered knowledge graph 🧠
        - **hybrid**: Best of both - graph-guided vector search 🔗
        - **deep thinking**: Agentic multi-step reasoning 🕵️‍♂️
        """
    )
    st.session_state.search_mode = search_mode
    
    st.markdown("---")
    
    # LLM Provider Selection
    st.subheader("🤖 LLM Provider")
    llm_options = ["Ollama (Free)", "Claude API ($)"]
    llm_choice = st.radio(
        "Choose LLM:",
        llm_options,
        index=0 if LLM_PROVIDER == "ollama" else 1,
        help="""
        - **Ollama**: Free, local models (llama3.2:3b)
        - **Claude API**: High quality, paid ($0.02/query)
        """
    )
    selected_provider = "ollama" if llm_choice == llm_options[0] else "claude"
    
    # Show API key status for Claude
    if selected_provider == "claude":
        if ANTHROPIC_API_KEY:
            # Validate the key (cache result in session state to avoid repeated API calls)
            validation_key = f"claude_key_validated_{ANTHROPIC_API_KEY[:20]}"
            if validation_key not in st.session_state:
                # Validate the key
                try:
                    from anthropic import Anthropic
                    client = Anthropic(api_key=ANTHROPIC_API_KEY)
                    # Quick validation call
                    test_response = client.messages.create(
                        model="claude-haiku-4-5",
                        max_tokens=1,
                        messages=[{"role": "user", "content": "Hi"}]
                    )
                    st.session_state[validation_key] = True
                    st.success("✅ Claude API key configured and validated")
                except Exception as e:
                    error_msg = str(e)
                    st.session_state[validation_key] = False
                    if "401" in error_msg or "authentication" in error_msg.lower():
                        st.error("❌ Claude API key is INVALID (401 error)")
                        st.warning("💡 Your API key may be expired or revoked. Please:")
                        st.info("1. Get a new key from: https://console.anthropic.com/\n2. Update `.env` file: `ANTHROPIC_API_KEY=sk-ant-...`\n3. Restart container: `docker-compose restart streamlit-ui`")
                    else:
                        st.warning(f"⚠️ Could not validate API key: {error_msg[:100]}")
            else:
                # Use cached validation result
                if st.session_state[validation_key]:
                    st.success("✅ Claude API key configured and validated")
                else:
                    st.error("❌ Claude API key is INVALID")
                    st.info("💡 Update `.env` and restart: `docker-compose restart streamlit-ui`")
        else:
            st.error("❌ Set ANTHROPIC_API_KEY in .env file or docker-compose.yml")
            st.info("💡 Create a `.env` file in the project root with:\n```\nANTHROPIC_API_KEY=your-key-here\n```")
    
    st.session_state.llm_provider = selected_provider
    
    st.markdown("---")
    
    # Service Status
    st.subheader("📊 Services")
    
    # Check embedding service
    try:
        stats = requests.get(f'{EMBEDDING_SERVICE}/stats', timeout=2).json()
        st.success(f"✅ Vector DB: {stats.get('total_documents', 0):,} chunks")
    except:
        st.error("⚠️ Vector service offline")
    
    # Check Claude Graph service
    try:
        claude_graph_response = requests.get(f'{CLAUDE_GRAPH_SERVICE}/health', timeout=2)
        if claude_graph_response.status_code == 200:
            claude_graph_data = claude_graph_response.json()
            if claude_graph_data.get('graph_loaded'):
                nodes = claude_graph_data.get('nodes', 0)
                edges = claude_graph_data.get('edges', 0)
                st.success(f"✅ Claude Graph: {nodes:,} entities, {edges:,} relationships")
            else:
                st.warning("⚠️ Claude Graph: Not loaded (build graph first)")
        else:
            st.warning("⚠️ Claude Graph: Service unavailable")
    except:
        st.warning("⚠️ Claude Graph: Offline")
    
    # Check LLM service (Ollama or GPT-OSS) and get available models
    available_models = []
    try:
        if LLM_PROVIDER == "GPT-OSS":
            # Check GPT-OSS
            gpt_oss_response = requests.get(f'{LLM_HOST}/v1/models', timeout=2)
            if gpt_oss_response.status_code == 200:
                models_data = gpt_oss_response.json().get('data', [])
                available_models = [m.get('id', m.get('name', 'unknown')) for m in models_data]
                st.success(f"✅ GPT-OSS: {len(available_models)} models")
            else:
                st.warning("⚠️ GPT-OSS unavailable")
                available_models = ["ai/gpt-oss:latest"]  # Fallback
        else:
            # Check Ollama and get model list
            ollama_response = requests.get(f'{OLLAMA_HOST}/api/tags', timeout=2)
            if ollama_response.status_code == 200:
                models_data = ollama_response.json().get('models', [])
                available_models = [m.get('name', 'unknown') for m in models_data]
                if available_models:
                    st.success(f"✅ Ollama: {len(available_models)} models available")
                else:
                    st.warning("⚠️ No Ollama models found")
                    available_models = ["llama3.2:3b"]  # Fallback
            else:
                st.warning("⚠️ Ollama unavailable")
                available_models = ["qwen2.5-coder:14b", "deepseek-r1:14b", "llama3.2:3b"]  # Fallback
    except Exception as e:
        st.error(f"⚠️ {LLM_PROVIDER} offline: {str(e)[:50]}")
        # Fallback models
        if LLM_PROVIDER == "GPT-OSS":
            available_models = ["ai/gpt-oss:latest"]
        else:
            available_models = ["qwen2.5-coder:14b", "deepseek-r1:14b", "llama3.2:3b"]
    
    st.markdown("---")
    
    # Model selection
    st.subheader("⚙️ Settings")
    
    if available_models:
        model_option = st.selectbox(
            "Model",
            available_models,
            help=f"Choose from {len(available_models)} available models"
        )
    else:
        model_option = st.selectbox(
            "Model",
            ["No models available"],
            help="No models found. Please check your Ollama/GPT-OSS connection."
        )
    
    num_sources = st.slider("Sources", 1, 20, 5)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1)
    show_sources = st.checkbox("Show Sources", value=True)
    
    st.markdown("---")
    
    # Actions
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Export Answer"):
            # Find last assistant message
            last_answer = next((m for m in reversed(st.session_state.messages) if m["role"] == "assistant"), None)
            
            if last_answer:
                export_data = {
                    "timestamp": datetime.now().isoformat(),
                    "model": model_option,
                    "search_mode": search_mode,
                    "content": last_answer["content"],
                    "sources": last_answer.get("sources", [])
                }
                
                # Convert to Markdown
                md_content = f"# RAG Answer Export\n\n"
                md_content += f"**Date:** {export_data['timestamp']}\n"
                md_content += f"**Model:** {export_data['model']}\n"
                md_content += f"**Mode:** {export_data['search_mode']}\n\n"
                md_content += "---\n\n"
                
                md_content += f"{export_data['content']}\n\n"
                
                if export_data['sources']:
                    md_content += "### 📚 Sources\n"
                    for source in export_data['sources']:
                        md_content += f"- **{source.get('filename', 'Unknown')}**"
                        if 'relevance' in source:
                            md_content += f" ({source['relevance']:.0f}%)"
                        md_content += "\n"
                    md_content += "\n"
                
                st.download_button(
                    "Download Markdown",
                    data=md_content,
                    file_name=f"rag_answer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                    mime="text/markdown"
                )
            else:
                st.warning("No answer to export")
    
    with col2:
        pass

# Main chat interface
st.title("💬 Chat with Your Knowledge Base")

# Display search mode indicator
mode_emoji = {
    'vector': '🔍',
    'graph-claude': '🧠',
    'hybrid': '🔗'
}
st.caption(f"{mode_emoji.get(search_mode, '🔍')} Using: **{search_mode}** search")

# Display chat history
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message["role"] == "assistant" and "sources" in message and show_sources:
            with st.expander("📚 Sources", expanded=True):
                if not message["sources"]:
                    st.info("No sources available")
                else:
                    for i, source in enumerate(message["sources"], 1):
                        if "filename" in source:
                            relevance = source.get("relevance", 0)
                            st.write(f"**{i}. {source['filename']}** - {relevance:.0f}% relevant")
                            st.caption(f"📁 {source.get('filepath', '')}")
                            # Show snippet if available
                            if "snippet" in source:
                                with st.container():
                                    st.text(source["snippet"][:200] + "..." if len(source.get("snippet", "")) > 200 else source.get("snippet", ""))
                            st.divider()

    # Phase 1: Rating buttons for assistant messages (OUTSIDE chat_message context)
    if message["role"] == "assistant":
        st.caption("Rate this response:")
        rating_emojis = ["😞", "😕", "😐", "😊", "😍"]
        rating_labels = ["Poor", "Fair", "OK", "Good", "Excellent"]

        # Centered compact layout
        cols = st.columns([2, 1, 1, 1, 1, 1, 2])
        for i, (emoji, label) in enumerate(zip(rating_emojis, rating_labels)):
            with cols[i + 1]:
                if st.button(emoji, key=f"rate_{idx}_{i+1}", help=label, use_container_width=True):
                    st.toast(f"✅ Rated: {label}")

# Chat input
if prompt := st.chat_input("Ask about your notes..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Use selected search mode
    search_mode = st.session_state.search_mode

    # Generate response
    with st.chat_message("assistant"):
        try:
            sources_list = []
            context_text = ""

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
                        if dist < 0:
                            relevance = abs(dist) * 100
                        else:
                            # Improved relevance: 1/(1+d) decay so 1.0 distance = 50% instead of 0%
                            relevance = (1 / (1 + dist)) * 100
                        relevance = min(100, max(0, relevance))
                        filename = meta.get('filename', 'unknown')
                        filepath = meta.get('filepath', 'unknown')
                        
                        # Extract snippet (first 200 chars) for display
                        snippet = doc[:200] + "..." if len(doc) > 200 else doc
                        
                        context_parts.append(f"Source {i} - {filename} ({relevance:.0f}% relevant):\n{doc}")
                        sources_list.append({
                            "filename": filename,
                            "filepath": filepath,
                            "relevance": relevance,
                            "snippet": snippet
                        })
                    
                    context_text = "\n\n---\n\n".join(context_parts)
            
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
                            # We'll just let it fall through or copy vector logic? 
                            # For simplicity, let's just error out or maybe better to copy vector logic.
                            # Actually, let's just duplicate the vector logic here for fallback or better yet, 
                            # refactor vector logic into a function? 
                            # Given the constraints, I'll just implement a simple fallback message and stop for now, 
                            # or better, just run the vector search without graph context.
                            
                            # Fallback: Standard vector search
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
                            if vault_response.status_code == 200:
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
                                context_text = "\n\n---\n\n".join(context_parts)
                            else:
                                st.error("Vector search failed")
                                st.stop()

                    except Exception as e:
                        st.warning(f"Hybrid search error: {e}, falling back to vector")
                        # Fallback: Standard vector search
                        query_params = {
                            "query": prompt,
                            "n_results": num_sources,
                            "reranking": True,
                            "deduplicate": True
                        }
                        try:
                            vault_response = requests.post(
                                f'{EMBEDDING_SERVICE}/query',
                                json=query_params,
                                timeout=30
                            )
                            if vault_response.status_code == 200:
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
                                context_text = "\n\n---\n\n".join(context_parts)
                            else:
                                st.error("Vector search failed")
                                st.stop()
                        except:
                            st.error("Vector search failed")
                            st.stop()

            elif search_mode == 'graph-claude':
                # Use Claude-powered knowledge graph
                with st.spinner("🧠 Querying Claude knowledge graph..."):
                    try:
                        graph_response = requests.post(
                            f'{CLAUDE_GRAPH_SERVICE}/query',
                            json={
                                "query": prompt,
                                "max_entities": 20
                            },
                            timeout=30
                        )
                        
                        if graph_response.status_code != 200:
                            if graph_response.status_code == 503:
                                st.error("❌ Claude Graph not loaded. Build graph first using build_knowledge_graph.py")
                            else:
                                st.error(f"Graph query failed: {graph_response.status_code}")
                            st.stop()
                        
                        graph_result = graph_response.json()
                        
                        # Check for errors in the response
                        if 'error' in graph_result:
                            error_msg = graph_result.get('error', 'Unknown error')
                            st.error(f"❌ Graph service error: {error_msg}")
                            if 'credit balance' in str(error_msg).lower():
                                st.info("💡 This error is from the graph service's Claude API call. Check your Anthropic account credits.")
                            st.stop()
                        
                        context_text = graph_result.get('answer', '')
                        
                        if not context_text:
                            st.warning("No answer from knowledge graph")
                            st.stop()
                        
                        # For Claude graph, the answer is already synthesized
                        # We can use it directly or combine with vector search
                        sources_list = [{
                            "filename": "Knowledge Graph",
                            "filepath": "Claude Graph",
                            "relevance": 100
                        }]
                        
                    except requests.exceptions.ConnectionError:
                        st.error("❌ Cannot connect to Claude Graph service. Is it running?")
                        st.info("💡 Start it with: docker-compose up graph-service")
                        st.stop()
                    except Exception as e:
                        st.error(f"Graph query error: {e}")
                        st.stop()

            elif search_mode == 'Deep Thinking (Agentic)':
                # Deep Thinking Mode
                if not ANTHROPIC_API_KEY:
                    st.error("❌ Claude API key required for Deep Thinking mode")
                    st.stop()
                
                from anthropic import Anthropic
                client = Anthropic(api_key=ANTHROPIC_API_KEY)
                
                # Initialize Orchestrator
                orchestrator = DeepThinkingRAG(
                    anthropic_client=client,
                    vector_service_url=EMBEDDING_SERVICE,
                    graph_service_url=CLAUDE_GRAPH_SERVICE
                )
                
                # Create a container for progress updates
                progress_container = st.container()
                status_text = progress_container.empty()
                details_expander = progress_container.expander("🧠 Research Process", expanded=True)
                
                # Callback for UI updates
                def ui_status_callback(msg, details=None):
                    status_text.markdown(f"**{msg}**")
                    if details:
                        # If it's a plan, show it nicely
                        if "plan" in details:
                            with details_expander:
                                st.markdown("### 📋 Research Plan")
                                for step in details["plan"]:
                                    st.markdown(f"- **Step {step['step_number']}**: {step['sub_question']} ({step['search_strategy']})")
                                st.divider()
                    
                    # If it's a step update (heuristic based on msg content)
                    if msg.startswith("👣 Step"):
                        with details_expander:
                            st.markdown(f"**{msg}**")
                    elif msg.startswith("   Found"):
                        with details_expander:
                            st.caption(msg)
                    elif msg.startswith("   Insight"):
                        with details_expander:
                            st.info(msg)
                            st.divider()
                    elif msg.startswith("⚖️ Policy"):
                        with details_expander:
                            st.markdown(f"_{msg}_")

                try:
                    result = orchestrator.query(
                        question=prompt,
                        max_iterations=7,
                        status_callback=ui_status_callback
                    )
                    
                    # Clear progress container content but keep expander closed/open as user left it? 
                    # Actually, let's just clear the status text
                    status_text.empty()
                    
                    # Set context_text to the final answer so it falls through to display
                    # But wait, Deep Thinking returns the FINAL answer, not context for an LLM.
                    # We need to handle this differently than the other modes which prepare context.
                    
                    response_text = result["answer"]
                    
                    # Display confidence
                    conf_score = result.get("confidence_score", 0.0)
                    conf_just = result.get("confidence_justification", "")
                    
                    if conf_score > 0:
                        color = "green" if conf_score >= 0.8 else "orange" if conf_score >= 0.5 else "red"
                        st.markdown(f"### 🎯 Confidence: :{color}[{conf_score*100:.0f}%]")
                        st.caption(f"_{conf_just}_")
                        st.divider()
                    
                    # Prepare sources list
                    for citation in result["citations"]:
                        # Clean Obsidian links
                        clean_citation = citation.replace("[[", "").replace("]]", "")
                        sources_list.append({
                            "filename": clean_citation,
                            "filepath": "Deep Thinking Citation",
                            "relevance": 100,
                            "type": "Agent"
                        })
                        
                    # Add retrieved docs to sources if not already there (optional, might be too many)
                    # For now, let's just stick to the citations generated by the agent
                    
                    # We need to bypass the standard LLM generation block below
                    # A simple way is to set a flag or structure the code to skip
                    
                except Exception as e:
                    st.error(f"Deep Thinking error: {e}")
                    import traceback
                    st.code(traceback.format_exc())
                    st.stop()
            
            
            if search_mode != 'Deep Thinking (Agentic)' and (not context_text or context_text.strip() == ""):
                st.warning("No relevant information found")
                st.stop()
            
            # For Claude graph and Deep Thinking, the answer is already synthesized
            if search_mode == 'graph-claude':
                # Claude graph already provides a complete answer from Claude
                response_text = context_text
            elif search_mode == 'Deep Thinking (Agentic)':
                # Already generated above
                pass
            else:
                # For other modes, use LLM to generate response
                with st.spinner(f"💭 Thinking with {model_option} ({LLM_PROVIDER})..."):
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
- If the context doesn't contain relevant information, say so clearly

Answer:"""

                    # Get selected LLM provider from session state
                    active_provider = st.session_state.get('llm_provider', 'ollama')
                    
                    if active_provider == "claude":
                        # Use Claude API
                        if not ANTHROPIC_API_KEY:
                            st.error("❌ Claude API key not configured")
                            st.stop()
                        
                        try:
                            from anthropic import Anthropic
                            client = Anthropic(api_key=ANTHROPIC_API_KEY)
                            
                            # Extract just the question from system_prompt
                            claude_response = client.messages.create(
                                model="claude-haiku-4-5",
                                max_tokens=4000,
                                temperature=temperature,
                                system=f"You are an AI assistant helping Michel understand his Obsidian knowledge base.\n\nContext from notes:\n{context_text}",
                                messages=[
                                    {"role": "user", "content": prompt}
                                ]
                            )
                            
                            response_text = claude_response.content[0].text
                        except Exception as e:
                            st.error(f"Claude API error: {e}")
                            st.stop()
                    
                    elif LLM_PROVIDER == "GPT-OSS" or active_provider == "gpt-oss":
                        # Use OpenAI-compatible API
                        llm_response = requests.post(
                            f'{LLM_HOST}/v1/chat/completions',
                            json={
                                'model': model_option,
                                'messages': [
                                    {'role': 'system', 'content': system_prompt}
                                ],
                                'max_tokens': 4096,
                                'temperature': temperature
                            },
                            timeout=180
                        )
                        
                        if llm_response.status_code != 200:
                            st.error(f"GPT-OSS API error: {llm_response.status_code}")
                            st.code(llm_response.text)
                            st.stop()
                        
                        result = llm_response.json()
                        if 'choices' in result and len(result['choices']) > 0:
                            response_text = result['choices'][0]['message']['content']
                        else:
                            st.error("Unexpected GPT-OSS response format")
                            st.code(json.dumps(result, indent=2))
                            st.stop()
                    else:
                        # Use Ollama API
                        ollama_response = requests.post(
                            f'{OLLAMA_HOST}/api/generate',
                            json={
                                'model': model_option,
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

    # Phase 1: Rating buttons for the CURRENT response (OUTSIDE chat_message context)
    if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "assistant":
        st.caption("Rate this response:")
        rating_emojis = ["😞", "😕", "😐", "😊", "😍"]
        rating_labels = ["Poor", "Fair", "OK", "Good", "Excellent"]

        # Use unique key based on current message count
        msg_idx = len(st.session_state.messages) - 1

        # Centered compact layout
        cols = st.columns([2, 1, 1, 1, 1, 1, 2])
        for i, (emoji, label) in enumerate(zip(rating_emojis, rating_labels)):
            with cols[i + 1]:
                if st.button(emoji, key=f"rate_current_{msg_idx}_{i+1}", help=label, use_container_width=True):
                    st.toast(f"✅ Rated: {label}")

# Footer
st.markdown("---")
st.caption("💡 Choose between fast vector search or intelligent graph reasoning. All data stays local.")



