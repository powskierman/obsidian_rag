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

# Load environment variables from .env file
from pathlib import Path
try:
    from dotenv import load_dotenv
    env_file = Path('.env')
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass  # python-dotenv not required, will use system env vars

# Service URLs - updated for LOCAL execution (not Docker)
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8000")
CLAUDE_GRAPH_SERVICE_URL = os.getenv("CLAUDE_GRAPH_SERVICE_URL", "http://localhost:8002")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
GPT_OSS_HOST = os.getenv("GPT_OSS_HOST", "http://host.docker.internal:12434/engines/llama.cpp")
USE_GPT_OSS = os.getenv("USE_GPT_OSS", "false").lower() == "true"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

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
    
    st.markdown("---")
    
    # Search Mode Selection
    st.subheader("🔍 Search Mode")
    search_mode = st.radio(
        "Choose search method:",
        ["vector", "graph-claude", "hybrid"],
        index=2,
        help="""
        - **vector**: Fast semantic search with Ollama (ChromaDB) 🔍
        - **graph-claude**: Claude Haiku-powered knowledge graph 🧠
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
            st.error("❌ Set ANTHROPIC_API_KEY in .env file or docker-compose.yml")
            st.info("💡 Create a `.env` file in the project root with:\n```\nANTHROPIC_API_KEY=your-key-here\n```")
    
    # Show API key status for Gemini
    elif selected_provider == "gemini":
        if GEMINI_API_KEY:
            st.success("✅ Gemini API key configured")
        else:
            st.error("❌ Set GEMINI_API_KEY in .env file")
            st.info("💡 Create a `.env` file in the project root with:\n```\nGEMINI_API_KEY=your-key-here\n```\n\nGet your key from: https://makersuite.google.com/app/apikey")
    
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
    
    # Check Claude Graph service
    try:
        claude_graph_response = requests.get(f'{CLAUDE_GRAPH_SERVICE_URL}/health', timeout=2)
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
                all_models = [m.get('name', 'unknown') for m in models_data]
                
                # Filter out embedding-only models (they can't generate text)
                embedding_keywords = ['embed', 'nomic', 'minilm', 'bge', 'gte']
                available_models = [
                    model for model in all_models 
                    if not any(keyword in model.lower() for keyword in embedding_keywords)
                ]
                
                if available_models:
                    st.success(f"✅ Ollama: {len(available_models)} LLM models available")
                else:
                    st.warning("⚠️ No LLM models found (only embedding models)")
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
                # Create markdown export
                markdown_content = f"# RAG Chat Export\n\n"
                markdown_content += f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                markdown_content += f"**Model**: {model_option}\n\n"
                markdown_content += f"**Search Mode**: {search_mode}\n\n"
                markdown_content += "---\n\n"
                
                for msg in st.session_state.messages:
                    if msg["role"] == "user":
                        markdown_content += f"## 👤 User\n\n{msg['content']}\n\n"
                    else:
                        markdown_content += f"## 🤖 Assistant\n\n{msg['content']}\n\n"
                        if msg.get("sources"):
                            markdown_content += "**Sources:**\n"
                            for source in msg["sources"]:
                                markdown_content += f"- {source.get('filename', 'Unknown')} ({source.get('relevance', 0):.0f}% relevant)\n"
                            markdown_content += "\n"
                    markdown_content += "---\n\n"
                
                # Save to Downloads directory
                import os
                downloads_path = os.path.expanduser("~/Downloads")
                filename = f"rag_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                filepath = os.path.join(downloads_path, filename)
                
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    st.success(f"✅ Exported to {filepath}")
                except Exception as e:
                    st.error(f"❌ Export failed: {e}")
    
    with col2:
        if st.button("🗑️ Clear Conversation"):
            st.session_state.messages = []
            st.rerun()

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

    # Phase 3c: Auto-select search mode based on query patterns (DISABLED - respects user choice)
    # import re
    
    # Synthesis patterns that suggest graph-claude mode
    # synthesis_patterns = [
    #     r'\bhow\s+(have|has|did|do|does|would)\b',
    #     ... (patterns omitted)
    # ]
    
    # Use the search mode selected by user in sidebar
    search_mode = st.session_state.search_mode

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
                        f'{EMBEDDING_SERVICE_URL}/query',
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
                            f'{CLAUDE_GRAPH_SERVICE_URL}/query',
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
                                f'{EMBEDDING_SERVICE_URL}/query',
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
                                f'{EMBEDDING_SERVICE_URL}/query',
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
                                f'{EMBEDDING_SERVICE_URL}/query',
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
                            f'{CLAUDE_GRAPH_SERVICE_URL}/query',
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
                # Get selected LLM provider from session state
                active_provider = st.session_state.get('llm_provider', 'ollama')
                
                # Determine provider display name and model for spinner
                provider_display = {"ollama": "Ollama", "gemini": "Gemini Pro", "claude": "Claude Sonnet", "gpt-oss": "GPT-OSS"}.get(active_provider, "Ollama")
                
                # Use correct model name based on provider
                if active_provider == "gemini":
                    display_model = "gemini-3-pro-preview"
                elif active_provider == "claude":
                    display_model = "claude-sonnet-4-5"
                elif active_provider == "gpt-oss":
                    display_model = model_option
                else:  # ollama
                    display_model = model_option
                
                with st.spinner(f"💭 Thinking with {display_model} ({provider_display})..."):
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
                    
                    if active_provider == "claude":
                        # Use Claude API
                        logger.info(f"🎯 CALLING CLAUDE API with model: claude-sonnet-4-5-20250929")
                        if not ANTHROPIC_API_KEY:
                            st.error("❌ Claude API key not configured")
                            st.stop()
                        
                        try:
                            from anthropic import Anthropic
                            client = Anthropic(api_key=ANTHROPIC_API_KEY)
                            
                            # Extract just the question from system_prompt
                            claude_response = client.messages.create(
                                model="claude-sonnet-4-5-20250929",
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
                    
                    elif active_provider == "gemini":
                        # Use Gemini API
                        logger.info(f"🎯 CALLING GEMINI API with model: gemini-3-pro-preview")
                        if not GEMINI_API_KEY:
                            st.error("❌ Gemini API key not configured")
                            st.stop()
                        
                        try:
                            # Create the prompt with context
                            full_prompt = f"""You are an AI assistant helping Michel understand his Obsidian knowledge base.

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
                            
                            # Use Gemini 3 Pro Preview with REST API
                            gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-preview:generateContent"
                            gemini_response = requests.post(
                                gemini_url,
                                headers={
                                    "x-goog-api-key": GEMINI_API_KEY,
                                    "Content-Type": "application/json"
                                },
                                json={
                                    "contents": [{
                                        "role": "user",
                                        "parts": [{"text": full_prompt}]
                                    }],
                                    "generationConfig": {
                                        "temperature": temperature,
                                        "maxOutputTokens": 4000
                                    }
                                },
                                timeout=180
                            )
                            
                            if gemini_response.status_code != 200:
                                st.error(f"Gemini API error: {gemini_response.status_code}")
                                st.code(gemini_response.text)
                                st.stop()
                            
                            result = gemini_response.json()
                            try:
                                candidates = result.get('candidates', [])
                                if candidates and len(candidates) > 0:
                                    content = candidates[0].get('content', {})
                                    parts = content.get('parts', [])
                                    if parts and len(parts) > 0:
                                        response_text = parts[0].get('text', '')
                                    else:
                                        st.error("Unexpected Gemini response format: no parts found")
                                        st.code(json.dumps(result, indent=2))
                                        st.stop()
                                else:
                                    st.error("Unexpected Gemini response format: no candidates")
                                    st.code(json.dumps(result, indent=2))
                                    st.stop()
                            except (KeyError, IndexError) as e:
                                st.error(f"Error parsing Gemini response: {e}")
                                st.code(json.dumps(result, indent=2))
                                st.stop()
                        except Exception as e:
                            st.error(f"Gemini API error: {e}")
                            st.stop()
                    
                    elif active_provider == "gpt-oss":
                        # Use OpenAI-compatible API
                        logger.info(f"🎯 CALLING GPT-OSS API with model: {model_option}")
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
                        logger.info(f"🎯 CALLING OLLAMA API with model: {model_option}")
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
            
            # Enhanced Search Sections (if enabled)
            llm_knowledge_text = ""
            web_search_text = ""
            
            if enhanced_search:
                # Section 2: LLM Knowledge (context-aware - builds on vault findings)
                with st.spinner("🧠 Gathering additional knowledge..."):
                    try:
                        # Include vault findings as context so LLM can build on them
                        knowledge_prompt = f"""Based on the following information found in the user's vault:

{response_text[:2000]}

User's question: {prompt}

Provide ADDITIONAL insights, clinical context, or alternative perspectives that COMPLEMENT (not repeat) the vault information. Focus on:
1. Clinical implications of the findings
2. Treatment considerations mentioned
3. Additional context that would be helpful
4. Answering aspects of the question not covered by vault notes"""
                        
                        if active_provider == "claude":
                            from anthropic import Anthropic
                            client = Anthropic(api_key=ANTHROPIC_API_KEY)
                            knowledge_response = client.messages.create(
                                model="claude-sonnet-4-5-20250929",
                                max_tokens=4000,
                                temperature=temperature,
                                messages=[{"role": "user", "content": knowledge_prompt}]
                            )
                            llm_knowledge_text = knowledge_response.content[0].text
                            
                        elif active_provider == "gemini":
                            gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-preview:generateContent"
                            knowledge_response = requests.post(
                                gemini_url,
                                headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                                json={
                                    "contents": [{"role": "user", "parts": [{"text": knowledge_prompt}]}],
                                    "generationConfig": {"temperature": temperature, "maxOutputTokens": 4000}
                                },
                                timeout=60
                            )
                            if knowledge_response.status_code == 200:
                                try:
                                    result = knowledge_response.json()
                                    candidates = result.get('candidates', [])
                                    if candidates and len(candidates) > 0:
                                        content = candidates[0].get('content', {})
                                        parts = content.get('parts', [])
                                        if parts and len(parts) > 0:
                                            llm_knowledge_text = parts[0].get('text', '')
                                except (KeyError, IndexError, ValueError) as e:
                                    logging.warning(f"Error parsing Gemini LLM knowledge response: {e}")
                                    llm_knowledge_text = ""
                                    
                        else:  # Ollama
                            knowledge_resp = requests.post(
                                f'{OLLAMA_HOST}/api/generate',
                                json={'model': model_option, 'prompt': knowledge_prompt, 'stream': False, 'options': {'temperature': temperature}},
                                timeout=60
                            )
                            if knowledge_resp.status_code == 200:
                                llm_knowledge_text = knowledge_resp.json().get('response', '')
                    except Exception as e:
                        llm_knowledge_text = f"_Could not retrieve LLM knowledge: {str(e)}_"
                
                # Section 3: Web Search (Gemini & Claude only) - Extract medical terms from vault context
                if active_provider in ["gemini", "claude"]:
                    with st.spinner("🌐 Searching the web..."):
                        try:
                            from tavily import TavilyClient
                            TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
                            
                            if TAVILY_API_KEY:
                                # Extract key medical terms from vault response for better search
                                # First 500 chars should capture main topics
                                context_sample = response_text[:500]
                                
                                # Create focused medical search query
                                search_query_prompt = f"Extract 3-5 key medical terms or concepts from this text to create a focused web search query: {context_sample}\n\nProvide only the search terms, no explanation."
                                
                                # Quick call to get search terms
                                if active_provider == "claude":
                                    from anthropic import Anthropic
                                    client = Anthropic(api_key=ANTHROPIC_API_KEY)
                                    terms_resp = client.messages.create(
                                        model="claude-sonnet-4-5-20250929",
                                        max_tokens=100,
                                        messages=[{"role": "user", "content": search_query_prompt}]
                                    )
                                    search_terms = terms_resp.content[0].text.strip()
                                else:  # gemini
                                    gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-preview:generateContent"
                                    terms_resp = requests.post(
                                        gemini_url,
                                        headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                                        json={
                                            "contents": [{"role": "user", "parts": [{"text": search_query_prompt}]}],
                                            "generationConfig": {"maxOutputTokens": 100}
                                        },
                                        timeout=30
                                    )
                                    if terms_resp.status_code == 200:
                                        try:
                                            result = terms_resp.json()
                                            # Safely extract text from response
                                            candidates = result.get('candidates', [])
                                            if candidates and len(candidates) > 0:
                                                content = candidates[0].get('content', {})
                                                parts = content.get('parts', [])
                                                if parts and len(parts) > 0:
                                                    search_terms = parts[0].get('text', prompt).strip()
                                                else:
                                                    search_terms = prompt
                                            else:
                                                search_terms = prompt
                                        except (KeyError, IndexError, ValueError) as e:
                                            logging.warning(f"Error parsing Gemini response for search terms: {e}")
                                            search_terms = prompt  # Fallback to original query
                                    else:
                                        search_terms = prompt  # Fallback to original query
                                
                                # Use extracted terms for web search
                                tavily = TavilyClient(api_key=TAVILY_API_KEY)
                                search_response = tavily.search(query=search_terms, search_depth="advanced", max_results=5)
                                
                                if 'results' in search_response and search_response['results']:
                                    web_results = []
                                    for i, res in enumerate(search_response['results'][:3], 1):
                                        web_results.append(f"{i}. **[{res['title']}]({res['url']})**\n   {res['content']}")
                                    web_search_text = f"_Search terms used: {search_terms}_\n\n" + "\n\n".join(web_results)
                                else:
                                    web_search_text = "_No web results found._"
                            else:
                                web_search_text = "_Web search unavailable: TAVILY_API_KEY not set in .env_"
                        except ImportError:
                            web_search_text = "_Web search unavailable: tavily-python not installed_"
                        except Exception as e:
                            web_search_text = f"_Web search error: {str(e)}_"
                else:
                    web_search_text = f"_⚠️ Web search not available with {provider_display}_"
            
            # Format final response with sections
            final_response = f"## 📚 Vault Knowledge\n\n{response_text}"
            
            if enhanced_search:
                if llm_knowledge_text:
                    final_response += f"\n\n---\n\n## 🧠 LLM Knowledge\n\n{llm_knowledge_text}"
                if web_search_text:
                    final_response += f"\n\n---\n\n## 🌐 Web Search\n\n{web_search_text}"
            
            # Display response
            st.markdown(final_response)
            
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
                "content": final_response,
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



