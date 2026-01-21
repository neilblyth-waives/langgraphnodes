#!/bin/bash
# Restart frontend only

echo "🔄 Restarting frontend..."

# Restart frontend
docker-compose restart frontend

# Wait a moment
sleep 2

# Show status
echo ""
echo "📊 Frontend status:"
docker-compose ps frontend

echo ""
echo "📝 View logs: docker-compose logs -f frontend"
echo "🔗 Frontend: http://localhost:3000"

