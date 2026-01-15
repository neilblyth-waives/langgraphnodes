#!/bin/bash
# Redeploy backend and frontend services

echo "🔨 Rebuilding backend..."
docker-compose build --no-cache backend

echo ""
echo "🚀 Starting services..."
docker-compose up -d backend frontend

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

echo ""
echo "✅ Checking health..."
curl -s http://localhost:8000/health/liveness | python3 -m json.tool

echo ""
echo "✅ Redeploy complete!"
echo "Backend: http://localhost:8000"
echo "Frontend: http://localhost:3000"

