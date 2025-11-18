#!/usr/bin/env python3
"""
Enhanced Streamlit UI for Obsidian RAG
Features: Better stats display, metadata filtering, conversation export
"""

import streamlit as st
import requests
from datetime import datetime
import json

st.set_page_config(
    page_title="Obsidian RAG",
    page_icon="🧠",
    layout="wide"
)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []

# Sidebar configuration
with st.sidebar:
    st.title("🧠 Obsidian RAG")
    st.markdown("Query your knowledge base with AI")
    
    st.markdown("---")
    
    # Stats with better display
    st.subheader("📊 Statistics")
    try:
        stats = requests.get('http://localhost:8000/stats', timeout=2).json()
        total_chunks = stats['total_documents']
        est_notes = stats.get('estimated_notes', int(total_chunks / 4.4))
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📚 Chunks", f"{total_chunks:,}")
        with col2:
            st.metric("📝 Notes", f"~{est_notes:,}")
        
        st.caption("💡 Documents are chunked for precision")
    except:
        st.error("⚠️ Embedding service offline")
        st.caption("Start: `./start_obsidian_rag.sh`")
    
    st.markdown("---")
    
    # Model selection
    st.subheader("⚙️ Settings")

    model_option = st.selectbox(
        "Model",
        ["qwen2.5-coder:32b", "qwen2.5:32b", "qwen2.5:14b", "deepseek-r1:14b", "llama3.2:3b"],
        help="Recommended: qwen2.5-coder:32b for medical + coding"
    )

    retrieval_mode = st.selectbox(
        "Retrieval Mode",
        ["vector", "graph-naive", "graph-local", "graph-global", "graph-hybrid"],
        value="vector",
        help="vector=fast | graph=better reasoning"
    )

    num_sources = st.slider(
        "Number of Sources",
        min_value=1,
        max_value=20,
        value=5,
        help="More sources = more context but slower"
    )

    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.0,
        value=0.3,
        step=0.1,
        help="Lower = more focused, Higher = more creative"
    )

    show_sources = st.checkbox("Show Sources", value=True)
    use_reranking = st.checkbox("Use Re-ranking", value=True, help="Better precision but slower")
    deduplicate = st.checkbox("Deduplicate Sources", value=True)
    
    st.markdown("---")
    
    # Advanced filters
    with st.expander("🔍 Advanced Filters"):
        tag_filter = st.multiselect(
            "Filter by tags",
            ["medical", "lymphoma", "tech", "ai", "3d-printing", "raspberry-pi"],
            help="Only show notes with these tags"
        )
        
        date_filter = st.date_input(
            "Notes after date",
            value=None,
            help="Only search recent notes"
        )
    
    st.markdown("---")

    # Metrics & Feedback
    st.subheader("📈 Feedback System")
    show_metrics = st.checkbox("Show Metrics Dashboard", value=False)

    if show_metrics:
        try:
            metrics_response = requests.get('http://localhost:8000/metrics?hours=24', timeout=2)
            if metrics_response.status_code == 200:
                metrics_data = metrics_response.json()
                metrics = metrics_data.get('metrics', {})

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Queries", metrics.get('total_queries', 0))
                with col2:
                    st.metric("Feedback Rate", f"{metrics.get('feedback_rate', 0):.1f}%")

                col3, col4 = st.columns(2)
                with col3:
                    st.metric("Avg Rating", f"{metrics.get('avg_rating', 0):.2f}/5")
                with col4:
                    st.metric("Success Rate", f"{metrics.get('success_rate', 0):.1f}%")

                # Mode performance
                mode_perf = metrics_data.get('mode_performance', [])
                if mode_perf:
                    st.caption("Performance by Mode")
                    for perf in mode_perf:
                        st.write(f"**{perf['mode']}**: {perf['success_rate']:.1f}% success | {perf['avg_latency_ms']:.0f}ms avg")
        except:
            st.warning("Could not load metrics")

    st.markdown("---")

    # Export conversation
    if st.button("💾 Export Conversation"):
        if st.session_state.messages:
            export_data = {
                "timestamp": datetime.now().isoformat(),
                "model": model_option,
                "messages": st.session_state.messages
            }
            
            st.download_button(
                "Download JSON",
                data=json.dumps(export_data, indent=2),
                file_name=f"rag_conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# Main chat interface
st.title("💬 Chat with Your Obsidian Vault")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Show sources if available
        if message["role"] == "assistant" and "sources" in message and show_sources:
            with st.expander("📚 Sources Used", expanded=False):
                for source in message["sources"]:
                    relevance = source.get("relevance", 0)
                    filename = source.get("filename", "unknown")
                    st.write(f"**{filename}** - {relevance:.0f}% relevant")

# Chat input
if prompt := st.chat_input("Ask about your notes..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate response
    with st.chat_message("assistant"):
        try:
            # Query vault
            with st.spinner(f"🔍 Searching vault ({retrieval_mode})..."):
                query_params = {
                    "query": prompt,
                    "n_results": num_sources,
                    "reranking": use_reranking,
                    "deduplicate": deduplicate,
                    "mode": retrieval_mode
                }

                if tag_filter:
                    query_params["filters"] = {"tags": tag_filter}

                vault_response = requests.post(
                    'http://localhost:8000/query',
                    json=query_params,
                    timeout=10
                )
                
                if vault_response.status_code != 200:
                    st.error("Failed to search vault")
                    st.stop()
                
                results = vault_response.json()
                documents = results.get('documents', [[]])[0]
                metadatas = results.get('metadatas', [[]])[0]
                distances = results.get('distances', [[]])[0]
                query_id = results.get('query_id')  # For feedback system

            if not documents:
                st.warning("No relevant notes found. Try a different query.")
                st.stop()
            
            # Build context
            context_parts = []
            sources_list = []
            
            for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                relevance = (1 - dist) * 100
                filename = meta.get('filename', 'unknown')
                filepath = meta.get('filepath', 'unknown')
                
                context_parts.append(f"Source {i} - {filename} ({relevance:.0f}% relevant):\n{doc}")
                sources_list.append({
                    "filename": filename,
                    "filepath": filepath,
                    "relevance": relevance
                })
            
            context_text = "\n\n---\n\n".join(context_parts)
            
            # Generate response with LLM
            with st.spinner(f"💭 Thinking with {model_option}..."):
                system_prompt = f"""You are an AI assistant helping Michel understand his Obsidian knowledge base.

Michel has:
- High-grade B-cell DLBCL (double-hit lymphoma)
- Completed Yescarta CAR-T therapy ~6 months ago
- 3-month post-Yescarta PET scan completed
- Upcoming 6-month PET scan this week
- Technical interests: 3D printing, Raspberry Pi, AI/ML, Fusion 360

Context from notes:
{context_text}

User question: {prompt}

Provide a thorough, compassionate answer that:
- References specific information from the notes
- Is medically accurate for his condition
- Includes technical details when relevant
- Is supportive and encouraging
- Cites which sources you used

Answer:"""

                ollama_response = requests.post(
                    'http://localhost:11434/api/generate',
                    json={
                        'model': model_option,
                        'prompt': system_prompt,
                        'stream': False,
                        'options': {
                            'temperature': temperature,
                            'num_ctx': 65536  # Use large context window
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
            if show_sources:
                with st.expander("📚 Sources Used", expanded=False):
                    for source in sources_list:
                        st.write(f"**{source['filename']}** - {source['relevance']:.0f}% relevant")
                        st.caption(source['filepath'])

            # Feedback buttons
            st.divider()
            st.markdown("**Was this answer helpful?**")
            feedback_cols = st.columns([1, 1, 1, 1, 1, 2])

            with feedback_cols[0]:
                if st.button("😞", key=f"bad_{query_id}", help="Not helpful"):
                    try:
                        requests.post(
                            'http://localhost:8000/feedback',
                            json={"query_id": query_id, "rating": 1},
                            timeout=5
                        )
                        st.success("Feedback saved!")
                    except:
                        st.warning("Could not save feedback")

            with feedback_cols[1]:
                if st.button("🙁", key=f"poor_{query_id}", help="Partially helpful"):
                    try:
                        requests.post(
                            'http://localhost:8000/feedback',
                            json={"query_id": query_id, "rating": 2},
                            timeout=5
                        )
                        st.success("Feedback saved!")
                    except:
                        st.warning("Could not save feedback")

            with feedback_cols[2]:
                if st.button("😐", key=f"ok_{query_id}", help="Somewhat helpful"):
                    try:
                        requests.post(
                            'http://localhost:8000/feedback',
                            json={"query_id": query_id, "rating": 3},
                            timeout=5
                        )
                        st.success("Feedback saved!")
                    except:
                        st.warning("Could not save feedback")

            with feedback_cols[3]:
                if st.button("😊", key=f"good_{query_id}", help="Helpful"):
                    try:
                        requests.post(
                            'http://localhost:8000/feedback',
                            json={"query_id": query_id, "rating": 4},
                            timeout=5
                        )
                        st.success("Feedback saved!")
                    except:
                        st.warning("Could not save feedback")

            with feedback_cols[4]:
                if st.button("😍", key=f"excellent_{query_id}", help="Very helpful"):
                    try:
                        requests.post(
                            'http://localhost:8000/feedback',
                            json={"query_id": query_id, "rating": 5},
                            timeout=5
                        )
                        st.success("Feedback saved!")
                    except:
                        st.warning("Could not save feedback")

            # Save to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": response_text,
                "sources": sources_list,
                "query_id": query_id
            })
        
        except requests.exceptions.Timeout:
            st.error("⏱️ Request timed out. Try a simpler query or reduce number of sources.")
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

# Footer
st.markdown("---")
st.caption("💡 Tip: Use specific keywords for better results. Your data never leaves your computer.")
