#!/bin/bash
# Helper script to run vault_analyzer.py with the correct virtual environment

cd "$(dirname "$0")"
source venv/bin/activate
python Scripts/vault_analyzer.py "$@"

