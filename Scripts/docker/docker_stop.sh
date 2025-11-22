#!/bin/bash
# Stop Obsidian RAG Docker services

echo "🛑 Stopping Obsidian RAG Docker services..."
echo ""

docker-compose down

echo ""
echo "✅ All services stopped"
echo ""
echo "To remove volumes (data):  docker-compose down -v"
echo "To restart:                Scripts/docker/docker_start.sh"



