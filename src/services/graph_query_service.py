"""
Flask service for Claude-powered knowledge graph queries
Runs alongside your existing embedding service in Docker
"""

from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import os
import re
import requests
import json
from kimi_graph_builder import GraphBuilder, GraphQuerier
import logging
from openai import OpenAI
import threading
import sys
from pathlib import Path

# Add necessary directories to sys.path for local vs Docker layouts
current_dir = Path(__file__).parent.resolve()
# Docker setup: services are in /app, utils are in /app/utils
# Local setup: services are in src/services, utils are in src/utils
potential_roots = [
    current_dir,           # Docker /app/
    current_dir.parent,    # /app/src/
    current_dir.parent.parent # Project Root
]

for pr in potential_roots:
    if pr.exists() and (pr / "utils").exists():
        if str(pr) not in sys.path:
            sys.path.insert(0, str(pr))
            break
    if pr.exists() and (pr / "src" / "utils").exists():
        src_path = str(pr / "src")
        if src_path not in sys.path:
            sys.path.insert(0, src_path)
            break

try:
    from utils.memory_manager import get_memory_manager
except ImportError as e:
    logger.error(f"Critical Import Error: {e}")
    # Fallback to direct import if possible
    try:
        from src.utils.memory_manager import get_memory_manager
    except ImportError:
        logger.error("All memory_manager import attempts failed.")
        def get_memory_manager(): return None

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global graph builder and querier
builder = None
querier = None
graph_loaded = False

# Environment variables for vector service
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://embedding-service:8000")
def extract_entities_from_graph(graph_text: str) -> list:
    """Extract key entities from graph response text."""
    # Extract capitalized phrases (likely entities)
    entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', graph_text)

    # Common words to filter out
    stopwords = {'The', 'This', 'That', 'These', 'Those', 'There', 'Here',
                 'When', 'Where', 'What', 'How', 'Why', 'Based', 'Your'}

    # Filter and deduplicate
    entities = [e for e in entities if e not in stopwords]
    entities = list(set(entities))[:10]  # Top 10 unique entities

    return entities


def generate_hyde_text(user_query: str, llm_provider: str, model: str) -> str:
    """Generate a hypothetical answer to improve vector search (HyDE)."""
    hyde_prompt = f"""You are a helpful assistant. Provide a concise, hypothetical but technically accurate answer to the following question. 
This answer will be used to help find relevant documents in a knowledge base.

Question: {user_query}

Hypothetical Answer:"""
    
    try:
        logger.info(f"Generating HyDE hypothetical answer for query: {user_query}")
        hyde_answer = call_llm(llm_provider, model, hyde_prompt, user_query, temperature=0.3)
        return hyde_answer
    except Exception as e:
        logger.error(f"HyDE generation failed: {e}")
        return user_query # Fallback to original query


def call_llm(provider: str, model: str, system_prompt: str, user_query: str, temperature: float = 0.7) -> str:
    """
    Call the specified LLM provider with the given prompt.

    Args:
        provider: 'ollama', 'claude', 'gemini', or 'gpt-oss'
        model: Model name (e.g., 'llama3.2', 'claude-sonnet-4-5-20250929', 'gemini-3-pro-preview')
        system_prompt: System prompt with context
        user_query: User's question
        temperature: Temperature for generation

    Returns:
        LLM response text
    """
    logger.info(f"Calling LLM: provider={provider}, model={model}")

    if provider == "claude":
        # Use Claude API via Anthropic
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=4000,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_query}]
        )
        return response.content[0].text

    elif provider == "gemini":
        # Use Gemini API via REST
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        # Combine system prompt and user query for Gemini
        full_prompt = f"{system_prompt}\n\nUser question: {user_query}\n\nAnswer:"

        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        gemini_response = requests.post(
            gemini_url,
            headers={
                "x-goog-api-key": api_key,
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
            raise ValueError(f"Gemini API error: {gemini_response.status_code} - {gemini_response.text}")

        result = gemini_response.json()
        candidates = result.get('candidates', [])
        if candidates and len(candidates) > 0:
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            if parts and len(parts) > 0:
                return parts[0].get('text', '')

        raise ValueError("Unexpected Gemini response format")

    elif provider == "gpt-oss":
        # Use OpenAI-compatible API (gpt-oss)
        llm_host = os.getenv("GPT_OSS_HOST", "http://host.docker.internal:12434/engines/llama.cpp")

        # Combine system prompt and user query
        full_prompt = f"{system_prompt}\n\nUser question: {user_query}\n\nAnswer:"

        llm_response = requests.post(
            f'{llm_host}/v1/chat/completions',
            json={
                'model': model,
                'messages': [
                    {'role': 'system', 'content': full_prompt}
                ],
                'max_tokens': 4096,
                'temperature': temperature
            },
            timeout=180
        )

        if llm_response.status_code != 200:
            raise ValueError(f"GPT-OSS API error: {llm_response.status_code} - {llm_response.text}")

        result = llm_response.json()
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']

        raise ValueError("Unexpected GPT-OSS response format")

    elif provider == "kimi":
        # Use OpenRouter for Kimi
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not configured")

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            temperature=temperature
        )
        return response.choices[0].message.content

    else:  # ollama (default)
        ollama_host = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")

        # Combine system prompt and user query for Ollama
        full_prompt = f"{system_prompt}\n\nUser question: {user_query}\n\nAnswer:"

        ollama_response = requests.post(
            f'{ollama_host}/api/generate',
            json={
                'model': model,
                'prompt': full_prompt,
                'stream': False,
                'options': {
                    'temperature': temperature
                }
            },
            timeout=180
        )

        if ollama_response.status_code != 200:
            raise ValueError(f"Ollama API error: {ollama_response.status_code} - {ollama_response.text}")

        result = ollama_response.json()
        return result.get('response', '')


def call_llm_stream(provider: str, model: str, system_prompt: str, user_query: str, temperature: float = 0.7):
    """
    Call the specified LLM provider with streaming enabled.

    Args:
        provider: 'ollama', 'claude', 'gemini', or 'gpt-oss'
        model: Model name
        system_prompt: System prompt with context
        user_query: User's question
        temperature: Temperature for generation

    Yields:
        Chunks of text from the LLM as they're generated
    """
    logger.info(f"Calling LLM with streaming: provider={provider}, model={model}")

    if provider == "claude":
        # Use Claude API with streaming
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")

        client = Anthropic(api_key=api_key)

        with client.messages.stream(
            model=model,
            max_tokens=4000,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_query}]
        ) as stream:
            for text in stream.text_stream:
                yield text

    elif provider == "ollama":
        # Use Ollama with streaming
        ollama_host = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")
        full_prompt = f"{system_prompt}\n\nUser question: {user_query}\n\nAnswer:"

        ollama_response = requests.post(
            f'{ollama_host}/api/generate',
            json={
                'model': model,
                'prompt': full_prompt,
                'stream': True,
                'options': {'temperature': temperature}
            },
            timeout=180,
            stream=True
        )

        if ollama_response.status_code != 200:
            raise ValueError(f"Ollama API error: {ollama_response.status_code}")

        # Stream the response
        for line in ollama_response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line)
                    if 'response' in chunk:
                        yield chunk['response']
                except json.JSONDecodeError:
                    continue

    elif provider == "gpt-oss":
        # Use OpenAI-compatible streaming
        llm_host = os.getenv("GPT_OSS_HOST", "http://host.docker.internal:12434/engines/llama.cpp")
        full_prompt = f"{system_prompt}\n\nUser question: {user_query}\n\nAnswer:"

        llm_response = requests.post(
            f'{llm_host}/v1/chat/completions',
            json={
                'model': model,
                'messages': [{'role': 'system', 'content': full_prompt}],
                'max_tokens': 4096,
                'temperature': temperature,
                'stream': True
            },
            timeout=180,
            stream=True
        )

        if llm_response.status_code != 200:
            raise ValueError(f"GPT-OSS API error: {llm_response.status_code}")

        # Stream the response
        for line in llm_response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    line_str = line_str[6:]
                    if line_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(line_str)
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            if 'content' in delta:
                                yield delta['content']
                    except json.JSONDecodeError:
                        continue

    elif provider == "gemini":
        # Gemini doesn't support streaming in the same way, fall back to non-streaming
        # but chunk the response for client-side streaming effect
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not configured")

        full_prompt = f"{system_prompt}\n\nUser question: {user_query}\n\nAnswer:"
        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

        gemini_response = requests.post(
            gemini_url,
            headers={
                "x-goog-api-key": api_key,
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
            raise ValueError(f"Gemini API error: {gemini_response.status_code}")

        result = gemini_response.json()
        candidates = result.get('candidates', [])
        if candidates and len(candidates) > 0:
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            if parts and len(parts) > 0:
                text = parts[0].get('text', '')
                # Chunk the response into words for streaming effect
                words = text.split(' ')
                for i, word in enumerate(words):
                    yield word + (' ' if i < len(words) - 1 else '')
        else:
            raise ValueError("Unexpected Gemini response format")


def initialize_graph(graph_path: str = None):
    """Initialize the knowledge graph"""
    global builder, querier, graph_loaded
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.error("OPENROUTER_API_KEY not set")
        return False
    
    try:
        builder = GraphBuilder(api_key=api_key)
        
        # If no path provided, try default locations
        if graph_path is None:
            graph_path = os.environ.get('GRAPH_PATH', '/app/graph_data/knowledge_graph_full.pkl')
        
        # Try multiple possible locations
        possible_paths = [
            graph_path,
            '/app/graph_data/knowledge_graph_full.pkl',
            '/app/graph_data/knowledge_graph_test.pkl',
            '/app/knowledge_graph_full.pkl',
            '/app/knowledge_graph_test.pkl'
        ]
        
        graph_file = None
        for path in possible_paths:
            if os.path.exists(path):
                graph_file = path
                break
        
        if graph_file:
            builder.load_graph(graph_file)
            querier = GraphQuerier(builder, api_key=api_key)
            graph_loaded = True
            logger.info(f"Graph loaded from {graph_file}: {builder.graph.number_of_nodes()} nodes, {builder.graph.number_of_edges()} edges")
            return True
        else:
            logger.warning(f"Graph file not found. Tried: {possible_paths}")
            return False
    except Exception as e:
        logger.error(f"Error loading graph: {e}")
        return False


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'graph_loaded': graph_loaded,
        'nodes': builder.graph.number_of_nodes() if graph_loaded else 0,
        'edges': builder.graph.number_of_edges() if graph_loaded else 0
    })


@app.route('/query', methods=['POST'])
def query_graph():
    """
    Unified query endpoint supporting vector, graph, and hybrid modes with LLM synthesis

    POST body:
    {
        "query": "What treatments are mentioned?",
        "mode": "vector" | "graph" | "hybrid",  // optional, default: "graph"
        "llm_provider": "ollama" | "claude" | "gemini" | "gpt-oss",  // optional, default: "ollama"
        "model": "llama3.2",  // optional, defaults based on provider
        "temperature": 0.7,  // optional
        "system_prompt": "Custom system instructions...",  // optional
        "max_entities": 20,  // optional, for graph mode
        "n_results": 10,  // optional, for vector/hybrid modes
        "web_search": false,  // optional, enables web search with Tavily
        "llm_knowledge": false,  // optional, adds complementary LLM insights
        "conversation_history": []  // optional, list of {role, content} messages
    }
    """
    try:
        data = request.json
        user_query = data.get('query', '')
        mode = data.get('mode', 'graph')
        llm_provider = data.get('llm_provider', 'ollama')
        model = data.get('model', '')
        temperature = data.get('temperature', 0.7)
        custom_system_prompt = data.get('system_prompt', '')
        max_entities = data.get('max_entities', 20)
        n_results = data.get('n_results', 10)
        web_search_enabled = data.get('web_search', False)
        llm_knowledge_enabled = data.get('llm_knowledge', False)
        conversation_history = data.get('conversation_history', [])

        if not user_query:
            return jsonify({'error': 'Query is required'}), 400

        # Set default models based on provider
        if not model:
            model_defaults = {
                'ollama': 'llama3.2',
                'claude': 'claude-sonnet-4-5-20250929',
                'gemini': 'gemini-3-pro-preview',
                'gpt-oss': 'gpt-4',
                'kimi': 'moonshotai/kimi-k2-0905'
            }
            model = model_defaults.get(llm_provider, 'llama3.2')

        # Handle vector mode: Vector search + LLM synthesis
        if mode == 'vector':
            try:
                # Get vector search results
                vector_response = requests.post(
                    f'{EMBEDDING_SERVICE_URL}/query',
                    json={
                        'query': user_query,
                        'n_results': n_results,
                        'reranking': True,
                        'deduplicate': True
                    },
                    timeout=60
                )

                if vector_response.status_code != 200:
                    return jsonify({'error': 'Vector search failed', 'mode': mode}), 503

                vector_data = vector_response.json()
                documents = vector_data.get('documents', [[]])[0]
                metadatas = vector_data.get('metadatas', [[]])[0]
                distances = vector_data.get('distances', [[]])[0]

                # Build context from vector results
                context_parts = []
                vector_sources = []

                for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                    # Calculate relevance
                    if dist < 0:
                        relevance = abs(dist) * 100
                    else:
                        relevance = (1 / (1 + dist)) * 100
                    relevance = min(100, max(0, relevance))

                    filename = meta.get('filename', 'unknown')
                    filepath = meta.get('filepath', 'unknown')
                    snippet = doc[:200] + "..." if len(doc) > 200 else doc

                    context_parts.append(f"Source {i} ({filename}):\n{doc}\n")
                    vector_sources.append({
                        'filename': filename,
                        'filepath': filepath,
                        'relevance': relevance,
                        'snippet': snippet
                    })

                context_text = "\n".join(context_parts)

                # Build system prompt
                if custom_system_prompt:
                    system_prompt = custom_system_prompt
                else:
                    system_prompt = f"""You are an AI assistant helping analyze an Obsidian knowledge base.

Context from notes:
{context_text}

Provide a thorough, accurate answer that:
- References specific information from the context
- Is medically accurate when discussing health topics
- Includes technical details when relevant
- Cites which sources you used
- If the context doesn't contain relevant information, say so clearly"""

                # Call LLM
                answer = call_llm(llm_provider, model, system_prompt, user_query, temperature)

                return jsonify({
                    'answer': answer,
                    'query': user_query,
                    'mode': mode,
                    'sources': vector_sources,
                    'llm_provider': llm_provider,
                    'model': model
                })

            except Exception as e:
                logger.error(f"Vector mode error: {e}")
                return jsonify({'error': str(e), 'mode': mode}), 500

        # Handle graph and hybrid modes
        else:
            if not graph_loaded:
                return jsonify({'error': 'Graph not loaded'}), 503

            # Step 1: Query the knowledge graph with custom system prompt
            logger.info(f"=== GRAPH QUERY DEBUG ===")
            logger.info(f"Query: {user_query}")
            logger.info(f"Mode: {mode}")
            logger.info(f"LLM Provider: {llm_provider}")
            logger.info(f"Model: {model}")
            logger.info(f"Max Entities: {max_entities}")
            logger.info(f"Custom System Prompt Present: {bool(custom_system_prompt)}")
            logger.info(f"Custom System Prompt (first 200 chars): {custom_system_prompt[:200] if custom_system_prompt else 'None'}")

            # Pass custom_system_prompt to graph query for personalized responses
            graph_answer, context_nodes = querier.query_with_llm(
                user_query,
                max_entities=max_entities,
                custom_system_prompt=custom_system_prompt
            )
            logger.info(f"Graph Answer (first 500 chars): {graph_answer[:500]}")

            # Extract entities directly from the context nodes used
            raw_entities = [node['entity'] for node in context_nodes if 'entity' in node]
            
            # Filter out dates (YYYY-MM-DD) and specific noise words
            import re
            date_pattern = re.compile(r'^\d{4}-\d{2}-\d{2}$')
            # Add specific terms user found irrelevant
            stopwords = {'Readwise', 'Source', 'Context', 'Key', 'Attached', 'Static', 'Unknown'}
            
            verified_entities = []
            for e in raw_entities:
                # Skip dates
                if date_pattern.match(e.strip()):
                    continue
                # Skip stopwords (case-insensitive check)
                if e.strip().title() in stopwords or e.strip() in stopwords:
                    continue
                # Skip short numeric artifacts
                if e.strip().isdigit() and len(e.strip()) < 4:
                    continue
                    
                verified_entities.append(e)
                
            # Deduplicate with case normalization preference
            # Prefer "ESP32" over "esp32", "IoT" over "iot" (heuristic: prefer more uppercase)
            normalized_map = {}
            for e in verified_entities:
                norm = e.lower()
                if norm not in normalized_map:
                    normalized_map[norm] = e
                else:
                    # If current entity has more uppercase letters than stored one, replace it
                    # e.g. "ESP32" (3 filtered upper) > "esp32" (0)
                    current_upper = sum(1 for c in e if c.isupper())
                    stored_upper = sum(1 for c in normalized_map[norm] if c.isupper())
                    if current_upper > stored_upper:
                        normalized_map[norm] = e
            
            entities = list(normalized_map.values())
            logger.info(f"Extracted {len(entities)} verified graph entities for visualization (filtered from {len(raw_entities)})")

            # Build base response
            base_response = {
                'answer': graph_answer,
                'query': user_query,
                'mode': mode,
                'extracted_entities': entities
            }

            # Pre-populate sources from graph context nodes as initial fallback
            graph_sources = []
            seen_source_files = set()
            for node in context_nodes:
                node_props = node.get('properties', {})
                # Our GraphBuilder adds 'sources' list to properties
                node_sources = node_props.get('sources', [])
                for src in node_sources:
                    fname = src.get('filename', 'Unknown')
                    if fname not in seen_source_files and fname != 'Unknown':
                        seen_source_files.add(fname)
                        graph_sources.append({
                            'filename': fname,
                            'filepath': fname,
                            'relevance': 85.0,
                            'snippet': f"Context: {node['entity']} mentioned. {node_props.get('description', '')}"
                        })
            base_response['sources'] = graph_sources

            # Step 2: If mode is 'hybrid', enhance with vector search
            if mode == 'hybrid':
                try:
                    # === STEP 2a: HyDE Enhancement ===
                    # Generate hypothetical answer for better vector retrieval
                    hyde_text = generate_hyde_text(user_query, llm_provider, model)
                    
                    # Search using both original query and hypothetical answer
                    enhanced_query = f"{user_query} {hyde_text} {' '.join(entities)}"

                    vector_response = requests.post(
                        f'{EMBEDDING_SERVICE_URL}/query',
                        json={
                            'query': enhanced_query,
                            'n_results': n_results,
                            'reranking': True,
                            'deduplicate': True
                        },
                        timeout=60
                    )

                    if vector_response.status_code == 200:
                        vector_data = vector_response.json()
                        documents = vector_data.get('documents', [[]])[0]
                        metadatas = vector_data.get('metadatas', [[]])[0]
                        distances = vector_data.get('distances', [[]])[0]

                        # Build vector context
                        vector_sources = []
                        context_parts = []
                        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                            # Calculate relevance
                            if dist < 0:
                                relevance = abs(dist) * 100
                            else:
                                relevance = (1 / (1 + dist)) * 100
                            relevance = min(100, max(0, relevance))

                            filename = meta.get('filename', 'unknown')
                            filepath = meta.get('filepath', 'unknown')
                            snippet = doc[:300] + "..." if len(doc) > 300 else doc
                            
                            doc_context = f"Source {i} ({filename}):\n{doc}\n"
                            context_parts.append(doc_context)

                            vector_sources.append({
                                'filename': filename,
                                'filepath': filepath,
                                'relevance': relevance,
                                'snippet': snippet
                            })

                        # Merge vector sources with graph fallbacks (prefer vector info for overlaps)
                        final_sources = vector_sources.copy()
                        vector_filenames = {s['filename'] for s in vector_sources}
                        for g_src in graph_sources:
                            if g_src['filename'] not in vector_filenames:
                                final_sources.append(g_src)
                        
                        base_response['sources'] = final_sources
                        base_response['extracted_entities'] = entities
                        
                        # SYNTHESIS STEP: Re-generate answer using both Graph and Vector context
                        logger.info("Synthesizing Hybrid Answer with Vector Context...")
                        vector_context_text = "\n".join(context_parts)
                        
                        # Prepare context strings
                        vault_context = f"=== GRAPH ANALYSIS ===\n{graph_answer}\n\n=== DOCUMENTS ===\n{vector_context_text}"
                        
                        # === STEP 2b: Personal Memory Integration ===
                        logger.info("Fetching Personal Memories from mem0...")
                        memory_manager = get_memory_manager()
                        memory_context = memory_manager.search_memory(user_query)
                        if not memory_context:
                            memory_context = "(No specific personal history found for this query)"
                        
                        synthesis_system_prompt = f"""Your task is to answer questions by analyzing the retrieved materials and Michel’s personal context.

### CONTEXT FROM MEMORY
{memory_context}

### RELEVANT NOTES FROM VAULT
{vault_context}

### USER QUESTION
{user_query}

When generating your answer:
1. Reference Michel’s specific **medical timeline** (DLBCL, Yescarta, scans) when relevant.
2. Incorporate insights from his **Obsidian notes**, citing which notes or sources you use.
3. Maintain a **compassionate and supportive** tone for medical topics.
4. Provide **technical depth** and precision for engineering and coding topics.
5. Adapt to his **expert-level understanding** — avoid overexplaining known concepts.
6. Be **concise but thorough**, focusing on clarity and reasoning.
7. Avoid redundant or generic phrasing.

Finally, provide your answer in a structured, easy-to-read format.

**Answer:**
"""
                        # Call LLM for final synthesis
                        final_answer = call_llm(llm_provider, model, synthesis_system_prompt, user_query, temperature)
                        base_response['answer'] = final_answer
                        
                        # === STEP 2c: Async Memory Update ===
                        def update_mem0():
                            try:
                                interaction = f"User asked: {user_query}\nAssistant answered: {final_answer}"
                                memory_manager.add_memory(interaction)
                                logger.info("mem0 personal memory updated successfully")
                            except Exception as ex:
                                logger.error(f"Failed to update mem0: {ex}")
                        
                        threading.Thread(target=update_mem0, daemon=True).start()
                        
                    else:
                        logger.warning(f"Vector search failed with status {vector_response.status_code}")
                        base_response['mode'] = 'graph'
                        base_response['warning'] = 'Vector search unavailable, returned graph-only result'

                except Exception as e:
                    logger.error(f"Hybrid search error: {e}")
                    base_response['mode'] = 'graph'
                    base_response['warning'] = f'Hybrid search failed: {str(e)}'

            # Step 3: If web search is requested, extract terms from combined context
            if web_search_enabled:
                try:
                    from tavily import TavilyClient

                    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
                    if TAVILY_API_KEY:
                        # Combine graph answer and vector sources for richer context
                        combined_context = graph_answer
                        if base_response.get('sources'):
                            # Add top 3 vector source snippets to context
                            top_sources = base_response['sources'][:3]
                            source_text = "\n\n".join([f"Source: {s['snippet']}" for s in top_sources])
                            combined_context = f"Graph Analysis:\n{graph_answer}\n\nVault Context:\n{source_text}"

                        # Extract specific medical/technical terms from combined context
                        search_terms_prompt = f"""Based on this combined knowledge, extract 4-6 specific medical terms, medications, procedures, measurements, or technical concepts that would find the most relevant and detailed clinical information on the web. Focus on:
- Specific medical conditions, diseases, or syndromes mentioned
- Medications, treatments, or procedures
- Technical measurements, biomarkers, or test results
- Specific medical entities (not general terms)

Context:
{combined_context[:1500]}

Provide only the search terms separated by spaces, no explanation or formatting."""

                        # Call OpenRouter with Kimi to extract search terms
                        from openai import OpenAI
                        client = OpenAI(
                            base_url="https://openrouter.ai/api/v1",
                            api_key=os.environ.get("OPENROUTER_API_KEY")
                        )

                        terms_response = client.chat.completions.create(
                            model="moonshotai/kimi-k2-0905",
                            messages=[{"role": "user", "content": search_terms_prompt}],
                            max_tokens=100
                        )
                        search_terms = terms_response.choices[0].message.content.strip()

                        logger.info(f"Web search terms extracted: {search_terms}")

                        # Perform web search with extracted terms
                        tavily = TavilyClient(api_key=TAVILY_API_KEY)
                        search_response = tavily.search(query=search_terms, search_depth="advanced", max_results=5)

                        if 'results' in search_response and search_response['results']:
                            web_results = []
                            for res in search_response['results'][:3]:
                                web_results.append({
                                    'title': res['title'],
                                    'url': res['url'],
                                    'content': res['content']
                                })

                            base_response['web_search'] = {
                                'search_terms': search_terms,
                                'results': web_results
                            }
                            logger.info(f"Web search returned {len(web_results)} results")
                        else:
                            base_response['web_search'] = {
                                'search_terms': search_terms,
                                'results': [],
                                'message': 'No web results found'
                            }
                            logger.warning("Web search returned no results")
                    else:
                        base_response['web_search'] = {
                            'error': 'TAVILY_API_KEY not configured'
                        }
                        logger.error("TAVILY_API_KEY not set")
                except ImportError:
                    base_response['web_search'] = {
                        'error': 'tavily-python not installed'
                    }
                    logger.error("tavily-python package not installed")
                except Exception as e:
                    logger.error(f"Web search error: {e}")
                    base_response['web_search'] = {
                        'error': str(e)
                    }

            # Step 4: If LLM knowledge is requested, get additional insights
            if llm_knowledge_enabled:
                try:
                    # Build knowledge prompt that complements the main answer
                    # Use custom system prompt if provided, otherwise use default
                    if custom_system_prompt:
                        knowledge_prompt = f"""{custom_system_prompt}

Based on the following information found in the user's vault:

{graph_answer[:2000]}

User's question: {user_query}

Provide ADDITIONAL insights, clinical context, or alternative perspectives that COMPLEMENT (not repeat) the vault information."""
                    else:
                        knowledge_prompt = f"""Based on the following information found in the user's vault:

{graph_answer[:2000]}

User's question: {user_query}

Provide ADDITIONAL insights, clinical context, or alternative perspectives that COMPLEMENT (not repeat) the vault information. Focus on:
1. Clinical implications of the findings
2. Treatment considerations mentioned
3. Additional context that would be helpful
4. Answering aspects of the question not covered by vault notes"""

                    # Call LLM for additional knowledge
                    llm_knowledge = call_llm(llm_provider, model, knowledge_prompt, user_query, temperature)
                    base_response['llm_knowledge'] = llm_knowledge
                    logger.info("LLM knowledge section generated")

                except Exception as e:
                    logger.error(f"LLM knowledge error: {e}")
                    base_response['llm_knowledge'] = {
                        'error': str(e)
                    }

            # Add response alias for researcher compatibility
            base_response['response'] = base_response.get('answer', '')
            return jsonify(base_response)

    except Exception as e:
        logger.error(f"Error processing query: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/query_stream', methods=['POST'])
def query_stream():
    """
    Streaming version of /query endpoint for real-time LLM responses.

    Accepts same parameters as /query but returns Server-Sent Events (SSE) stream.

    Request body:
    {
        "query": "What treatments are mentioned?",
        "mode": "vector" | "graph" | "hybrid",
        "llm_provider": "ollama" | "claude" | "gemini" | "gpt-oss",
        "model": "llama2",
        "temperature": 0.7,
        "system_prompt": "Custom instructions...",
        "n_results": 10,
        "stream": true  // Must be true for streaming
    }

    Returns: Server-Sent Events stream with JSON chunks
    """
    try:
        data = request.json
        user_query = data.get('query', '')
        mode = data.get('mode', 'vector')  # Default to vector for streaming
        llm_provider = data.get('llm_provider', 'ollama')
        model = data.get('model', '')
        temperature = data.get('temperature', 0.7)
        custom_system_prompt = data.get('system_prompt', '')
        n_results = data.get('n_results', 10)

        if not user_query:
            return jsonify({'error': 'Query is required'}), 400

        # Set default models
        if not model:
            model_defaults = {
                'ollama': 'llama2',
                'claude': 'claude-sonnet-4-5-20250929',
                'gemini': 'gemini-3-pro-preview',
                'gpt-oss': 'gpt-4'
            }
            model = model_defaults.get(llm_provider, 'llama2')

        def generate_stream():
            """Generator function for streaming response"""
            try:
                # Send metadata first
                yield f"data: {json.dumps({'type': 'metadata', 'mode': mode, 'provider': llm_provider, 'model': model})}\n\n"

                # Handle vector mode with streaming
                if mode == 'vector':
                    # Get vector search results
                    vector_response = requests.post(
                        f'{EMBEDDING_SERVICE_URL}/query',
                        json={
                            'query': user_query,
                            'n_results': n_results,
                            'reranking': True,
                            'deduplicate': True
                        },
                        timeout=30
                    )

                    if vector_response.status_code != 200:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Vector search failed'})}\n\n"
                        return

                    vector_data = vector_response.json()
                    documents = vector_data.get('documents', [[]])[0]
                    metadatas = vector_data.get('metadatas', [[]])[0]
                    distances = vector_data.get('distances', [[]])[0]

                    # Build context and sources
                    context_parts = []
                    vector_sources = []

                    for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                        relevance = (1 / (1 + abs(dist))) * 100 if dist < 0 else (1 / (1 + dist)) * 100
                        relevance = min(100, max(0, relevance))

                        filename = meta.get('filename', 'unknown')
                        filepath = meta.get('filepath', 'unknown')
                        snippet = doc[:200] + "..." if len(doc) > 200 else doc

                        context_parts.append(f"Source {i} ({filename}):\n{doc}\n")
                        vector_sources.append({
                            'filename': filename,
                            'filepath': filepath,
                            'relevance': relevance,
                            'snippet': snippet
                        })

                    # Send sources
                    yield f"data: {json.dumps({'type': 'sources', 'sources': vector_sources})}\n\n"

                    context_text = "\n".join(context_parts)

                    # Build system prompt
                    if custom_system_prompt:
                        system_prompt = custom_system_prompt
                    else:
                        system_prompt = f"""You are an AI assistant helping analyze an Obsidian knowledge base.

Context from notes:
{context_text}

Provide a thorough, accurate answer that:
- References specific information from the context
- Is medically accurate when discussing health topics
- Includes technical details when relevant
- Cites which sources you used
- If the context doesn't contain relevant information, say so clearly"""

                    # Stream LLM response
                    yield f"data: {json.dumps({'type': 'start'})}\n\n"

                    for chunk in call_llm_stream(llm_provider, model, system_prompt, user_query, temperature):
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

                elif mode == 'graph':
                    # Graph mode with streaming
                    if not graph_loaded:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Graph not loaded'})}\n\n"
                        return

                    # For graph mode, we can't stream the initial query result
                    # but we can send it in chunks
                    graph_answer = querier.query_with_llm(user_query, max_entities=20)

                    yield f"data: {json.dumps({'type': 'start'})}\n\n"

                    # Chunk the response for streaming effect
                    words = graph_answer.split(' ')
                    for i, word in enumerate(words):
                        chunk = word + (' ' if i < len(words) - 1 else '')
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

                elif mode == 'hybrid':
                    # Hybrid mode - similar to graph but with vector enhancement
                    if not graph_loaded:
                        yield f"data: {json.dumps({'type': 'error', 'message': 'Graph not loaded'})}\n\n"
                        return

                    # Get graph answer
                    graph_answer = querier.query_with_llm(user_query, max_entities=20)

                    # Extract entities and do vector search
                    entities = extract_entities_from_graph(graph_answer)
                    enhanced_query = f"{user_query} {' '.join(entities)}"

                    vector_response = requests.post(
                        f'{EMBEDDING_SERVICE_URL}/query',
                        json={
                            'query': enhanced_query,
                            'n_results': n_results,
                            'reranking': True,
                            'deduplicate': True
                        },
                        timeout=60
                    )

                    vector_sources = []
                    if vector_response.status_code == 200:
                        vector_data = vector_response.json()
                        documents = vector_data.get('documents', [[]])[0]
                        metadatas = vector_data.get('metadatas', [[]])[0]
                        distances = vector_data.get('distances', [[]])[0]

                        for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                            relevance = (1 / (1 + abs(dist))) * 100 if dist < 0 else (1 / (1 + dist)) * 100
                            vector_sources.append({
                                'filename': meta.get('filename', 'unknown'),
                                'filepath': meta.get('filepath', 'unknown'),
                                'relevance': min(100, max(0, relevance)),
                                'snippet': doc[:200] + "..." if len(doc) > 200 else doc
                            })

                    # Send sources and entities
                    yield f"data: {json.dumps({'type': 'sources', 'sources': vector_sources})}\n\n"
                    yield f"data: {json.dumps({'type': 'entities', 'entities': entities})}\n\n"

                    # Stream the answer
                    yield f"data: {json.dumps({'type': 'start'})}\n\n"

                    words = graph_answer.split(' ')
                    for i, word in enumerate(words):
                        chunk = word + (' ' if i < len(words) - 1 else '')
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    yield f"data: {json.dumps({'type': 'done'})}\n\n"

            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return Response(
            stream_with_context(generate_stream()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        logger.error(f"Error setting up stream: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/entity/<path:entity_name>', methods=['GET'])
def get_entity(entity_name: str):
    """Get information about a specific entity"""
    if not graph_loaded:
        return jsonify({'error': 'Graph not loaded'}), 503
    
    try:
        neighborhood = querier.get_entity_neighborhood(entity_name)
        return jsonify(neighborhood)
    except Exception as e:
        logger.error(f"Error getting entity: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/path', methods=['POST'])
def find_path():
    """
    Find paths between two entities
    
    POST body:
    {
        "source": "Entity 1",
        "target": "Entity 2",
        "max_depth": 3  // optional
    }
    """
    if not graph_loaded:
        return jsonify({'error': 'Graph not loaded'}), 503
    
    try:
        data = request.json
        source = data.get('source', '')
        target = data.get('target', '')
        max_depth = data.get('max_depth', 3)
        
        if not source or not target:
            return jsonify({'error': 'Both source and target are required'}), 400
        
        paths = querier.find_paths(source, target, max_depth)
        
        return jsonify({
            'source': source,
            'target': target,
            'paths': paths,
            'count': len(paths)
        })
    
    except Exception as e:
        logger.error(f"Error finding path: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/stats', methods=['GET'])
def get_stats():
    """Get graph statistics"""
    if not graph_loaded:
        return jsonify({'error': 'Graph not loaded'}), 503
    
    try:
        stats = querier.get_graph_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/search_entities', methods=['POST'])
def search_entities():
    """
    Search for entities by name
    
    POST body:
    {
        "query": "search term",
        "limit": 10  // optional
    }
    """
    if not graph_loaded:
        return jsonify({'error': 'Graph not loaded'}), 503
    
    try:
        data = request.json
        search_query = data.get('query', '').lower()
        limit = data.get('limit', 10)
        
        if not search_query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Search entities
        matching_entities = []
        for node in builder.graph.nodes():
            if search_query in node.lower():
                node_data = dict(builder.graph.nodes[node])
                matching_entities.append({
                    'name': node,
                    'type': node_data.get('entity_type', 'Unknown'),
                    'connections': builder.graph.degree(node)
                })
        
        # Sort by number of connections
        matching_entities.sort(key=lambda x: x['connections'], reverse=True)
        
        return jsonify({
            'query': search_query,
            'results': matching_entities[:limit],
            'total': len(matching_entities)
        })
    
    except Exception as e:
        logger.error(f"Error searching entities: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # Initialize graph on startup
    graph_path = os.environ.get('GRAPH_PATH')
    initialize_graph(graph_path)
    
    # Run Flask app
    port = int(os.environ.get('PORT', 8002))
    app.run(host='0.0.0.0', port=port, debug=False)
