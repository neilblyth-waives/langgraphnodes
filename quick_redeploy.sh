#!/bin/bash
# Fast redeploy - uses cache, only rebuilds if needed

set -e

echo "🚀 Quick Redeploy..."

# Stop containers (fast)
docker-compose stop backend

# Rebuild with cache (much faster than --no-cache)
echo "🔨 Rebuilding backend (using cache)..."
docker-compose build backend

# Start containers
echo "▶️  Starting containers..."
docker-compose up -d backend

# Wait briefly
sleep 3

# Quick version check
echo ""
echo "✅ Checking version..."
VERSION=$(curl -s http://localhost:8000/ 2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('version', 'unknown'))" 2>/dev/null || echo "checking...")

if [ "$VERSION" = "2.0.0" ]; then
    echo "✓ Version 2.0.0 confirmed!"
else
    echo "⚠ Version: $VERSION"
fi

echo ""
echo "📊 Container status:"
docker-compose ps backend

echo ""
echo "🔗 API: http://localhost:8000"
echo "📝 Logs: docker-compose logs -f backend"

