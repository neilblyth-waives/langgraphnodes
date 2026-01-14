# Testing Guide - DV360 Multi-Agent System

This guide shows you how to test the current setup of the DV360 Multi-Agent System.

## Quick Test (Recommended)

### Option 1: Using Docker (Easiest) ⭐ Recommended

**No virtual environment needed** - Docker provides isolation automatically.

If you have Docker running, this is the simplest way to test:

```bash
# 1. Start all services
cd infrastructure
docker-compose up -d

# 2. Wait for services to be healthy (about 30 seconds)
sleep 30

# 3. Run database migrations
docker exec -it dv360-backend alembic upgrade head

# 4. Test health endpoint
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "version": "0.1.0",
#   "checks": {
#     "database": true,
#     "redis": true
#   }
# }
```

### Option 2: Using Make Commands

```bash
# Start services
make start

# Run migrations
make migrate

# Check health
make health

# View logs
make logs-backend
```

### Option 3: Manual API Testing

Once services are running, test the endpoints:

```bash
# Root endpoint
curl http://localhost:8000/

# Health check
curl http://localhost:8000/health

# Liveness probe
curl http://localhost:8000/health/liveness

# Readiness probe
curl http://localhost:8000/health/readiness

# Prometheus metrics
curl http://localhost:8000/metrics
```

## Comprehensive Testing

### Using the Test Script

The test script (`test_setup.py`) can be run in two ways:

#### Inside Docker Container (Recommended)

```bash
# Copy test script to container
docker cp test_setup.py dv360-backend:/app/test_setup.py

# Run test script
docker exec -it dv360-backend python test_setup.py
```

#### Local Testing (Requires Dependencies)

**⚠️ Virtual environment required** when running locally (outside Docker):

```bash
# Install dependencies first
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run test script
cd ..
python test_setup.py
```

**Note:** If using Docker (recommended), you don't need a venv - Docker handles isolation.

## What Gets Tested

### 1. Configuration Loading ✅
- Environment variables
- Database configuration
- Redis configuration
- LLM API keys (OpenAI/Anthropic)
- Snowflake credentials
- Memory settings

### 2. Database Connection ✅
- PostgreSQL connectivity
- pgvector extension
- Health check

### 3. Redis Connection ✅
- Redis connectivity
- Health check

### 4. Core Components ✅
- VectorStore import
- SessionManager import
- SnowflakeTool import
- DecisionLogger import
- BaseAgent import

### 5. API Endpoints ✅
- Root endpoint (`/`)
- Health check (`/health`)
- Liveness probe (`/health/liveness`)
- Readiness probe (`/health/readiness`)
- Metrics endpoint (`/metrics`)

## Expected Test Results

### All Tests Passing ✅

```
✓ Configuration: PASSED
✓ Database: PASSED
✓ Redis: PASSED
✓ Components: PASSED
✓ API: PASSED

🎉 All tests passed! System is ready.
```

### Common Issues

#### Database Connection Failed

**Symptoms:**
```
✗ Database test failed: connection refused
```

**Solutions:**
1. Check if PostgreSQL is running:
   ```bash
   docker ps | grep postgres
   ```

2. Check PostgreSQL logs:
   ```bash
   docker logs dv360-postgres
   ```

3. Verify connection settings in `.env`:
   ```bash
   POSTGRES_HOST=postgres  # Use 'postgres' in Docker, 'localhost' locally
   POSTGRES_PORT=5432
   POSTGRES_DB=dv360agent
   POSTGRES_USER=dvdbowner
   POSTGRES_PASSWORD=dvagentlangchain
   ```

#### Redis Connection Failed

**Symptoms:**
```
✗ Redis test failed: connection refused
```

**Solutions:**
1. If using Redis Cloud (production):
   - Verify credentials in `.env`
   - Check Redis Cloud dashboard
   - Test connection manually:
     ```bash
     redis-cli -h redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com -p 10054 -a YOUR_PASSWORD ping
     ```

2. If using local Redis:
   ```bash
   # Start local Redis
   docker-compose --profile local-redis up -d redis
   ```

#### LLM API Keys Missing

**Symptoms:**
```
⚠ OpenAI API key not configured
⚠ Anthropic API key not configured
✗ LLM configuration: FAILED
```

**Solutions:**
1. Add API keys to `.env`:
   ```bash
   OPENAI_API_KEY=sk-your-key-here
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```

2. Restart backend:
   ```bash
   docker-compose restart backend
   ```

#### API Endpoints Not Responding

**Symptoms:**
```
⚠ Server not running at http://localhost:8000
```

**Solutions:**
1. Check if backend is running:
   ```bash
   docker ps | grep backend
   ```

2. Check backend logs:
   ```bash
   docker logs dv360-backend
   ```

3. Restart backend:
   ```bash
   docker-compose restart backend
   ```

## Testing Individual Components

### Test Database Directly

```bash
# Connect to PostgreSQL
docker exec -it dv360-postgres psql -U dvdbowner -d dv360agent

# Check pgvector extension
SELECT * FROM pg_extension WHERE extname='vector';

# Check tables
\dt

# Exit
\q
```

### Test Redis Directly

```bash
# Connect to Redis (local)
docker exec -it dv360-redis redis-cli

# Or Redis Cloud
redis-cli -h redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com -p 10054 -a YOUR_PASSWORD

# Test ping
PING

# Check keys
KEYS *

# Exit
exit
```

### Test Snowflake Connection

```bash
# Enter backend container
docker exec -it dv360-backend bash

# Run Python test
python -c "
from src.tools.snowflake_tool import SnowflakeTool
import asyncio

async def test():
    tool = SnowflakeTool()
    result = await tool.execute_query('SELECT 1 as test')
    print(result)

asyncio.run(test())
"
```

## Integration Testing

### Test Session Management

```bash
# Using curl
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "metadata": {"source": "test"}
  }'
```

### Test Vector Store

```bash
# Enter backend container
docker exec -it dv360-backend bash

# Run Python test
python -c "
from src.memory.vector_store import VectorStore
import asyncio

async def test():
    store = VectorStore()
    # Test storing a learning
    learning_id = await store.store_learning({
        'content': 'Test learning',
        'agent_name': 'test_agent',
        'learning_type': 'pattern',
        'confidence_score': 0.9
    })
    print(f'Stored learning: {learning_id}')

asyncio.run(test())
"
```

## Performance Testing

### Load Testing with Locust

```bash
# Start services
make start

# Run load test
cd backend/tests/load
locust -f load_test.py --host=http://localhost:8000

# Open browser: http://localhost:8089
# Configure: 100 users, 10 spawn rate
```

## Monitoring

### View Metrics

```bash
# Prometheus metrics
curl http://localhost:8000/metrics

# Or view in Prometheus UI
open http://localhost:9090
```

### View Logs

```bash
# All services
make logs

# Backend only
make logs-backend

# Specific service
docker logs -f dv360-backend
```

## Next Steps

Once all tests pass:

1. ✅ **Configuration**: Verify all settings in `.env`
2. ✅ **Database**: Run migrations (`make migrate`)
3. ✅ **Redis**: Verify connection
4. ✅ **LLM**: Test with a simple query
5. ✅ **Snowflake**: Test data queries
6. ⏳ **Agents**: Implement and test agents
7. ⏳ **API**: Implement chat endpoints
8. ⏳ **Memory**: Test learning storage and retrieval

## Troubleshooting

For more help, check:
- `README.md` - Quick start guide
- `spec.md` - Technical specification
- `docs/` - Additional documentation

