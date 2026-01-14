#!/bin/bash

# Quick Start Script for DV360 Multi-Agent System

set -e

echo "========================================="
echo "DV360 Multi-Agent System - Quick Start"
echo "========================================="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📝 Setting up environment..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env and add your credentials:"
    echo "   - OPENAI_API_KEY or ANTHROPIC_API_KEY"
    echo "   - SNOWFLAKE_* credentials"
    echo ""
    read -p "Press Enter after updating .env to continue..."
fi

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "🚀 Starting services..."
cd infrastructure
docker-compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
echo "🏥 Checking service health..."
if curl -f -s http://localhost:8000/health/liveness > /dev/null 2>&1; then
    echo "✅ Backend is running"
else
    echo "⏳ Backend is starting... (this may take a minute)"
    for i in {1..30}; do
        sleep 2
        if curl -f -s http://localhost:8000/health/liveness > /dev/null 2>&1; then
            echo "✅ Backend is running"
            break
        fi
        echo -n "."
    done
fi

echo ""
echo "📊 Running database migrations..."
docker exec dv360-backend alembic upgrade head

echo ""
echo "========================================="
echo "✅ System is ready!"
echo "========================================="
echo ""
echo "Access Points:"
echo "  🌐 API:        http://localhost:8000"
echo "  📚 API Docs:   http://localhost:8000/docs"
echo "  ❤️  Health:     http://localhost:8000/health"
echo "  📈 Prometheus: http://localhost:9090"
echo "  📊 Grafana:    http://localhost:3001 (admin/admin)"
echo ""
echo "Useful Commands:"
echo "  make logs          - View logs"
echo "  make logs-backend  - View backend logs only"
echo "  make stop          - Stop services"
echo "  make shell         - Open backend shell"
echo "  make db-shell      - Open database shell"
echo ""
echo "Next Steps:"
echo "  1. Check API docs: http://localhost:8000/docs"
echo "  2. Test health endpoint: curl http://localhost:8000/health"
echo "  3. View logs: make logs-backend"
echo ""
