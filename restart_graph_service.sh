#!/bin/bash
# Quick script to restart graph service after updating .env

cd "$(dirname "${BASH_SOURCE[0]}")"

echo "🔄 Restarting graph-service to pick up new API key..."
docker-compose stop graph-service
docker-compose up -d graph-service

echo ""
echo "⏳ Waiting for service to start..."
sleep 5

echo ""
echo "🔍 Checking service health..."
curl -s http://localhost:8002/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8002/health

echo ""
echo "✅ Done! Try your query in the UI now."


