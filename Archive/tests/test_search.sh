#!/bin/bash
# Simple search test script

echo "Testing semantic search..."
echo ""

curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "n_results": 3}' \
  2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    docs = data.get('documents', [[]])[0]
    meta = data.get('metadatas', [[]])[0]
    print('✅ Search working!')
    print(f'\nFound {len(docs)} results:\n')
    for i, (doc, m) in enumerate(zip(docs, meta), 1):
        print(f'{i}. {m.get(\"filename\", \"unknown\")}')
        print(f'   {doc[:100]}...\n')
except Exception as e:
    print(f'❌ Error: {e}')
"

