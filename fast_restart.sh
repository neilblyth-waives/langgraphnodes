#!/bin/bash
# Fastest restart - just restart container, no rebuild

echo "⚡ Fast Restart (no rebuild)..."

# Just restart the container
docker-compose restart backend

sleep 2

echo "✅ Container restarted"
echo ""
echo "📊 Status:"
docker-compose ps backend

echo ""
echo "🔗 API: http://localhost:8000"
echo "📝 Logs: docker-compose logs -f backend"

