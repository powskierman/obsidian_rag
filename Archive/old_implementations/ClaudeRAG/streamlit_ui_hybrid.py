"""
Enhanced Streamlit UI with Hybrid Search
Combines ChromaDB vector search + Claude knowledge graph
"""

import streamlit as st
import requests
import json
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Obsidian RAG with Knowledge Graph",
    page_icon="🧠",
    layout="wide"
)

# Service URLs
EMBEDDING_SERVICE_URL = "http://embedding-service:8000"
GRAPH_SERVICE_URL = "http://graph-service:8002"
OLLAMA_URL = "http://host.docker.internal:11434"

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'graph_available' not in st.session_state:
    st.session_state.graph_available = False

def check_graph_availability():
    """Check if graph service is available"""
    try:
        response = requests.get(f"{GRAPH_SERVICE_URL}/health", timeout=2)
        if response.status_code == 200:
            data = response.json()
            return data.get('graph_loaded', False)
    except:
        pass
    return False

def vector_search(query: str, n_results: int = 5):
    """Search using ChromaDB vector database"""
    try:
        response = requests.post(
            f"{EMBEDDING_SERVICE_URL}/query",
            json={"query": query, "n_results": n_results},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Vector search error: {e}")
        return None

def graph_search(query: str):
    """Search using Claude-powered knowledge graph"""
    try:
        response = requests.post(
            f"{GRAPH_SERVICE_URL}/query",
            json={"query": query, "max_entities": 20},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Graph search error: {e}")
        return None

def hybrid_search(query: str, n_vector_results: int = 5):
    """
    Hybrid search: Combines vector and graph search
    Returns both vector chunks and graph reasoning
    """
    results = {
        'vector': None,
        'graph': None,
        'query': query,
        'timestamp': datetime.now().isoformat()
    }
    
    # Run both searches in parallel (conceptually)
    col1, col2 = st.columns(2)
    
    with col1:
        with st.spinner("🔍 Searching vector database..."):
            results['vector'] = vector_search(query, n_vector_results)
    
    with col2:
        if st.session_state.graph_available:
            with st.spinner("🧠 Analyzing knowledge graph..."):
                results['graph'] = graph_search(query)
    
    return results

def get_graph_stats():
    """Get knowledge graph statistics"""
    try:
        response = requests.get(f"{GRAPH_SERVICE_URL}/stats", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def display_vector_results(results):
    """Display vector search results"""
    if not results or 'results' not in results:
        st.warning("No vector results found")
        return
    
    st.subheader("📚 Vector Search Results")
    
    documents = results['results'].get('documents', [])
    metadatas = results['results'].get('metadatas', [])
    distances = results['results'].get('distances', [])
    
    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
        with st.expander(f"📄 {meta.get('filename', 'Unknown')} (similarity: {1-dist:.3f})"):
            st.markdown(doc)
            st.caption(f"Source: {meta.get('filename', 'Unknown')}")

def display_graph_results(results):
    """Display graph search results"""
    if not results or 'answer' not in results:
        st.warning("No graph results available")
        return
    
    st.subheader("🧠 Knowledge Graph Analysis")
    st.markdown(results['answer'])

def search_entities(query: str):
    """Search for entities in the graph"""
    try:
        response = requests.post(
            f"{GRAPH_SERVICE_URL}/search_entities",
            json={"query": query, "limit": 10},
            timeout=5
        )
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

# Main UI
st.title("🧠 Obsidian RAG with Knowledge Graph")
st.markdown("*Combining vector search + Claude-powered knowledge graph*")

# Check graph availability
st.session_state.graph_available = check_graph_availability()

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Search mode
    search_mode = st.selectbox(
        "Search Mode",
        [
            "Hybrid (Vector + Graph)",
            "Vector Only",
            "Graph Only"
        ],
        disabled=not st.session_state.graph_available
    )
    
    n_results = st.slider("Vector Results", 3, 10, 5)
    
    st.divider()
    
    # System status
    st.header("📊 System Status")
    
    # Embedding service
    try:
        response = requests.get(f"{EMBEDDING_SERVICE_URL}/stats", timeout=2)
        if response.status_code == 200:
            stats = response.json()
            st.success("✅ Embedding Service")
            st.metric("Total Chunks", stats.get('total_chunks', 'Unknown'))
    except:
        st.error("❌ Embedding Service")
    
    # Graph service
    if st.session_state.graph_available:
        graph_stats = get_graph_stats()
        if graph_stats:
            st.success("✅ Graph Service")
            st.metric("Entities", graph_stats.get('total_nodes', 0))
            st.metric("Relationships", graph_stats.get('total_edges', 0))
            
            # Top entities
            if 'top_entities' in graph_stats:
                with st.expander("🌟 Top Entities"):
                    for entity in graph_stats['top_entities'][:5]:
                        st.write(f"• {entity['entity']}: {entity['connections']} connections")
    else:
        st.warning("⚠️ Graph Service")
        st.caption("Graph not built yet. Use build_knowledge_graph.py to create it.")
    
    st.divider()
    
    # Graph exploration
    if st.session_state.graph_available:
        st.header("🔍 Explore Graph")
        
        entity_search = st.text_input("Search entities", placeholder="e.g., 'CAR-T'")
        if entity_search:
            entity_results = search_entities(entity_search)
            if entity_results and entity_results.get('results'):
                st.write(f"Found {entity_results['total']} entities:")
                for entity in entity_results['results'][:5]:
                    st.write(f"• **{entity['name']}** ({entity['type']}) - {entity['connections']} connections")

# Main search interface
st.header("💬 Ask a Question")

query = st.text_input(
    "Your question",
    placeholder="e.g., What do I know about lymphoma treatment?",
    label_visibility="collapsed"
)

if st.button("🔍 Search", type="primary", disabled=not query):
    if query:
        # Perform search based on mode
        if search_mode == "Hybrid (Vector + Graph)":
            results = hybrid_search(query, n_results)
            
            # Display in tabs
            tab1, tab2 = st.tabs(["📚 Vector Results", "🧠 Graph Analysis"])
            
            with tab1:
                display_vector_results(results.get('vector'))
            
            with tab2:
                if st.session_state.graph_available:
                    display_graph_results(results.get('graph'))
                else:
                    st.warning("Graph service not available")
        
        elif search_mode == "Vector Only":
            results = vector_search(query, n_results)
            display_vector_results(results)
        
        elif search_mode == "Graph Only":
            if st.session_state.graph_available:
                results = graph_search(query)
                display_graph_results(results)
            else:
                st.error("Graph service not available")

# Example queries
with st.expander("💡 Example Queries"):
    st.markdown("""
    **Medical Questions:**
    - What treatments are mentioned in my medical notes?
    - How are my scans related to my treatment plan?
    - What's the timeline of my medical journey?
    
    **Technical Questions:**
    - What 3D printing projects have I worked on?
    - How does Fusion 360 relate to my designs?
    - What programming languages do I use?
    
    **Cross-Domain:**
    - How do my technical skills relate to my medical situation?
    - What patterns exist across my different interests?
    """)

# Footer
st.divider()
st.caption(f"System: {n_results} vector results | Graph: {'✅ Available' if st.session_state.graph_available else '❌ Not built'}")
