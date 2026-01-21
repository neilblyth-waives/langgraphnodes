#!/bin/bash
# Restart both frontend and backend

echo "🔄 Restarting frontend and backend..."

# Restart both services
docker-compose restart backend frontend

# Wait a moment
sleep 3

# Show status
echo ""
echo "📊 Service status:"
docker-compose ps

echo ""
echo "📝 View logs:"
echo "   Backend:  docker-compose logs -f backend"
echo "   Frontend: docker-compose logs -f frontend"
echo ""
echo "🔗 URLs:"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3000"

