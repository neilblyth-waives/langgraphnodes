#!/bin/bash
# Quick test script for DV360 Multi-Agent System
# Tests basic connectivity without requiring Python dependencies

set -e

echo "=========================================="
echo "DV360 Multi-Agent System - Quick Test"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    echo "  Please install Docker or use the Python test script"
    exit 1
fi

echo -e "${BLUE}Checking Docker services...${NC}"

# Check if containers are running
BACKEND_RUNNING=$(docker ps --filter "name=dv360-backend" --format "{{.Names}}" | grep -q dv360-backend && echo "yes" || echo "no")
POSTGRES_RUNNING=$(docker ps --filter "name=dv360-postgres" --format "{{.Names}}" | grep -q dv360-postgres && echo "yes" || echo "no")

if [ "$BACKEND_RUNNING" = "no" ] || [ "$POSTGRES_RUNNING" = "no" ]; then
    echo -e "${YELLOW}⚠ Services not running. Starting services...${NC}"
    cd infrastructure
    docker-compose up -d
    echo "Waiting for services to start..."
    sleep 10
    cd ..
fi

echo ""
echo -e "${BLUE}Testing API endpoints...${NC}"

# Test root endpoint
echo -n "Testing root endpoint (/): "
if curl -s -f http://localhost:8000/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
    echo "  Backend may not be running. Try: cd infrastructure && docker-compose up -d"
fi

# Test health endpoint
echo -n "Testing health endpoint (/health): "
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health 2>/dev/null || echo "")
if [ -n "$HEALTH_RESPONSE" ]; then
    echo -e "${GREEN}✓ OK${NC}"
    echo "$HEALTH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$HEALTH_RESPONSE"
else
    echo -e "${RED}✗ FAILED${NC}"
fi

# Test liveness
echo -n "Testing liveness probe (/health/liveness): "
if curl -s -f http://localhost:8000/health/liveness > /dev/null 2>&1; then
    echo -e "${GREEN}✓ OK${NC}"
else
    echo -e "${RED}✗ FAILED${NC}"
fi

# Test readiness
echo -n "Testing readiness probe (/health/readiness): "
READINESS_RESPONSE=$(curl -s http://localhost:8000/health/readiness 2>/dev/null || echo "")
if [ -n "$READINESS_RESPONSE" ]; then
    echo -e "${GREEN}✓ OK${NC}"
    echo "$READINESS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$READINESS_RESPONSE"
else
    echo -e "${RED}✗ FAILED${NC}"
fi

echo ""
echo -e "${BLUE}Checking Docker containers...${NC}"

# Check container status
docker ps --filter "name=dv360-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | head -5

echo ""
echo -e "${BLUE}Checking database...${NC}"

# Test database connection
if docker exec dv360-postgres pg_isready -U dvdbowner -d dv360agent > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL is ready${NC}"
    
    # Check pgvector extension
    if docker exec dv360-postgres psql -U dvdbowner -d dv360agent -tAc "SELECT 1 FROM pg_extension WHERE extname='vector'" | grep -q 1; then
        echo -e "${GREEN}✓ pgvector extension installed${NC}"
    else
        echo -e "${YELLOW}⚠ pgvector extension not found${NC}"
        echo "  Run migrations: docker exec -it dv360-backend alembic upgrade head"
    fi
else
    echo -e "${RED}✗ PostgreSQL not ready${NC}"
fi

echo ""
echo -e "${BLUE}Summary${NC}"
echo "=========================================="
echo "For comprehensive testing, run:"
echo "  docker exec -it dv360-backend python test_setup.py"
echo ""
echo "Or view logs:"
echo "  docker logs dv360-backend"
echo "=========================================="

