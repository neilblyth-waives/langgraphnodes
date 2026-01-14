# Redis Cloud Setup Guide

## Overview

You're using **Redis Cloud (free tier)** instead of running Redis locally in Docker. This is recommended for production-like testing and easier management.

**Your Redis Endpoint:**
```
redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com:10054
```

## Step 1: Get Your Redis Password

### From Redis Cloud Console

1. Go to https://app.redislabs.com/
2. Sign in to your account
3. Click on your database (should show your endpoint)
4. Look for **"Default user password"** or **"Security"** section
5. Copy the password (it's usually a long random string)

### Alternative: From Email

When you created your Redis Cloud database, you should have received an email with:
- Endpoint (you already have this)
- Port (10054)
- Password

## Step 2: Update Your .env File

```bash
# Copy the example
cp .env.example .env

# Edit .env
nano .env  # or your preferred editor
```

### Add These Lines:

```bash
# Redis Cloud Configuration
REDIS_HOST=redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com
REDIS_PORT=10054
REDIS_DB=0
REDIS_PASSWORD=YOUR_ACTUAL_PASSWORD_HERE

# Full connection URL (update password)
REDIS_URL=redis://default:YOUR_ACTUAL_PASSWORD_HERE@redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com:10054/0
```

**Important:** Replace `YOUR_ACTUAL_PASSWORD_HERE` with your actual Redis password!

## Step 3: Update Docker Compose

The `docker-compose.yml` has already been configured to:
- Skip starting local Redis
- Use environment variables from `.env`
- Connect to your Redis Cloud instance

## Step 4: Test Connection

### Start the System

```bash
cd infrastructure
docker-compose up -d
```

The local Redis service won't start (it's in a profile now), and the backend will connect to your Redis Cloud instance.

### Verify Connection

```bash
# Check backend logs
docker logs dv360-backend | grep -i redis

# You should see:
# ✓ Redis initialized: redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com:10054
```

### Test Redis Commands

```bash
# Install redis-cli if not installed
# On Mac: brew install redis
# On Ubuntu: apt install redis-tools

# Test connection
redis-cli -h redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com \
          -p 10054 \
          -a YOUR_PASSWORD_HERE \
          PING

# Should return: PONG
```

### Test from Backend

```bash
# Enter backend container
docker exec -it dv360-backend python

# In Python:
>>> from src.core.cache import check_redis_health
>>> import asyncio
>>> asyncio.run(check_redis_health())
True  # Should return True
```

## Configuration Details

### Connection String Format

```
redis://[username]:[password]@[host]:[port]/[db]
```

For Redis Cloud:
```
redis://default:your_password@redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com:10054/0
```

**Parts:**
- `default` - Default Redis username (Redis Cloud uses this)
- `your_password` - Your Redis Cloud password
- `redis-10054...` - Your Redis Cloud host
- `10054` - Your Redis Cloud port
- `0` - Database number (0 is default)

### Environment Variables

The system reads these from `.env`:

```bash
REDIS_HOST=redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com
REDIS_PORT=10054
REDIS_DB=0
REDIS_PASSWORD=your_password
```

These are automatically used by:
- `backend/src/core/config.py` - Configuration
- `backend/src/core/cache.py` - Redis client
- All caching operations

## What Redis Is Used For

### 1. Session Cache
- Active conversation sessions
- Automatic TTL (24 hours default)
- Fast access to session data

### 2. Query Cache
- Snowflake query results
- Reduces database load
- TTL: 60 minutes (configurable)

### 3. Rate Limiting
- Per-user request limits
- Token usage tracking
- Prevents abuse

### 4. Working Memory
- Short-term context (1 hour)
- Recent messages across sessions
- Fast retrieval

## Redis Cloud Free Tier Limits

**Your Free Plan Includes:**
- **30 MB** storage
- **30 connections**
- **High availability** (multi-zone)
- **Data persistence**
- **SSL/TLS** encryption

**Sufficient for:**
- Development
- Testing
- Small production deployments (< 50 users)

## Monitoring Usage

### Via Redis Cloud Console

1. Go to https://app.redislabs.com/
2. Click your database
3. View metrics:
   - Memory usage
   - Commands per second
   - Connected clients
   - Hit rate

### Via Application

```bash
# Check Redis info
docker exec -it dv360-backend python

>>> from src.core.cache import get_redis
>>> import asyncio
>>> redis = asyncio.run(get_redis())
>>> info = asyncio.run(redis.info())
>>> print(f"Memory used: {info['used_memory_human']}")
>>> print(f"Connected clients: {info['connected_clients']}")
```

## Troubleshooting

### Connection Timeout

**Error:** `TimeoutError: connect timeout`

**Causes:**
1. Wrong host/port
2. Firewall blocking connection
3. Redis Cloud database not running

**Solutions:**
1. Verify endpoint in Redis Cloud console
2. Check firewall rules
3. Restart Redis Cloud database if needed

### Authentication Failed

**Error:** `NOAUTH Authentication required` or `ERR invalid password`

**Causes:**
1. Wrong password
2. Missing password in connection string

**Solutions:**
1. Get correct password from Redis Cloud console
2. Ensure password in both `REDIS_PASSWORD` and `REDIS_URL`
3. No spaces or quotes around password

### Connection Refused

**Error:** `ConnectionRefusedError`

**Causes:**
1. Redis Cloud database not active
2. Wrong endpoint

**Solutions:**
1. Check database status in Redis Cloud console
2. Verify endpoint matches exactly

### SSL/TLS Issues

If you need SSL (Redis Cloud supports it):

```bash
# Update REDIS_URL
REDIS_URL=rediss://default:password@host:port/0
#         ^ Note the extra 's' for SSL
```

## Switching Back to Local Redis

If you want to use local Docker Redis instead:

### 1. Update docker-compose.yml

Uncomment Redis service dependency:

```yaml
depends_on:
  postgres:
    condition: service_healthy
  redis:  # Uncomment these lines
    condition: service_healthy
```

### 2. Start with local-redis profile

```bash
docker-compose --profile local-redis up -d
```

### 3. Update .env

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_URL=redis://localhost:6379/0
```

## Security Best Practices

### For Redis Cloud

1. **Use strong passwords** (Redis Cloud generates these)
2. **Don't commit `.env`** (already in .gitignore)
3. **Rotate passwords** regularly
4. **Monitor access logs** in Redis Cloud console
5. **Enable IP allowlist** if available in your plan

### For Production

1. **Use Redis Cloud Pro** for better limits
2. **Enable SSL/TLS** (use `rediss://`)
3. **Set up alerts** for memory usage
4. **Use separate databases** per environment (dev=0, staging=1, prod=2)
5. **Regular backups** (Redis Cloud handles this)

## Cost & Upgrades

**Free Tier:**
- ✅ Perfect for development
- ✅ Good for testing
- ⚠️ Limited for production (30MB, 30 connections)

**Upgrade Needed When:**
- Memory usage > 25MB (leave headroom)
- Active connections > 25
- Need > 100 req/second
- Need longer data persistence

**Paid Plans Start:**
- ~$5/month for 100MB
- Scale as needed

## Summary

✅ **Your Redis Cloud is configured:**
- Host: `redis-10054.c338.eu-west-2-1.ec2.cloud.redislabs.com`
- Port: `10054`
- Region: EU West (London)

**Next Steps:**
1. Get your password from Redis Cloud console
2. Update `.env` with password
3. Start system: `docker-compose up -d`
4. Verify: `docker logs dv360-backend | grep Redis`

**Files Modified:**
- `.env.example` - Shows Redis Cloud configuration
- `infrastructure/docker-compose.yml` - Uses external Redis
- `docs/REDIS_CLOUD_SETUP.md` - This guide

**Ready to go!** 🔴
