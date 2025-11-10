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

# Service URLs (configurable via environment)
EMBEDDING_SERVICE = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
CLAUDE_GRAPH_SERVICE = os.getenv("CLAUDE_GRAPH_SERVICE_URL", "http://graph-service:8002")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
GPT_OSS_HOST = os.getenv("GPT_OSS_HOST", "http://host.docker.internal:12434/engines/llama.cpp")
USE_GPT_OSS = os.getenv("USE_GPT_OSS", "false").lower() == "true"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

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
    
    st.markdown("---")
    
    # Search Mode Selection
    st.subheader("🔍 Search Mode")
    search_mode = st.radio(
        "Choose search method:",
        ["vector", "graph-claude"],
        index=0,
        help="""
        - **vector**: Fast semantic search with Ollama (ChromaDB) 🔍
        - **graph-claude**: Claude Haiku-powered knowledge graph 🧠
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
            st.success("✅ Claude API key configured")
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
    
    # Check LLM service (Ollama or GPT-OSS)
    try:
        if LLM_PROVIDER == "GPT-OSS":
            # Check GPT-OSS
            gpt_oss_response = requests.get(f'{LLM_HOST}/v1/models', timeout=2)
            if gpt_oss_response.status_code == 200:
                models = gpt_oss_response.json().get('data', [])
                st.success(f"✅ GPT-OSS: {len(models)} models")
            else:
                st.warning("⚠️ GPT-OSS unavailable")
        else:
            # Check Ollama
            ollama_response = requests.get(f'{OLLAMA_HOST}/api/tags', timeout=2)
            if ollama_response.status_code == 200:
                models = ollama_response.json().get('models', [])
                st.success(f"✅ Ollama: {len(models)} models")
            else:
                st.warning("⚠️ Ollama unavailable")
    except:
        st.error(f"⚠️ {LLM_PROVIDER} offline")
    
    st.markdown("---")
    
    # Model selection
    st.subheader("⚙️ Settings")
    
    if LLM_PROVIDER == "GPT-OSS":
        # GPT-OSS models
        model_option = st.selectbox(
            "Model",
            ["ai/gpt-oss:latest"],
            help="GPT-OSS model for generating responses"
        )
    else:
        # Ollama models
        model_option = st.selectbox(
            "Model",
            ["qwen2.5-coder:14b", "deepseek-r1:14b", "llama3.2:3b"],
            help="LLM for generating responses"
        )
    
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
                    "model": model_option,
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
    'graph-claude': '🧠'
}
st.caption(f"{mode_emoji.get(search_mode, '🔍')} Using: **{search_mode}** search")

# Display chat history
for message in st.session_state.messages:
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
            
            
            if not context_text or context_text.strip() == "":
                st.warning("No relevant information found")
                st.stop()
            
            # Step 2: Generate response with LLM
            # For Claude graph, the answer is already synthesized, so we can display it directly
            if search_mode == 'graph-claude':
                # Claude graph already provides a complete answer from Claude
                response_text = context_text
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
                                model="claude-3-5-sonnet-20241022",
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

# Footer
st.markdown("---")
st.caption("💡 Choose between fast vector search or intelligent graph reasoning. All data stays local.")



