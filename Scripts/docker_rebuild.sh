#!/bin/bash
# Rebuild and restart Docker services

echo "🔄 Rebuilding Obsidian RAG Docker services..."
echo ""

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

echo ""
echo "🏗️ Rebuilding images (this may take a few minutes)..."
docker-compose build --no-cache

echo ""
echo "🚀 Starting services..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services..."
sleep 10

echo ""
echo "✅ Rebuild complete!"
echo ""
echo "📊 Check status: ./Scripts/docker_status.sh"
echo "🌐 Access UI:    http://localhost:8501"



