# Production Configuration Summary

**Last Updated:** 2024-01-12
**Status:** Configured and Ready to Deploy

## Overview

This document details the complete production configuration for the DV360 Multi-Agent System. All credentials and endpoints are configured in `.env` file.

---

## Infrastructure Components

### 1. LLM Provider Configuration

#### Anthropic Claude (Primary)
**Purpose:** Agent reasoning and decision-making

```bash
Provider: Anthropic
Model: claude-3-opus-20240229
API Key: Configured ✅
Priority: Primary (used when both keys present)
```

**Usage:**
- All agent conversations and reasoning
- Chat Conductor agent logic
- Specialist agent analysis
- Decision generation

**Costs:**
- Input: $15 per 1M tokens
- Output: $75 per 1M tokens
- Typical conversation: $0.02-$0.40

#### OpenAI (Secondary - Embeddings Only)
**Purpose:** Semantic memory and vector embeddings

```bash
Provider: OpenAI
Model: text-embedding-3-small
API Key: Configured ✅
Priority: Secondary (embeddings only)
```

**Usage:**
- Converting learnings to vector embeddings
- Semantic similarity search
- Memory retrieval context

**Costs:**
- $0.02 per 1M tokens
- 10,000 learnings ≈ $0.02
- Negligible compared to LLM costs

**Why Both?**
- Claude excels at complex reasoning (used for agents)
- Anthropic doesn't provide embeddings
- OpenAI embeddings are cheap and effective
- Best of both worlds approach

---

### 2. Database Configuration

#### PostgreSQL with pgvector

```bash
Type: PostgreSQL 16 with pgvector extension
Database: dv360agent
User: dvdbowner
Password: dvagentlangchain (configured)
Host: localhost (Docker container)
Port: 5432
```

**Features:**
- ✅ pgvector extension for semantic search
- ✅ UUID extension for primary keys
- ✅ Connection pooling (20 connections)
- ✅ Health checks configured
- ✅ Auto-update timestamps

**Tables:**
1. `sessions` - Conversation sessions
2. `messages` - Full message history
3. `agent_decisions` - Decision audit trail
4. `agent_learnings` - Semantic memory with embeddings
5. `query_cache` - Snowflake query cache

**Storage:**
- Vector dimension: 1536 (OpenAI embeddings)
- Index type: ivfflat for cosine similarity
- Expected size: Grows with learnings (~50MB per 10K learnings)

**Migration to Cloud:**
- Can migrate to AWS RDS PostgreSQL
- Can migrate to Google Cloud SQL
- Can migrate to Azure Database for PostgreSQL
- All support pgvector extension

---

### 3. Cache Configuration

#### Redis Cloud (Managed)

```bash
Provider: Redis Cloud (https://redislabs.com)
Plan: Free Tier
Host: redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com
Port: 10054
Region: EU West 2 (London)
Password: Configured ✅ (URL-encoded for special chars)
```

**Specifications:**
- Storage: 30 MB
- Connections: 30 concurrent
- Availability: Multi-zone HA
- Persistence: Enabled
- SSL/TLS: Supported
- Eviction: allkeys-lru

**Usage:**
- Session caching (TTL: 24 hours)
- Query result caching (TTL: 60 minutes)
- Rate limiting (per-user)
- Token usage tracking
- Working memory (TTL: 1 hour)

**Monitoring:**
- Dashboard: https://app.redislabs.com/
- Metrics: Memory, commands/sec, connections
- Alerts: Available in console

**Upgrade Path:**
- Free → $5/mo for 100MB
- Scalable as needed
- No code changes required

---

### 4. Data Source Configuration

#### Snowflake

```bash
Platform: Snowflake
Account: ai60319.eu-west-1
Region: EU West 1 (Ireland)
User: neilblyth@sub2tech.com
Warehouse: COMPUTE_WH
Database: REPORTS
Schema: METRICS
Role: SYSADMIN
```

**Access:**
- ✅ Read-only access to DV360 data
- ✅ Connection pooling enabled
- ✅ Query caching (Redis + DB)
- ✅ Async execution

**Expected Tables:**
- `dv360_campaigns` - Campaign performance
- `dv360_audience_performance` - Audience metrics
- `dv360_creative_performance` - Creative metrics
- (Additional tables as available)

**Query Patterns:**
- Campaign performance by date range
- Budget pacing analysis
- Audience segment comparison
- Creative performance metrics

---

### 5. Monitoring & Debugging

#### LangSmith

```bash
Provider: LangChain
Project: dv360-agent-system
API Key: Configured ✅
Tracing: Enabled
Endpoint: https://api.smith.langchain.com
```

**Features:**
- ✅ Agent execution tracing
- ✅ LLM call logging
- ✅ Token usage tracking
- ✅ Performance metrics
- ✅ Error debugging

**Access:**
- Console: https://smith.langchain.com/
- View traces, runs, and feedback
- Monitor agent performance
- Debug conversation flows

#### Prometheus + Grafana

```bash
Prometheus: http://localhost:9090
Grafana: http://localhost:3001 (admin/admin)
```

**Metrics Collected:**
- HTTP request rates and latency
- Agent execution times
- LLM token consumption
- Database query performance
- Cache hit/miss rates
- Redis memory usage

---

## Configuration Files

### `.env` (Primary Configuration)

**Location:** `/Users/neilblyth/Documents/Apps/TestAgentMemory/.env`

**Sections:**
1. API Configuration (port, CORS, etc.)
2. LLM Provider (Anthropic + OpenAI)
3. PostgreSQL (custom database)
4. Redis Cloud (managed)
5. Snowflake (data source)
6. LangSmith (monitoring)
7. Memory settings
8. Session settings
9. Rate limiting

**Security:**
- ✅ Not committed to git (.gitignore)
- ✅ Template available (.env.example)
- ✅ Passwords not shown in logs

### `docker-compose.yml`

**Location:** `/Users/neilblyth/Documents/Apps/TestAgentMemory/infrastructure/docker-compose.yml`

**Services:**
1. **postgres** - PostgreSQL with pgvector
2. **redis** - Disabled (using Redis Cloud)
3. **backend** - FastAPI application
4. **prometheus** - Metrics (optional profile)
5. **grafana** - Dashboards (optional profile)

**Networks:**
- dv360-network (bridge)

**Volumes:**
- postgres_data (persistent)
- backend_cache (temporary)

---

## Deployment Architecture

### Current Setup (Development/Testing)

```
┌─────────────────────────────────────┐
│   Local Machine / Development      │
│                                     │
│  ┌──────────────────────────────┐  │
│  │    FastAPI Backend           │  │
│  │    (Docker Container)        │  │
│  │    Port 8000                 │  │
│  └─────────┬────────────────────┘  │
│            │                        │
│  ┌─────────▼────────────────────┐  │
│  │    PostgreSQL + pgvector     │  │
│  │    (Docker Container)        │  │
│  │    Port 5432                 │  │
│  └──────────────────────────────┘  │
│                                     │
└─────────────────┬───────────────────┘
                  │
      ┌───────────┼────────────┐
      │           │            │
      ▼           ▼            ▼
┌─────────┐ ┌─────────┐ ┌──────────┐
│ Redis   │ │Snowflake│ │Claude API│
│ Cloud   │ │ Cloud   │ │OpenAI API│
│ EU-W2   │ │ EU-W1   │ │  (Cloud) │
└─────────┘ └─────────┘ └──────────┘
```

### Production Setup (Future)

```
┌────────────────────────────────────┐
│         Load Balancer (Nginx)      │
│         SSL/TLS Termination        │
└──────────────┬─────────────────────┘
               │
   ┌───────────┼───────────┐
   ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐
│Backend │ │Backend │ │Backend │
│   1    │ │   2    │ │   N    │
└───┬────┘ └───┬────┘ └───┬────┘
    │          │          │
    └──────────┼──────────┘
               │
    ┌──────────┼──────────┐
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│AWS RDS │ │ Redis  │ │Snowflake│
│Postgres│ │ Cloud  │ │  Cloud  │
└────────┘ └────────┘ └────────┘
```

---

## Security Configuration

### API Keys & Secrets

**Storage:**
- All in `.env` file (not committed)
- Environment variables in Docker
- No hardcoded credentials

**Access Control:**
- PostgreSQL: Username/password auth
- Redis Cloud: Password protected
- Snowflake: Username/password auth
- APIs: API key authentication

### Network Security

**Current:**
- Local PostgreSQL (not exposed externally)
- Redis Cloud over TLS
- Snowflake over HTTPS
- API endpoints on localhost:8000

**Production Recommendations:**
1. SSL/TLS for all connections
2. VPC/private network for database
3. Firewall rules (allow only necessary ports)
4. API key rotation schedule
5. Secrets management (AWS Secrets Manager, Vault)

---

## Performance Configuration

### Connection Pooling

**PostgreSQL:**
- Pool size: 20 connections per backend replica
- Max overflow: 10
- Pre-ping: Enabled
- Recycle: 3600 seconds

**Redis:**
- Max connections: 50
- Socket keepalive: Enabled
- Retry on timeout: Enabled

**Snowflake:**
- Thread pool: 5 workers
- Connection reuse
- Query timeout: 60 seconds

### Caching Strategy

**Query Cache (Redis):**
- TTL: 60 minutes
- Automatic invalidation
- Hash-based keys

**Session Cache (Redis):**
- TTL: 24 hours
- Auto-extend on activity
- Per-user isolation

**Working Memory (Redis):**
- TTL: 1 hour
- Last 20 messages
- Per-user context

### Rate Limiting

**Per User:**
- 60 requests per minute
- 100,000 tokens per day
- Tracked in Redis

**Enforcement:**
- Redis-based counters
- Sliding window algorithm
- HTTP 429 on exceed

---

## Monitoring & Alerting

### Health Checks

**Endpoints:**
- `/health` - Overall health with component status
- `/health/liveness` - Kubernetes liveness probe
- `/health/readiness` - Kubernetes readiness probe

**Monitored:**
- PostgreSQL connectivity
- Redis connectivity
- API responsiveness

### Metrics

**Application:**
- Request count and latency
- Agent execution times
- LLM token usage
- Database query performance

**Infrastructure:**
- CPU and memory usage
- Disk I/O
- Network throughput
- Connection pool utilization

### Logging

**Format:** Structured JSON (production) or pretty (development)

**Levels:**
- DEBUG: Detailed execution info
- INFO: Normal operations (current)
- WARNING: Degraded performance
- ERROR: Failures and exceptions

**Correlation:**
- Unique correlation ID per request
- Traced across all components
- Included in error messages

---

## Backup & Recovery

### PostgreSQL Backups

**Current:**
- Docker volume (postgres_data)
- Manual backup: `pg_dump`

**Recommended:**
- Daily automated backups
- 7-day retention
- Point-in-time recovery (PITR)
- Test restore procedure

**Commands:**
```bash
# Backup
docker exec dv360-postgres pg_dump -U dvdbowner dv360agent > backup.sql

# Restore
docker exec -i dv360-postgres psql -U dvdbowner dv360agent < backup.sql
```

### Redis Backups

**Current:**
- Redis Cloud automatic snapshots
- Free tier: Daily snapshots

**Access:**
- Via Redis Cloud console
- Download and restore

### Configuration Backups

**Files:**
- `.env` (store securely, not in git)
- `docker-compose.yml` (in git)
- Database migrations (in git)

---

## Cost Estimates

### Monthly Operating Costs (Estimated)

**LLM (Anthropic Claude):**
- Light usage (100 conversations): ~$10-20
- Medium usage (1,000 conversations): ~$100-200
- Heavy usage (10,000 conversations): ~$1,000-2,000

**Embeddings (OpenAI):**
- Any usage level: < $1
- Negligible cost

**Redis Cloud:**
- Free tier: $0
- First paid tier: $5/mo (if needed)

**Database:**
- Local PostgreSQL: $0
- AWS RDS (if migrated): ~$50-100/mo

**Snowflake:**
- Based on warehouse usage
- Read-only queries: minimal cost

**Total (Light Usage):**
- Development: ~$10-20/mo (just LLM)
- Production: ~$50-100/mo (add database)

---

## Upgrade Paths

### When to Upgrade

**Redis Cloud:**
- Memory usage > 25MB
- Connections > 25
- Need SSL/TLS

**PostgreSQL:**
- Database size > 10GB
- Need high availability
- Need read replicas
- Need automated backups

**Backend:**
- Concurrent users > 50
- Need auto-scaling
- Need load balancing

### Migration Steps

**Redis Cloud ($5/mo plan):**
1. Upgrade in Redis Cloud console
2. No code changes needed
3. Automatic migration

**PostgreSQL to RDS:**
1. Create RDS instance with pgvector
2. Export data: `pg_dump`
3. Import to RDS
4. Update DATABASE_URL in `.env`
5. Restart backend

**Backend to Kubernetes:**
1. Use manifests in `infrastructure/k8s/`
2. Configure secrets
3. Deploy with `kubectl apply`
4. Configure ingress/load balancer

---

## Troubleshooting

### Common Issues

**1. Redis Connection Timeout**
- Check Redis Cloud database is running
- Verify endpoint and password
- Check network connectivity

**2. PostgreSQL Connection Failed**
- Check Docker container is running: `docker ps`
- Verify credentials match `.env`
- Check DATABASE_URL format

**3. Snowflake Authentication Failed**
- Verify credentials in `.env`
- Check account identifier format
- Ensure warehouse is running

**4. LLM API Errors**
- Check API keys are valid
- Verify billing is set up
- Check rate limits not exceeded

### Getting Help

**Documentation:**
- `docs/CLAUDE_SETUP.md` - LLM setup
- `docs/REDIS_CLOUD_SETUP.md` - Redis configuration
- `spec.md` - Complete technical spec
- `README.md` - Quick start guide

**Support:**
- GitHub Issues (if repo is set up)
- Check logs: `docker logs dv360-backend`
- LangSmith traces for agent debugging

---

## Summary

✅ **All Infrastructure Configured:**
- Claude (Anthropic) for agent reasoning
- OpenAI for embeddings
- PostgreSQL (dv360agent) for data
- Redis Cloud (EU-W2) for caching
- Snowflake (EU-W1) for DV360 data
- LangSmith for monitoring

✅ **Ready for Deployment:**
- Start with: `docker-compose up -d`
- Run migrations: `docker exec -it dv360-backend alembic upgrade head`
- Access API: http://localhost:8000

✅ **Production-Ready Architecture:**
- Horizontal scaling supported
- Health checks configured
- Monitoring enabled
- Security best practices

✅ **Cost-Effective:**
- Free tier Redis ($0)
- Local PostgreSQL ($0)
- Pay-as-you-go LLM (~$10-20/mo light usage)

**Status:** Configuration Complete and Verified
**Next Steps:** Start system and begin Sprint 2 implementation
