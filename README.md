# DV360 Multi-Agent System

An AI-powered DV360 strategy and analysis platform built with LangGraph. This system provides read-only analysis and recommendations from Snowflake data, with persistent memory across sessions.

## Architecture

```
Chat Conductor Agent (Supervisor)
    ├── Performance Diagnosis Agent
    ├── Budget & Pacing Agent
    ├── Audience & Targeting Agent
    └── Creative & Inventory Agent

Tools: Snowflake, Seasonality Context, Memory Retrieval, Decision Logging
Storage: PostgreSQL (pgvector), Redis, Snowflake
```

## Features

- **Multi-Agent System**: Specialized agents for different DV360 analysis domains
- **Persistent Memory**: Growing intelligence with semantic search using pgvector
- **Session Management**: Continue conversations across multiple sessions
- **Decision Tracking**: Full audit trail of all agent decisions
- **Scalable Architecture**: Horizontal scaling with stateless backend
- **Production-Ready**: Docker Compose with load balancing and monitoring

## Tech Stack

- **Framework**: LangGraph, LangChain, FastAPI
- **Database**: PostgreSQL with pgvector extension
- **Cache**: Redis
- **Data Source**: Snowflake
- **Observability**: Prometheus, Grafana, Structlog
- **Deployment**: Docker, Docker Compose, Kubernetes-ready

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- OpenAI or Anthropic API key
- Snowflake account credentials

## Quick Start

### 1. Clone and Setup

```bash
cd /path/to/project
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` file with your credentials:

```bash
# RECOMMENDED: Use Claude for reasoning + OpenAI for embeddings
# See docs/CLAUDE_SETUP.md for detailed setup guide

# Anthropic Claude (agent reasoning)
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-3-opus-20240229

# OpenAI (embeddings only - required for semantic memory)
OPENAI_API_KEY=sk-your-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Snowflake (required)
SNOWFLAKE_ACCOUNT=your_account.region
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_SCHEMA=your_schema

# Redis Cloud (configured)
REDIS_HOST=redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com
REDIS_PORT=10054
REDIS_PASSWORD=your_redis_password_here
```

**📖 Documentation:**
- **LLM Setup**: [docs/CLAUDE_SETUP.md](docs/CLAUDE_SETUP.md) - Claude + OpenAI configuration
- **Redis Cloud**: [docs/REDIS_CLOUD_SETUP.md](docs/REDIS_CLOUD_SETUP.md) - Redis Cloud setup
- **Production Config**: [docs/PRODUCTION_CONFIG.md](docs/PRODUCTION_CONFIG.md) - Complete configuration reference
- **Technical Spec**: [spec.md](spec.md) - Full system specification

### 3. Start Services

```bash
cd infrastructure

# Development mode (single backend instance)
docker-compose up -d

# Production mode (3 backend replicas with load balancer)
docker-compose -f docker-compose.prod.yml up -d

# Scale to more replicas
docker-compose -f docker-compose.prod.yml up -d --scale backend=5
```

### 4. Run Database Migrations

```bash
# Enter backend container
docker exec -it dv360-backend bash

# Run migrations
alembic upgrade head

# Exit container
exit
```

### 5. Verify Services

Check all services are healthy:

```bash
# Health check
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

Access services:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3001 (admin/admin)

## Development

### Local Setup (without Docker)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp ../.env.example ../.env
# Edit .env with your credentials

# Run PostgreSQL and Redis locally or via Docker
docker-compose up -d postgres redis

# Run migrations
alembic upgrade head

# Start development server
python -m src.api.main
```

### Running Tests

```bash
# Unit tests
pytest backend/tests/unit

# Integration tests
pytest backend/tests/integration

# Load tests
cd backend/tests/load
locust -f load_test.py
```

## Project Structure

```
dv360-agent-system/
├── backend/
│   ├── src/
│   │   ├── agents/          # Agent implementations
│   │   ├── tools/           # Snowflake, memory, seasonality tools
│   │   ├── memory/          # Memory management
│   │   ├── api/             # FastAPI routes
│   │   ├── core/            # Config, database, cache, telemetry
│   │   └── schemas/         # Pydantic schemas
│   ├── tests/               # Unit, integration, load tests
│   ├── alembic/             # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── infrastructure/
│   ├── docker-compose.yml       # Development
│   ├── docker-compose.prod.yml  # Production-like
│   ├── nginx.conf               # Load balancer config
│   └── k8s/                     # Kubernetes manifests
├── docs/                    # Documentation
├── .env.example            # Environment template
└── README.md
```

## API Usage

### Chat with Agent

```bash
# Send message (placeholder - will be implemented in Sprint 2)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "optional-session-id",
    "message": "How is campaign XYZ performing?"
  }'
```

### Session Management

```bash
# List sessions (placeholder)
curl http://localhost:8000/api/sessions

# Get session history (placeholder)
curl http://localhost:8000/api/sessions/{session_id}
```

## Configuration

### Environment Variables

Key configuration options in `.env`:

```bash
# LLM Provider
OPENAI_API_KEY=          # OpenAI API key
ANTHROPIC_API_KEY=       # Anthropic API key

# Database
POSTGRES_PASSWORD=       # PostgreSQL password
DATABASE_URL=           # Auto-generated

# Redis
REDIS_URL=              # Auto-generated

# Snowflake
SNOWFLAKE_*=            # All Snowflake connection details

# Memory
VECTOR_DIMENSION=1536   # Embedding dimension
MEMORY_TOP_K=5          # Memories to retrieve

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_TOKENS_PER_DAY=100000

# Logging
LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR
```

## Monitoring

### Prometheus Metrics

Available at `http://localhost:9090`:

- `http_requests_total` - Total HTTP requests
- `agent_executions_total` - Agent execution counts
- `llm_tokens_used` - LLM token consumption
- `db_query_duration_seconds` - Database performance

### Grafana Dashboards

Access at `http://localhost:3001` (admin/admin):

1. Add Prometheus data source: `http://prometheus:9090`
2. Import dashboards for API metrics, agent performance, LLM usage

### Logs

View structured logs:

```bash
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Specific service
docker logs -f dv360-backend
```

## Scaling

### Horizontal Scaling

Scale backend replicas:

```bash
# Scale to 5 replicas
docker-compose -f docker-compose.prod.yml up -d --scale backend=5

# Nginx automatically load balances across all replicas
```

### Load Testing

```bash
cd backend/tests/load

# Run load test
locust -f load_test.py --host=http://localhost:8000

# Open browser: http://localhost:8089
# Configure: 100 users, 10 spawn rate
```

## Database Management

### Migrations

```bash
# Create new migration
docker exec -it dv360-backend alembic revision -m "description"

# Run migrations
docker exec -it dv360-backend alembic upgrade head

# Rollback one migration
docker exec -it dv360-backend alembic downgrade -1

# Show current version
docker exec -it dv360-backend alembic current
```

### Backup & Restore

```bash
# Backup database
docker exec dv360-postgres pg_dump -U dv360_user dv360_agents > backup.sql

# Restore database
docker exec -i dv360-postgres psql -U dv360_user dv360_agents < backup.sql
```

## Troubleshooting

### Services Won't Start

```bash
# Check service logs
docker-compose logs

# Rebuild images
docker-compose build --no-cache
docker-compose up -d
```

### Database Connection Errors

```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check PostgreSQL logs
docker-compose logs postgres

# Verify pgvector extension
docker exec -it dv360-postgres psql -U dv360_user -d dv360_agents -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

### Redis Connection Errors

```bash
# Check Redis is running
docker-compose ps redis

# Test Redis connection
docker exec -it dv360-redis redis-cli ping
```

## Current Status

**Sprint 1 Complete**: Foundation infrastructure
- ✅ Project structure
- ✅ Core configuration management
- ✅ Database connections (PostgreSQL + pgvector)
- ✅ Redis caching
- ✅ FastAPI app with health checks
- ✅ Docker Compose (dev + prod)
- ✅ Monitoring setup (Prometheus, Grafana)
- ✅ Database schema migrations

**Sprint 2 (50% Complete)** - Core Agents & Memory
- ✅ Pydantic schemas (agent, chat, memory)
- ✅ Base agent class with LangGraph
- ✅ Decision logger tool
- ✅ Snowflake tool with query templates
- ✅ Vector store (semantic memory)
- ✅ Session manager
- ⏳ Memory retrieval tool
- ⏳ Performance Diagnosis Agent
- ⏳ Chat Conductor Agent
- ⏳ Chat API endpoints
- ⏳ Session API endpoints

## Deployed Configuration

**Infrastructure:**
- **LLM**: Claude 3 Opus (Anthropic) for reasoning + OpenAI for embeddings
- **Database**: PostgreSQL 16 with pgvector (dv360agent)
- **Cache**: Redis Cloud EU-W2 (30MB free tier)
- **Data**: Snowflake EU-W1 (REPORTS.METRICS)
- **Monitoring**: LangSmith enabled

**Services Running:**
- Backend API: http://localhost:8000
- PostgreSQL: localhost:5432 (Docker)
- Redis: redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com:10054
- Prometheus: http://localhost:9090 (optional)
- Grafana: http://localhost:3001 (optional)

**Ready for:**
- Agent implementation
- API endpoint development
- End-to-end testing
- Production deployment

See [docs/PRODUCTION_CONFIG.md](docs/PRODUCTION_CONFIG.md) for complete details.

## Contributing

This is a production system. Follow these guidelines:

1. Create feature branches
2. Write tests for new code
3. Update documentation
4. Run load tests before major changes
5. Review Prometheus metrics after deployment

## License

[Your License Here]

## Support

For issues and questions:
- GitHub Issues: [your-repo-url]
- Documentation: `docs/`
- Architecture: See `docs/architecture.md`
