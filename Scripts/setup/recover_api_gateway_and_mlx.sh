#!/bin/bash
# Backward-compatible wrapper for the provider-aware recovery helper.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/recover_local_llm_and_gateway.sh" "$@"
