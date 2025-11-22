#!/bin/bash
# Wrapper script to ensure venv is activated

cd "$(dirname "$0")"

# Activate venv
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "❌ venv directory not found"
    exit 1
fi

# Check if API key is set
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ ANTHROPIC_API_KEY environment variable not set"
    echo ""
    echo "Please set it with:"
    echo '  export ANTHROPIC_API_KEY="sk-ant-..."'
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Run the Python script
python run_test_mode.py

