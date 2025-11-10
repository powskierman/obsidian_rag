# GraphRAG 2.7.0 Setup Instructions for Claude Code Web VM

## Mission
Set up and run GraphRAG 2.7.0 indexing using local models in this cloud VM to process Obsidian vault files into a knowledge graph. Use NO external APIs - everything local to save costs.

## System Information
- **Target**: 1,607 Obsidian markdown files in vault
- **Models**: llama3.1:8b (LLM) + nomic-embed-text (embeddings)
- **GraphRAG Version**: 2.7.0 with LiteLLM support
- **Approach**: Fully local processing (zero API costs)

---

## Step 1: Environment Setup

### Install System Dependencies
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y curl wget python3 python3-pip python3-venv git build-essential

# Create working directory
mkdir -p ~/graphrag_workspace
cd ~/graphrag_workspace
```

### Install Ollama
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve &
sleep 10

# Verify Ollama is running
ps aux | grep ollama
```

### Download Required Models
```bash
# Download LLM model (this will take several minutes)
echo "Downloading llama3.1:8b model..."
ollama pull llama3.1:8b

# Download embedding model
echo "Downloading nomic-embed-text model..."
ollama pull nomic-embed-text

# Verify models are available
ollama list
```

---

## Step 2: Python Environment Setup

### Create Virtual Environment
```bash
# Create and activate virtual environment
python3 -m venv graphrag_env
source graphrag_env/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### Install GraphRAG and Dependencies
```bash
# Install GraphRAG 2.7.0 with LiteLLM support
pip install graphrag==2.7.0

# Install additional dependencies
pip install litellm requests pandas numpy

# Verify installation
python -c "import graphrag; print(f'GraphRAG version: {graphrag.__version__}')"
```

---

## Step 3: Configuration Setup

### Create GraphRAG Configuration
```bash
# Create main working directory
mkdir -p ~/graphrag_workspace/ragtest
cd ~/graphrag_workspace/ragtest

# Create necessary subdirectories
mkdir -p input output cache

# Create settings.yaml for local models
cat > settings.yaml << 'EOF'
encoding_model: cl100k_base
skip_workflows: []

llm:
  api_key: "ollama"
  type: openai_chat
  model: ollama/llama3.1:8b
  model_supports_json: true
  max_tokens: 4000
  request_timeout: 300.0
  api_base: http://localhost:11434/v1
  concurrent_requests: 2

parallelization:
  stagger: 0.5

async_mode: threaded

embeddings:
  async_mode: threaded
  llm:
    api_key: "ollama"
    type: openai_embedding
    model: ollama/nomic-embed-text
    api_base: http://localhost:11434/v1
    concurrent_requests: 2
    request_timeout: 180.0

chunks:
  size: 300
  overlap: 50
  group_by_columns: [id]

input:
  type: file
  file_type: text
  base_dir: "input"
  file_encoding: utf-8
  file_pattern: ".*\\.txt$"

cache:
  type: file
  base_dir: "cache"

storage:
  type: file
  base_dir: "output/${timestamp}/artifacts"

reporting:
  type: file
  base_dir: "output/${timestamp}/reports"

entity_extraction:
  prompt: "prompts/entity_extraction.txt"
  entity_types: [organization, person, geo, event, concept, technology, medical_condition, treatment, medication, procedure, symptom, diagnostic_test]
  max_gleanings: 1

summarize_descriptions:
  prompt: "prompts/summarize_descriptions.txt"
  max_length: 500

claim_extraction:
  enabled: true
  prompt: "prompts/claim_extraction.txt"
  description: "Any claims or facts that could be relevant to information discovery, research findings, or knowledge synthesis."
  max_gleanings: 1

community_report:
  prompt: "prompts/community_report.txt"
  max_length: 2000
  max_input_length: 8000

cluster_graph:
  max_cluster_size: 10

embed_graph:
  enabled: false

umap:
  enabled: false

snapshots:
  graphml: true
  raw_entities: true
  top_level_nodes: true

local_search:
  text_unit_prop: 0.5
  community_prop: 0.1
  conversation_history_max_turns: 5
  top_k_mapped_entities: 10
  top_k_relationships: 10
  max_tokens: 12000

global_search:
  max_tokens: 12000
  data_max_tokens: 12000
  map_max_tokens: 1000
  reduce_max_tokens: 2000
  concurrency: 2
EOF
```

---

## Step 4: Prepare Input Data

### Copy Vault Files
```bash
# Navigate to the repository directory (where vault is mounted)
cd ~/graphrag_workspace/ragtest

# Copy vault markdown files and convert to txt
echo "Converting vault files to text format..."
find /app/vault -name "*.md" -type f | head -20 | while read file; do
    base=$(basename "$file" .md)
    cp "$file" "input/${base}.txt"
done

# Count input files
echo "Input files prepared: $(ls input/*.txt | wc -l)"

# Show sample file
echo "Sample file content:"
head -10 input/*.txt | head -20
```

---

## Step 5: Run GraphRAG Indexing

### Test Ollama Connection
```bash
# Test Ollama API
curl -X POST http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "llama3.1:8b",
    "messages": [{"role": "user", "content": "Hello, respond with OK only."}],
    "max_tokens": 10
  }'

# Test embedding endpoint
curl -X POST http://localhost:11434/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nomic-embed-text",
    "input": "test text"
  }'
```

### Start GraphRAG Indexing
```bash
# Ensure we're in the right directory
cd ~/graphrag_workspace/ragtest

# Activate virtual environment
source ~/graphrag_workspace/graphrag_env/bin/activate

# Run GraphRAG indexing with verbose output
echo "Starting GraphRAG indexing..."
python -m graphrag index --root . --verbose

# Monitor progress
echo "Indexing started. Monitor the output above for progress..."
```

---

## Step 6: Verify Results

### Check Output Files
```bash
# List generated artifacts
echo "Generated artifacts:"
find output -name "*.parquet" -type f

# Show directory structure
echo "Output directory structure:"
tree output/ || ls -la output/

# Count entities and relationships
echo "Checking for key files:"
ls -la output/*/artifacts/ | grep -E "(entities|relationships|communities)"
```

### Create Test Query Script
```bash
cat > test_queries.py << 'EOF'
#!/usr/bin/env python3
"""
Test script to query the generated GraphRAG index
"""

import subprocess
import json
from pathlib import Path

def run_query(query, method="local"):
    """Run a GraphRAG query and return results"""
    try:
        cmd = [
            "python", "-m", "graphrag", "query",
            "--root", ".",
            "--method", method,
            query
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error: {result.stderr}"

    except Exception as e:
        return f"Exception: {str(e)}"

def main():
    """Run test queries"""

    # Check if index exists
    output_dirs = list(Path("output").glob("*/artifacts"))
    if not output_dirs:
        print("❌ No GraphRAG index found!")
        return

    print("✅ GraphRAG index found!")
    print(f"📁 Index location: {output_dirs[0]}")

    # Test queries
    test_queries = [
        "What are the main topics discussed in the documents?",
        "What are the key entities mentioned?",
        "Summarize the most important concepts",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n🔍 Test Query {i}: {query}")
        print("=" * 60)

        # Try local search
        result = run_query(query, "local")
        print("Local Search Result:")
        print(result[:500] + "..." if len(result) > 500 else result)

        print("-" * 40)

        # Try global search
        result = run_query(query, "global")
        print("Global Search Result:")
        print(result[:500] + "..." if len(result) > 500 else result)

        print("\n")

if __name__ == "__main__":
    main()
EOF

chmod +x test_queries.py
```

---

## Step 7: Run Tests

### Execute Test Queries
```bash
# Run test queries
cd ~/graphrag_workspace/ragtest
source ~/graphrag_workspace/graphrag_env/bin/activate

echo "Running test queries..."
python test_queries.py
```

### Generate Summary Report
```bash
cat > indexing_report.md << 'EOF'
# GraphRAG Indexing Report

## Environment
- **Date**: $(date)
- **GraphRAG Version**: 2.7.0
- **Models Used**: llama3.1:8b + nomic-embed-text
- **Processing Mode**: Fully local (no API costs)

## Input Statistics
- **Total Files**: $(ls input/*.txt | wc -l)
- **Total Size**: $(du -sh input/ | cut -f1)

## Output Statistics
- **Artifacts Generated**: $(find output -name "*.parquet" | wc -l)
- **Output Size**: $(du -sh output/ | cut -f1)
- **Processing Time**: See logs above

## Key Files Generated
$(ls -la output/*/artifacts/ | grep -E "(entities|relationships|communities)" || echo "Files still being generated...")

## Status
$(if [ -d "output" ] && [ "$(find output -name "*.parquet" | wc -l)" -gt 0 ]; then echo "✅ SUCCESS: GraphRAG indexing completed"; else echo "⏳ IN PROGRESS: Check logs for status"; fi)

## Next Steps
1. Download the output/ directory
2. Test queries with test_queries.py
3. Integrate with local setup if desired
4. Create pull request with results
EOF

echo "Report generated:"
cat indexing_report.md
```

---

## Expected Timeline
1. **Setup** (10-15 minutes): Environment, Ollama, models
2. **Configuration** (2-3 minutes): Settings and input prep
3. **Indexing** (30-90 minutes): Depends on file count and complexity
4. **Testing** (5 minutes): Verify results

## Success Criteria
- ✅ All input files processed
- ✅ Entities extracted and stored
- ✅ Relationships identified
- ✅ Communities detected
- ✅ Query system functional
- ✅ Zero API costs incurred

## If Issues Occur
1. Check Ollama service: `ps aux | grep ollama`
2. Verify models: `ollama list`
3. Check disk space: `df -h`
4. Monitor memory: `free -h`
5. Review logs for specific errors
6. Try smaller batch sizes if memory issues

---

## Final Notes
This setup uses only local models running in the VM, ensuring:
- No external API costs
- Complete data privacy
- Predictable resource usage
- Full control over the process

The entire operation should complete within your $250 Claude Code credit allocation.