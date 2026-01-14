# Claude (Anthropic) + OpenAI Setup Guide

## Overview

This system is configured to use **Claude (Anthropic) for agent reasoning** and **OpenAI for embeddings only**. This gives you the best of both worlds:

- ✅ **Claude 3 Opus/Sonnet** for intelligent agent reasoning
- ✅ **OpenAI text-embedding-3-small** for semantic memory (very cheap)
- ✅ Full semantic search and memory capabilities

## Why Both API Keys?

**Anthropic (Claude)**
- Powers all agent reasoning and decisions
- Superior performance for complex analysis
- Better instruction following

**OpenAI (Embeddings Only)**
- Required for semantic memory (vector search)
- Anthropic doesn't provide embeddings
- Cost: ~$0.02 per 1M tokens (very cheap)
- Only used for converting text to vectors, not reasoning

## Configuration

### 1. Get API Keys

**Anthropic API Key:**
1. Go to https://console.anthropic.com/
2. Create an account or sign in
3. Navigate to API Keys
4. Create a new API key
5. Copy the key (starts with `sk-ant-`)

**OpenAI API Key:**
1. Go to https://platform.openai.com/
2. Create an account or sign in
3. Navigate to API Keys
4. Create a new API key
5. Copy the key (starts with `sk-`)

### 2. Update .env File

```bash
# Copy the example
cp .env.example .env

# Edit .env and add your keys
nano .env  # or use your preferred editor
```

Add these lines to your `.env`:

```bash
# Anthropic - Used for LLM (agent reasoning)
ANTHROPIC_API_KEY=sk-ant-your-key-here
ANTHROPIC_MODEL=claude-3-opus-20240229

# OpenAI - Used ONLY for embeddings (semantic memory)
OPENAI_API_KEY=sk-your-key-here
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Snowflake (add your credentials)
SNOWFLAKE_ACCOUNT=your_account.region
SNOWFLAKE_USER=your_user
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_WAREHOUSE=your_warehouse
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_SCHEMA=your_schema
```

### 3. Model Options

**Claude Models (Anthropic):**
```bash
# Most capable (recommended for production)
ANTHROPIC_MODEL=claude-3-opus-20240229

# Balanced performance and cost
ANTHROPIC_MODEL=claude-3-sonnet-20240229

# Fastest and cheapest
ANTHROPIC_MODEL=claude-3-haiku-20240307
```

**Embedding Models (OpenAI):**
```bash
# Small, fast, cheap (recommended)
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# Larger, more accurate
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
```

## How It Works

### Agent Reasoning (Claude)

When you send a message:
1. Chat Conductor Agent receives message (uses Claude)
2. Routes to specialist agent(s) (uses Claude)
3. Specialist agent analyzes data (uses Claude)
4. Generates recommendations (uses Claude)

**Example log:**
```
INFO: Using Anthropic Claude for LLM model=claude-3-opus-20240229
```

### Semantic Memory (OpenAI Embeddings)

When storing/searching memories:
1. Learning text is converted to embedding vector (uses OpenAI)
2. Vector stored in PostgreSQL with pgvector
3. Similarity search uses vector cosine distance (database operation)
4. Results returned to agent (uses Claude)

**Example log:**
```
INFO: Using OpenAI for embeddings model=text-embedding-3-small
```

## Cost Estimates

### Anthropic (Claude) Costs

**Claude 3 Opus:**
- Input: $15 per 1M tokens
- Output: $75 per 1M tokens
- Typical conversation: 1,000-5,000 tokens = $0.02-$0.40

**Claude 3 Sonnet:**
- Input: $3 per 1M tokens
- Output: $15 per 1M tokens
- Typical conversation: 1,000-5,000 tokens = $0.004-$0.08

**Claude 3 Haiku:**
- Input: $0.25 per 1M tokens
- Output: $1.25 per 1M tokens
- Typical conversation: 1,000-5,000 tokens = $0.0003-$0.007

### OpenAI (Embeddings Only) Costs

**text-embedding-3-small:**
- $0.02 per 1M tokens
- Typical learning: 100 tokens = $0.000002
- 10,000 learnings = $0.02

**Total cost for 1,000 conversations:**
- Claude Opus: ~$20-$400 (depends on conversation length)
- Embeddings: ~$0.02 (negligible)

## Verification

### Check Configuration

```bash
# Start the system
docker-compose up -d

# Check logs for confirmation
docker logs dv360-backend | grep "Using"

# You should see:
# INFO: Using Anthropic Claude for LLM model=claude-3-opus-20240229
# INFO: Using OpenAI for embeddings model=text-embedding-3-small
```

### Test Agent

```bash
# Health check
curl http://localhost:8000/health

# Once chat API is implemented:
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, can you help me analyze campaign performance?",
    "user_id": "test_user"
  }'
```

### Check Database

```bash
# Check if embeddings are being stored
docker exec -it dv360-postgres psql -U dv360_user -d dv360_agents

# In psql:
SELECT agent_name, learning_type, confidence_score,
       CASE WHEN embedding IS NOT NULL THEN 'YES' ELSE 'NO' END as has_embedding
FROM agent_learnings
LIMIT 5;
```

You should see `has_embedding = YES` if everything is working.

## Troubleshooting

### "No LLM API key configured"

**Error:** `ValueError: No LLM API key configured`

**Solution:** Add at least one of:
- `ANTHROPIC_API_KEY` (recommended)
- `OPENAI_API_KEY`

### "Semantic memory disabled"

**Warning:** `Anthropic doesn't provide embeddings. Semantic memory disabled.`

**Cause:** Only `ANTHROPIC_API_KEY` is set, no `OPENAI_API_KEY`

**Impact:**
- ✅ Agents still work (use Claude)
- ❌ No semantic search
- ❌ No vector similarity
- ✅ Session memory still works

**Solution:** Add `OPENAI_API_KEY` to enable semantic memory

### Rate Limits

**Anthropic Rate Limits:**
- Tier 1: 50 requests/min, 40K tokens/min
- Tier 2: 1,000 requests/min, 80K tokens/min
- Check: https://console.anthropic.com/settings/limits

**OpenAI Rate Limits (Embeddings):**
- Tier 1: 3,000 requests/min
- Tier 2: 3,500 requests/min
- Very unlikely to hit limits for embeddings

### Invalid API Keys

**Error:** `Authentication failed` or `Invalid API key`

**Check:**
1. Key starts with correct prefix:
   - Anthropic: `sk-ant-`
   - OpenAI: `sk-`
2. No extra spaces or quotes in `.env`
3. Key is active (not revoked)
4. Account has billing set up

### Restart Required

After changing `.env`, restart services:

```bash
docker-compose restart backend

# Or full restart
docker-compose down
docker-compose up -d
```

## Alternative Configurations

### Option 2: Claude Only (No Semantic Memory)

If you don't want to use OpenAI at all:

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-your-key-here
# Don't set OPENAI_API_KEY
```

**Result:**
- ✅ Agents work (Claude)
- ❌ No semantic search
- ❌ No learnings storage with vectors
- ✅ Session-based memory works

### Option 3: OpenAI Only

If you prefer GPT-4:

```bash
# .env
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4-turbo-preview
# Don't set ANTHROPIC_API_KEY
```

**Result:**
- ✅ Agents work (GPT-4)
- ✅ Semantic search works
- ✅ Full memory system works

## Best Practices

### Production Setup

1. **Use Separate Keys** for dev/staging/prod
2. **Monitor Usage** via console.anthropic.com and platform.openai.com
3. **Set Budget Alerts** in both consoles
4. **Rotate Keys** regularly for security
5. **Use Environment Variables** never hardcode keys

### Cost Optimization

1. **Use Haiku for simple tasks** (10x cheaper than Opus)
2. **Cache frequently accessed data** (reduces LLM calls)
3. **Use smaller embedding model** (text-embedding-3-small)
4. **Implement rate limiting** (already configured)
5. **Monitor token usage** (via Prometheus metrics)

### Security

1. **Never commit `.env`** (already in .gitignore)
2. **Use secrets management** in production (Vault, AWS Secrets Manager)
3. **Restrict API key permissions** if available
4. **Monitor for unusual usage** (could indicate key leak)
5. **Rotate keys immediately** if compromised

## FAQ

**Q: Can I use only OpenAI?**
A: Yes, just don't set `ANTHROPIC_API_KEY`. GPT-4 will be used for both LLM and embeddings.

**Q: Can I use only Anthropic?**
A: Yes, but semantic memory will be disabled. Session memory still works.

**Q: Which is better, Claude or GPT-4?**
A: Claude is generally better for complex reasoning and instruction following. GPT-4 is good too. Try both!

**Q: How much will embeddings cost?**
A: Very little. Even with 10,000 learnings, expect < $1/month.

**Q: Can I change models later?**
A: Yes, just update `.env` and restart. All stored data remains compatible.

**Q: Do I need LangSmith?**
A: No, it's optional. Useful for debugging agents but not required.

**Q: What about Snowflake costs?**
A: Snowflake is read-only. Costs depend on your Snowflake plan and query volume.

## Summary

**Recommended Setup (Option 1):**
```bash
ANTHROPIC_API_KEY=sk-ant-...  # For agent reasoning
OPENAI_API_KEY=sk-...          # For embeddings only
```

**Result:**
- ✅ Claude for intelligent reasoning
- ✅ Full semantic memory
- ✅ Growing intelligence
- ✅ Best performance
- 💰 Embeddings cost < $1/month

This is the optimal configuration for the DV360 Multi-Agent System!
