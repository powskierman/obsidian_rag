import streamlit as st
import requests
import json
from datetime import datetime

st.set_page_config(
    page_title="Obsidian RAG",
    page_icon="🧠",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stChatMessage {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 10px;
        margin: 5px 0;
    }
    .source-box {
        background-color: #e8eaf6;
        border-left: 3px solid #3f51b5;
        padding: 10px;
        margin: 5px 0;
        border-radius: 5px;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("🧠 Obsidian RAG")
    st.markdown("---")
    
    # Settings
    st.subheader("⚙️ Settings")
    
    # Auto-detect available models
    try:
        models_response = requests.get('http://localhost:11434/api/tags', timeout=2)
        available_models = [m['name'] for m in models_response.json()['models']]
        
        if not available_models:
            available_models = ["No models found"]
            st.error("⚠️ No Ollama models found!")
            st.info("Run: `ollama pull llama3.2:3b`")
        else:
            st.success(f"✅ {len(available_models)} models available")
    except Exception as e:
        available_models = ["Cannot connect to Ollama"]
        st.error(f"⚠️ Cannot connect to Ollama")
        st.info("Make sure Ollama is running: `ollama serve`")
    
    model_option = st.selectbox(
        "Model",
        available_models,
        help="Choose your LLM model"
    )
    
    num_sources = st.slider(
        "Number of sources",
        min_value=1,
        max_value=10,
        value=5,
        help="How many relevant notes to retrieve"
    )
    
    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=0.3,
        step=0.1,
        help="Lower = more focused, Higher = more creative"
    )
    
    show_sources = st.checkbox("Show sources", value=True)
    
    st.markdown("---")
    
    # Stats
    try:
        stats = requests.get('http://localhost:8000/stats', timeout=2).json()
        st.metric("📚 Notes Indexed", stats['total_documents'])
        
        if stats['total_documents'] == 0:
            st.warning("⚠️ No documents indexed yet!")
            st.info("Run: `python obsidian_scanner.py`")
    except Exception as e:
        st.error("⚠️ Embedding service not running")
        st.info("Run: `python embedding_service.py`")
    
    st.markdown("---")
    
    # Actions
    if st.button("🔄 Rescan Vault"):
        st.info("Run in terminal: `python obsidian_scanner.py`")
    
    if st.button("🗑️ Clear Database", type="secondary"):
        if st.button("⚠️ Confirm Clear"):
            requests.post('http://localhost:8000/clear')
            st.success("Database cleared!")
            st.rerun()

# Main chat interface
st.title("💬 Chat with Your Obsidian Vault")
st.caption("Ask questions about your notes, get insights, and explore your knowledge base")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "sources" in message and show_sources:
            with st.expander("📚 Sources", expanded=False):
                for source in message["sources"]:
                    st.markdown(f"""
                    <div class="source-box">
                        <strong>{source['filename']}</strong><br>
                        <small>{source['filepath']}</small><br>
                        {source['text'][:200]}...
                    </div>
                    """, unsafe_allow_html=True)

# Chat input
# Chat input
if prompt := st.chat_input("Ask about your notes..."):
    if model_option in ["Cannot connect to Ollama", "No models found"]:
        st.error("⚠️ Ollama is not ready.")
        st.stop()
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        try:
            # Step 1: Get context
            with st.spinner("Searching your notes..."):
                context_response = requests.post(
                    'http://localhost:8000/query',
                    json={'query': prompt, 'n_results': num_sources},
                    timeout=10
                )
                
                if context_response.status_code != 200:
                    st.error("Embedding service error")
                    st.stop()
                
                results = context_response.json()
                documents = results.get('documents', [[]])[0]
                metadatas = results.get('metadatas', [[]])[0]
                distances = results.get('distances', [[]])[0]
            
            if not documents:
                st.warning("No relevant notes found.")
                st.stop()
            
            # Prepare context
            context_parts = []
            sources = []
            
            for doc, meta, dist in zip(documents, metadatas, distances):
                if doc and doc.strip():
                    filename = meta.get('filename', 'unknown')
                    context_parts.append(f"From {filename}:\n{doc}")
                    sources.append({
                        'filename': filename,
                        'filepath': meta.get('filepath', 'unknown'),
                        'text': doc,
                        'relevance': 1 - dist
                    })
            
            context_text = "\n\n---\n\n".join(context_parts)
            
            # Step 2: Query Ollama (using stable /generate endpoint)
            full_prompt = f"""Based on these notes from the user's knowledge base, answer their question:

{context_text}

Question: {prompt}

Answer:"""
            
            with st.spinner(f"Thinking with {model_option}..."):
                try:
                    # Use /generate instead of /chat (more stable, no subprocess issues)
                    ollama_response = requests.post(
                        'http://localhost:11434/api/generate',
                        json={
                            'model': model_option,
                            'prompt': full_prompt,
                            'stream': False,
                            'options': {
                                'temperature': temperature,
                                'num_ctx': 4096
                            }
                        },
                        timeout=120
                    )
                    
                    if ollama_response.status_code == 200:
                        response_text = ollama_response.json().get('response', 'No response')
                    else:
                        st.error(f"Ollama returned {ollama_response.status_code}")
                        st.code(ollama_response.text)
                        st.stop()
                        
                except requests.exceptions.Timeout:
                    st.error("⏱️ Ollama timed out. Try a smaller model.")
                    st.stop()
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to Ollama. Is it running?")
                    st.stop()
            
            # Display response
            st.markdown(response_text)
            
            # Show sources
            if show_sources and sources:
                with st.expander("📚 Sources Used", expanded=True):
                    for source in sources:
                        st.markdown(f"""
                        <div class="source-box">
                            <strong>{source['filename']}</strong> 
                            <small>(Relevance: {source['relevance']:.0%})</small><br>
                            <small>📁 {source['filepath']}</small><br>
                            <em>{source['text'][:200]}...</em>
                        </div>
                        """, unsafe_allow_html=True)
            
            # Save to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_text,
                "sources": sources
            })
            
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            import traceback
            with st.expander("🐛 Debug Info"):
                st.code(traceback.format_exc())
# Clear chat button
if st.session_state.messages:
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()