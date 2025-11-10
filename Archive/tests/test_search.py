#!/usr/bin/env python3
import urllib.request
import json

def test_search():
    EMBEDDING_URL = 'http://localhost:8000'
    query = 'notes on rag'

    try:
        data = {
            'query': query,
            'n_results': 5,
            'reranking': True,
            'deduplicate': True
        }

        json_data = json.dumps(data).encode('utf-8')

        req = urllib.request.Request(
            f'{EMBEDDING_URL}/query',
            data=json_data,
            headers={'Content-Type': 'application/json'}
        )

        response = urllib.request.urlopen(req, timeout=30)

        if response.status == 200:
            results = json.loads(response.read())
            documents = results.get('documents', [[]])[0]
            metadatas = results.get('metadatas', [[]])[0]
            distances = results.get('distances', [[]])[0]

            print(f'Found {len(documents)} notes for "{query}":')
            for i, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                # Distance is cosine distance, so lower is better
                # Convert to similarity percentage (closer to 0 = more similar)
                similarity = max(0, (1 - dist) * 100)
                filename = meta.get('filename', 'unknown')
                print(f'{i}. {filename} (similarity: {similarity:.1f}%)')
                # Show a snippet of the content
                snippet = doc[:100] + '...' if len(doc) > 100 else doc
                print(f'   Content: {snippet}')
                print()
        else:
            print(f'Search failed: {response.status}')

    except Exception as e:
        print(f'Search error: {str(e)}')

if __name__ == '__main__':
    test_search()