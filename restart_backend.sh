#!/bin/bash
# Quick backend restart script

echo "🔄 Restarting backend..."

# Restart backend container
docker-compose restart backend

# Wait a moment
sleep 2

# Show status
echo ""
echo "📊 Backend status:"
docker-compose ps backend

echo ""
echo "📝 View logs: docker-compose logs -f backend"
echo "🔗 API: http://localhost:8000"

