#!/bin/bash
# Full script to rebuild and restart Docker containers with latest code

set -e  # Exit on error

echo "🛑 Stopping and removing old containers..."
docker-compose down

echo ""
echo "🗑️  Removing old images (to force rebuild)..."
docker-compose rm -f

echo ""
echo "🔨 Rebuilding containers (no cache)..."
docker-compose build --no-cache

echo ""
echo "🚀 Starting containers..."
docker-compose up -d

echo ""
echo "⏳ Waiting for services to start..."
sleep 5

echo ""
echo "✅ Checking if new version is running..."
echo ""

# Check version from API
VERSION=$(curl -s http://localhost:8000/ | python3 -c "import sys, json; print(json.load(sys.stdin).get('version', 'unknown'))" 2>/dev/null || echo "unknown")

if [ "$VERSION" = "2.0.0" ]; then
    echo "✓ Version 2.0.0 confirmed running!"
else
    echo "⚠ Warning: Version check returned: $VERSION"
    echo "   Expected: 2.0.0"
fi

echo ""
echo "📊 Container status:"
docker-compose ps

echo ""
echo "📋 Full API response:"
curl -s http://localhost:8000/ | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/

echo ""
echo "🔗 Services:"
echo "   - API: http://localhost:8000"
echo "   - Health: http://localhost:8000/api/health"
echo ""
echo "📝 View logs: docker-compose logs -f backend"

