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
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
from pathlib import Path
try:
    from dotenv import load_dotenv
    env_file = Path('.env')
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

# Service URLs
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
CLAUDE_GRAPH_SERVICE_URL = os.getenv("CLAUDE_GRAPH_SERVICE_URL", "http://localhost:8002")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
GPT_OSS_HOST = os.getenv("GPT_OSS_HOST", "http://host.docker.internal:12434/engines/llama.cpp")
USE_GPT_OSS = os.getenv("USE_GPT_OSS", "false").lower() == "true"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Detect GPT-OSS endpoint
def is_gpt_oss_endpoint(host: str) -> bool:
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
        ["vector", "knowledge-graph", "hybrid"],
        index=2,
        help="""
        - **vector**: Fast semantic search with Ollama (ChromaDB) 🔍
        - **knowledge-graph**: Kimi/Gemini-powered knowledge graph 🧠
        - **hybrid**: Best of both - graph-guided vector search 🔗
        """
    )
    st.session_state.search_mode = search_mode
    
    st.markdown("---")
    
    # LLM Provider Selection
    st.subheader("🤖 LLM Provider")
    llm_options = ["Ollama (Free)", "Gemini Pro ($)", "Claude API ($)"]
    default_index = {"ollama": 0, "gemini": 1, "claude": 2}.get(LLM_PROVIDER, 0)
    llm_choice = st.radio(
        "Choose LLM:",
        llm_options,
        index=default_index,
        help="""
        - **Ollama**: Free, local models (llama3.2:3b)
        - **Gemini Pro**: Google's latest model, fast & high quality
        - **Claude API**: Anthropic's model, excellent reasoning
        """
    )
    if llm_choice == llm_options[0]:
        selected_provider = "ollama"
    elif llm_choice == llm_options[1]:
        selected_provider = "gemini"
    else:
        selected_provider = "claude"
    
    # Show API key status for Claude
    if selected_provider == "claude":
        if ANTHROPIC_API_KEY:
            st.success("✅ Claude API key configured")
        else:
            st.error("❌ Set ANTHROPIC_API_KEY in .env file")
    
    # Show API key status for Gemini
    elif selected_provider == "gemini":
        if GEMINI_API_KEY:
            st.success("✅ Gemini API key configured")
        else:
            st.error("❌ Set GEMINI_API_KEY in .env file")
    
    st.session_state.llm_provider = selected_provider
    
    st.markdown("---")
    
    # Service Status
    st.subheader("📊 Services")
    
    # Check embedding service
    try:
        stats = requests.get(f'{EMBEDDING_SERVICE_URL}/stats', timeout=2).json()
        st.success(f"✅ Vector DB: {stats.get('total_documents', 0):,} chunks")
    except:
        st.error("⚠️ Vector service offline")
    
    # Check Knowledge Graph service
    try:
        graph_response = requests.get(f'{CLAUDE_GRAPH_SERVICE_URL}/health', timeout=2)
        if graph_response.status_code == 200:
            graph_data = graph_response.json()
            if graph_data.get('graph_loaded'):
                nodes = graph_data.get('nodes', 0)
                edges = graph_data.get('edges', 0)
                st.success(f"✅ Knowledge Graph: {nodes:,} entities, {edges:,} relationships")
            else:
                st.warning("⚠️ Knowledge Graph: Not loaded (build graph first)")
        else:
            st.warning("⚠️ Knowledge Graph: Service unavailable")
    except:
        st.warning("⚠️ Knowledge Graph: Offline")
    
    st.markdown("---")
    
    # Settings
    st.subheader("⚙️ Settings")
    
    # Model selection (simplified for thin client - mainly for display or passed to backend if supported)
    # We'll just show a generic input or select box if we want custom models, but simpler is better.
    # We kept the logic to fetch models in the legacy code, but for thin client we can rely on backend defaults
    # or just let user type it if needed. For now, a text input or simple select is fine.
    model_option = st.text_input("Model Name (optional)", placeholder="Auto-select based on provider")

    num_sources = st.slider("Sources", 1, 50, 10)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1)
    show_sources = st.checkbox("Show Sources", value=True)
    enhanced_search = st.checkbox("Enhanced Search", value=False, 
                                   help="Add LLM Knowledge and Web Search sections (slower)")
    
    st.markdown("---")
    
    # Actions
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Export"):
            if st.session_state.messages:
                markdown_content = f"# RAG Chat Export\n\n**Date**: {datetime.now()}\n\n---\n\n"
                for msg in st.session_state.messages:
                    role = "👤 User" if msg["role"] == "user" else "🤖 Assistant"
                    markdown_content += f"## {role}\n\n{msg['content']}\n\n---\n\n"
                
                # In Docker, we can't easily save to user's host Downloads. giving a download button is better.
                st.download_button("Download MD", markdown_content, file_name="chat_export.md")
    
    with col2:
        if st.button("🗑️ Clear"):
            st.session_state.messages = []
            st.rerun()

# Main chat interface
st.title("💬 Chat with Your Knowledge Base")

# Display search mode indicator
mode_emoji = {'vector': '🔍', 'knowledge-graph': '🧠', 'hybrid': '🔗'}
st.caption(f"{mode_emoji.get(search_mode, '🔍')} Using: **{search_mode}** search")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and "sources" in message and show_sources and message["sources"]:
            with st.expander("📚 Sources"):
                for source in message["sources"]:
                    st.markdown(f"**{source.get('filename','?')}** ({int(source.get('relevance',0))}%)")
                    st.caption(source.get('snippet',''))

# Chat input
if prompt := st.chat_input("Ask about your notes..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response via Backend
    with st.chat_message("assistant"):
        active_provider = st.session_state.get('llm_provider', 'ollama')
        
        # Determine provider display name
        provider_display = {"ollama": "Ollama", "gemini": "Gemini Pro", "claude": "Claude Sonnet", "gpt-oss": "GPT-OSS"}.get(active_provider, "Ollama")
        
        # Backend mode mapping
        mode_map = {'vector': 'vector', 'knowledge-graph': 'graph', 'hybrid': 'hybrid'}
        query_mode = mode_map.get(st.session_state.search_mode, 'vector')
        
        with st.spinner(f"💭 Thinking with {provider_display} ({query_mode})..."):
            try:
                # Backend call
                payload = {
                    'query': prompt,
                    'mode': query_mode,
                    'llm_provider': active_provider,
                    'model': model_option if model_option else "",
                    'temperature': temperature,
                    'n_results': num_sources,
                    'llm_knowledge': enhanced_search,
                    'web_search': enhanced_search and active_provider in ["gemini", "claude"]
                }
                
                response = requests.post(
                    f"{CLAUDE_GRAPH_SERVICE_URL}/query",
                    json=payload,
                    timeout=180
                )
                
                if response.status_code != 200:
                    st.error(f"Backend error ({response.status_code}): {response.text}")
                    st.stop()
                    
                result = response.json()
                answer = result.get('answer', '')
                sources = result.get('sources', [])
                
                # Format final response
                final_output = f"{answer}"
                
                if enhanced_search:
                     if result.get('llm_knowledge'):
                        kb_text = result['llm_knowledge']
                        if isinstance(kb_text, dict): kb_text = kb_text.get('error', str(kb_text))
                        final_output += f"\n\n---\n\n### 🧠 LLM Knowledge\n\n{kb_text}"
                     
                     if result.get('web_search'):
                        web = result['web_search']
                        if 'results' in web and web['results']:
                             web_text = "\n".join([f"{i}. [{r['title']}]({r['url']})\n   {r['content'][:200]}..." for i,r in enumerate(web['results'],1)])
                             final_output += f"\n\n---\n\n### 🌐 Web Search\n\n**Terms**: _{web.get('search_terms','')}_\n\n{web_text}"
                        elif 'error' in web:
                             final_output += f"\n\n---\n\n### 🌐 Web Search\n\nError: {web['error']}"

                st.markdown(final_output)
                
                if show_sources and sources:
                    with st.expander("📚 Sources Used"):
                        for s in sources:
                            st.markdown(f"**{s.get('filename','?')}** ({int(s.get('relevance',0))}%)")
                            st.caption(s.get('snippet',''))

                # Append to history
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": final_output,
                    "sources": sources
                })

            except Exception as e:
                st.error(f"Connection error: {e}")

# Footer
st.markdown("---")
st.caption("💡 Choose between fast vector search or intelligent graph reasoning. All data stays local.")
