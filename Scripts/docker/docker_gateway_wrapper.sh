#!/bin/bash
# Wrapper script for Docker MCP Gateway for Claude Desktop
# Ensures proper PATH and environment for Claude Desktop

# Set PATH to include common Docker locations
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:$PATH"

# Find docker command
DOCKER_CMD=$(which docker 2>/dev/null || echo "/usr/local/bin/docker")

# Verify docker exists
if [ ! -x "$DOCKER_CMD" ]; then
    echo '{"jsonrpc":"2.0","id":1,"error":{"code":-32603,"message":"Docker not found. Please ensure Docker is installed and in PATH."}}' >&2
    exit 1
fi

# Run the gateway
# Gateway outputs config to stderr (fine), MCP protocol uses stdout
exec "$DOCKER_CMD" mcp gateway run

