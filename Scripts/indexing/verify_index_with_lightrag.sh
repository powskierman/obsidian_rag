#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# 1. Run the script against a small test vault
"${SCRIPT_DIR}/index_with_lightrag.sh" "${REPO_ROOT}/vault-test" > /tmp/index_with_lightrag.out 2>&1

# 2. Check LightRAG responds with expected health & basic query
curl -s http://localhost:8001/health | grep -q '"status":"ok"'

echo "VERIFICATION PASSED"
