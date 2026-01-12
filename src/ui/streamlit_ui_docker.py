#!/usr/bin/env python3
"""
Enhanced Streamlit UI for Obsidian RAG - Docker Version
Uses Unified API Gateway for all operations.
"""

import streamlit as st
import requests
import json
import os
import logging
import asyncio
import websockets
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Service Configuration
# In Docker, we use the internal hostname 'api-gateway' and port 3000
API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api-gateway:3000")
WS_GATEWAY_URL = API_GATEWAY_URL.replace("http", "ws") + "/api/v1/deep-research"

st.set_page_config(
    page_title="Obsidian RAG",
    page_icon="🧠",
    layout="wide"
)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'search_mode' not in st.session_state:
    # default to hybrid as per standard use
    st.session_state.search_mode = 'hybrid'

# Sidebar configuration
with st.sidebar:
    st.title("🧠 Obsidian RAG")
    st.markdown("Unified Knowledge Retrieval")
    
    st.markdown("---")
    
    # Search Mode Selection
    st.subheader("🔍 Search Mode")
    search_mode = st.radio(
        "Choose search method:",
        ["vector", "graph", "hybrid"],
        index=2,
        help="""
        - **vector**: Fast semantic search 🔍
        - **graph**: Knowledge graph reasoning 🧠
        - **hybrid**: Graph-guided vector search 🔗
        """
    )
    st.session_state.search_mode = search_mode
    
    st.markdown("---")
    
    # LLM Provider Selection (passed to backend)
    st.subheader("🤖 LLM Provider")
    llm_options = ["Ollama", "Gemini", "Claude", "Kimi", "GPT-OSS"]
    llm_choice = st.selectbox(
        "Choose Backend LLM:",
        llm_options,
        index=0
    )
    st.session_state.llm_provider = llm_choice.lower()
    
    year = 2024
    
    # Deep Thinking Toggle (Moved)
    deep_thinking = st.checkbox("🧠 Deep Thinking", value=False, 
                                help="Enable specific deep reasoning agent (overrides Search Mode)")
    
    enhanced_search = st.checkbox("Enhanced Search", value=False, 
                                   help="Add LLM Knowledge and Web Search sections to standard results")
    show_sources = st.checkbox(
        "Show Sources",
        value=True,
        help="Display cited sources with answers"
    )
    st.session_state.show_sources = show_sources
    
    st.markdown("---")
    
    # Gateway Status
    st.subheader("📊 System Status")
    try:
        health_resp = requests.get(f'{API_GATEWAY_URL}/api/v1/health', timeout=2)
        if health_resp.status_code == 200:
            health_data = health_resp.json().get('data', {})
            gw_status = health_data.get('gateway', 'unknown')
            services = health_data.get('services', {})
            
            st.success(f"✅ Gateway: {gw_status}")
            
            emb_status = services.get('embedding', {}).get('status', 'unknown')
            if emb_status == 'healthy':
                st.caption("✅ Embedding Service")
            else:
                st.error(f"❌ Embedding: {emb_status}")
                
            graph_service = services.get('networkx') or services.get('graph', {})
            graph_status = graph_service.get('status', 'unknown')
            if graph_status == 'healthy':
                st.caption("✅ Graph Service")
            else:
                st.error(f"❌ Graph: {graph_status}")
        else:
            st.error("⚠️ Gateway Unreachable")
    except Exception as e:
        st.error(f"⚠️ Gateway Offline: {e}")
    
    st.markdown("---")
    
    # Settings
    st.subheader("⚙️ Settings")
    
    num_sources = st.slider("Sources", 1, 50, 10)
    temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1)
    
    st.markdown("---")
    
    st.markdown("---")
    
    # Actions
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Main chat interface
st.title("💬 Chat with Your Knowledge Base")

# Indicator
if deep_thinking:
    st.caption("🚀 Mode: **Deep Thinking Agent** (WebSocket)")
else:
    mode_emoji = {'vector': '🔍', 'graph': '🧠', 'hybrid': '🔗'}
    st.caption(f"{mode_emoji.get(search_mode, '🔍')} Mode: **{search_mode}**")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and "sources" in message and show_sources and message["sources"]:
            with st.expander("📚 Sources"):
                for source in message["sources"]:
                    st.markdown(f"**{source.get('filename','?')}** ({int(source.get('relevance',0))}%)")
                    st.caption(source.get('snippet',''))

# Async handler for Deep Thinking
async def run_deep_thinking(user_query, log_container, result_container):
    try:
        async with websockets.connect(WS_GATEWAY_URL) as websocket:
            await websocket.send(json.dumps({"query": user_query}))
            
            logs = []
            final_ans = ""
            
            while True:
                try:
                    msg = await websocket.recv()
                    data = json.loads(msg)
                    msg_type = data.get("type")
                    
                    if msg_type == "log":
                        log_msg = f"{data.get('message')}"
                        # Replace previous log with new one
                        log_container.info(f"🔄 {log_msg}")
                            
                    elif msg_type == "status":
                        # Also update for major status changes
                        log_container.info(f"🚦 {data.get('content')}")
                            
                    elif msg_type == "result":

                        # The 'data' field might be a dictionary or a JSON string
                        raw_data = data.get("data", {})
                        
                        # Handle case where it's a stringified JSON
                        if isinstance(raw_data, str):
                            try:
                                # Try to parse it if it looks like JSON
                                if raw_data.strip().startswith("{"):
                                    parsed_data = json.loads(raw_data)
                                    final_ans = parsed_data
                                else:
                                    # It's just a string answer
                                    final_ans = {"answer": raw_data}
                            except json.JSONDecodeError:
                                final_ans = {"answer": raw_data}
                        elif isinstance(raw_data, dict):
                            final_ans = raw_data
                        else:
                             final_ans = {"answer": str(raw_data)}
                             
                        break
                        
                    elif msg_type == "error":
                        st.error(f"Agent Error: {data.get('content')}")
                        return None
                        
                except websockets.exceptions.ConnectionClosed:
                    break
            
            return final_ans
            
    except Exception as e:
        st.error(f"WebSocket Error: {e}")
        return None

# Chat input
if prompt := st.chat_input("Ask about your notes..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant"):
        
        # Branch 1: Deep Thinking (WebSocket)
        if deep_thinking:
            st.markdown("🤔 **Deep Thinking Agent Active**")
            
            # Use an empty placeholder for dynamic status updates
            status_placeholder = st.empty()
            result_placeholder = st.empty()
            
            # Run async loop
            result_payload = asyncio.run(run_deep_thinking(prompt, status_placeholder, result_placeholder))
            
            # Clear the status logs when finished
            status_placeholder.empty()
            
            if result_payload:
                # Extract components
                answer_text = result_payload.get("answer", "No answer generated.")
                citations = result_payload.get("citations", [])
                
                # Render content
                result_placeholder.markdown(answer_text)
                
                # Render structured citations if available
                if citations:
                    with st.expander("📚 Research References"):
                        for cit in citations:
                            # Handle different citation formats (string or object)
                            if isinstance(cit, str):
                                st.markdown(f"- {cit}")
                            elif isinstance(cit, dict):
                                st.markdown(f"**{cit.get('title', 'Ref')}**")
                                st.caption(cit.get('url', ''))
                
                # Append to history with structured format transparency
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer_text,
                    "sources": [{"filename": c} for c in citations] if citations else [] # approximate format for history
                })
        
        # Branch 2: Standard Unified Search (HTTP)
        else:
            with st.spinner(f"Searching ({st.session_state.search_mode})..."):
                try:
                    payload = {
                        'query': prompt,
                        'mode': st.session_state.search_mode,
                        'llm_provider': st.session_state.llm_provider,
                        'temperature': temperature,
                        'n_results': num_sources,
                        'llm_knowledge': enhanced_search,
                        'web_search': enhanced_search and st.session_state.llm_provider in ["gemini", "claude", "kimi"]
                    }
                    
                    response = requests.post(
                        f"{API_GATEWAY_URL}/api/v1/search",
                        json=payload,
                        timeout=180
                    )
                    
                    if response.status_code != 200:
                        st.error(f"Backend error ({response.status_code}): {response.text}")
                    else:
                        result = response.json()
                        answer = result.get('answer', '')
                        sources = result.get('sources', [])
                        
                        # Construct output
                        final_output = answer
                        
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

                        st.markdown(final_output)
                        
                        if show_sources and sources:
                            with st.expander("📚 Sources Used"):
                                for s in sources:
                                    st.markdown(f"**{s.get('filename','?')}** ({int(s.get('relevance',0))}%)")
                                    st.caption(s.get('snippet',''))
                        
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": final_output,
                            "sources": sources
                        })

                except Exception as e:
                    st.error(f"Connection error: {e}")

st.caption("💡 Unified API Gateway Connected")
