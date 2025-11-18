#!/usr/bin/env python3
"""
Claude-based Graph Reasoning
Uses Claude to perform semantic reasoning over vector search results
instead of using a separate graph service.
"""

import requests
import json
from pathlib import Path
from anthropic import Anthropic

# Load environment
try:
    from dotenv import load_dotenv
    env_file = Path('.env.local')
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

import os

# Initialize Anthropic client
client = Anthropic()

def search_vector_db(query: str, n_results: int = 10) -> dict:
    """
    Query the vector embedding service for similar documents

    Args:
        query: The search query
        n_results: Number of results to retrieve

    Returns:
        dict: Documents, metadata, and distances from embedding service
    """
    try:
        response = requests.post(
            'http://localhost:8000/query',
            json={
                'query': query,
                'n_results': n_results,
                'reranking': True,
                'deduplicate': True,
                'mode': 'vector'
            },
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            return {'error': f'Vector search failed: {response.status_code}'}
    except Exception as e:
        return {'error': f'Vector search error: {str(e)}'}


def reason_with_claude(query: str, documents: list, metadata: list) -> str:
    """
    Use Claude to perform semantic reasoning over retrieved documents

    Args:
        query: The original user query
        documents: List of retrieved document texts
        metadata: List of document metadata (filenames, etc)

    Returns:
        str: Claude's reasoned response
    """

    # Build context from documents
    context_parts = []
    for i, (doc, meta) in enumerate(zip(documents, metadata), 1):
        filename = meta.get('filename', 'unknown')
        relevance = (1 - meta.get('distance', 1)) * 100
        context_parts.append(
            f"Source {i} - {filename} ({relevance:.0f}% relevant):\n{doc}"
        )

    context_text = "\n\n---\n\n".join(context_parts)

    # Create Claude prompt for reasoning
    system_prompt = """You are an AI assistant helping to understand a personal knowledge base.

Your task is to:
1. Analyze the provided source documents
2. Identify key concepts, relationships, and patterns
3. Synthesize insights that answer the user's question
4. Draw connections between different sources when relevant
5. Provide a comprehensive, well-reasoned response

Be thorough but concise. Reference specific sources when appropriate."""

    user_message = f"""Question: {query}

Retrieved Sources:
{context_text}

Please analyze these sources and provide a comprehensive answer to the question above.
Consider relationships between the sources and provide synthesized insights."""

    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2000,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )

        return response.content[0].text
    except Exception as e:
        return f"Error during reasoning: {str(e)}"


def claude_graph_query(query: str, n_results: int = 10) -> dict:
    """
    Perform a graph-like query using Claude reasoning over vector search results

    This combines:
    - Vector semantic search (fast retrieval)
    - Claude reasoning (intelligent synthesis)

    Args:
        query: The search query
        n_results: Number of documents to retrieve and reason about

    Returns:
        dict: Contains reasoning result and source metadata
    """

    # Step 1: Retrieve relevant documents
    search_results = search_vector_db(query, n_results)

    if 'error' in search_results:
        return search_results

    documents = search_results.get('documents', [[]])[0]
    metadatas = search_results.get('metadatas', [[]])[0]
    distances = search_results.get('distances', [[]])[0]

    if not documents:
        return {
            'reasoning': 'No relevant documents found in your knowledge base.',
            'sources': [],
            'mode': 'claude-graph'
        }

    # Step 2: Use Claude to reason over the documents
    reasoning = reason_with_claude(query, documents, metadatas)

    # Step 3: Prepare sources with relevance scores
    sources = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        relevance = (1 - dist) * 100
        sources.append({
            'filename': meta.get('filename', 'unknown'),
            'filepath': meta.get('filepath', 'unknown'),
            'relevance': relevance,
            'chunk_id': meta.get('chunk_id', 0)
        })

    return {
        'reasoning': reasoning,
        'sources': sources,
        'mode': 'claude-graph',
        'num_sources': len(documents)
    }


if __name__ == '__main__':
    # Test the Claude graph reasoning
    test_query = "What are the key concepts in my knowledge base?"

    print("Testing Claude Graph Reasoning...")
    print(f"Query: {test_query}\n")

    result = claude_graph_query(test_query, n_results=5)

    if 'error' in result:
        print(f"Error: {result['error']}")
    else:
        print("Reasoning:")
        print(result['reasoning'])
        print(f"\n\nSources ({len(result['sources'])}):")
        for source in result['sources']:
            print(f"  - {source['filename']} ({source['relevance']:.0f}% relevant)")
