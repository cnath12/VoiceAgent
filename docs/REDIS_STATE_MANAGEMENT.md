# Redis State Management Guide

## Overview

VoiceAgent supports two state management backends:

1. **In-Memory State Manager** (default) - Simple, fast, single-instance
2. **Redis State Manager** (production) - Scalable, persistent, multi-instance

This guide covers Redis setup, configuration, and migration.

---

## Why Redis?

### Limitations of In-Memory State

The default in-memory state manager has several limitations:

❌ **State lost on restart** - Calls interrupted during deployment
❌ **Single instance only** - Cannot scale horizontally
❌ **No high availability** - Single point of failure
❌ **No failover** - Instance crash = lost state

###Benefits of Redis State

✅ **Persistent state** - Survives restarts and deployments
✅ **Horizontal scaling** - Multiple instances share state
✅ **High availability** - Redis clustering support
✅ **Automatic cleanup** - TTL-based state expiration
✅ **Production ready** - Battle-tested reliability

---

## Quick Start

### 1. Install Redis

**macOS (Homebrew):**
```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

**Docker:**
```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

**Render.com (Production):**
- Add Redis addon in Render dashboard
- Copy the `REDIS_URL` from addon details

### 2. Install Python Dependencies

```bash
pip install redis>=5.0.0 hiredis>=2.2.0
```

Already included in `requirements.txt` after this update.

### 3. Configure Environment

Update your `.env` file:

```bash
# Enable Redis
USE_REDIS=true

# Option A: Individual settings
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_SSL=false

# Option B: Full URL (overrides individual settings)
REDIS_URL=redis://localhost:6379/0
```

### 4. Restart Application

```bash
uvicorn src.main:app --reload
```

You should see in logs:
```
INFO: Initializing Redis-backed state manager
INFO: Redis connection established
```

---

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_REDIS` | `false` | Enable Redis state management |
| `REDIS_HOST` | `localhost` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `REDIS_DB` | `0` | Redis database number (0-15) |
| `REDIS_PASSWORD` | `` | Redis authentication password |
| `REDIS_SSL` | `false` | Use SSL/TLS connection |
| `REDIS_URL` | `` | Full Redis URL (overrides above) |

### Redis URL Format

```
redis://[[username:]password@]host[:port][/database]
rediss://[[username:]password@]host[:port][/database]  # SSL
```

**Examples:**
```bash
# Local development
REDIS_URL=redis://localhost:6379/0

# Password-protected
REDIS_URL=redis://:mypassword@redis.example.com:6379/0

# SSL (production)
REDIS_URL=rediss://:mypassword@secure-redis.com:6379/0

# Render.com addon
REDIS_URL=redis://red-xxxx:password@oregon-redis.render.com:6379
```

---

## Architecture

### State Storage

States are stored as JSON in Redis:

**Key Pattern:**
```
voiceagent:state:{call_sid}
```

**Example:**
```
voiceagent:state:CA1234567890abcdef
```

**Value:** JSON-serialized `ConversationState` object

### TTL (Time-To-Live)

Default: **3600 seconds (1 hour)**

States automatically expire after 1 hour to prevent memory leaks from abandoned calls.

Configurable in code:
```python
RedisStateManager(redis_client, ttl_seconds=1800)  # 30 minutes
```

### Serialization

- **Format:** JSON via Pydantic's `model_dump_json()` / `model_validate_json()`
- **Encoding:** UTF-8
- **Compression:** None (Redis handles memory optimization)

---

## Production Deployment

### Render.com Setup

1. **Add Redis Addon:**
   - Go to your Render service
   - Click "New" → "Redis"
   - Select plan (Starter: $7/month, Pro: $25/month)
   - Note the `REDIS_URL` from addon details

2. **Configure Environment:**
   ```bash
   USE_REDIS=true
   REDIS_URL=<redis-url-from-render>
   ```

3. **Deploy:**
   - Push changes to GitHub
   - Render auto-deploys with Redis enabled

### AWS ElastiCache

```bash
USE_REDIS=true
REDIS_URL=redis://my-cluster.xxxxx.cache.amazonaws.com:6379/0
```

### Azure Cache for Redis

```bash
USE_REDIS=true
REDIS_URL=rediss://:password@my-cache.redis.cache.windows.net:6380/0
REDIS_SSL=true
```

### Docker Compose

```yaml
version: '3.8'
services:
  app:
    build: .
    environment:
      - USE_REDIS=true
      - REDIS_HOST=redis
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

volumes:
  redis-data:
```

---

## Monitoring & Health Checks

### Health Check Endpoint

Redis state manager provides a health check:

```bash
curl http://localhost:8000/health/detailed
```

Response includes Redis status:
```json
{
  "status": "healthy",
  "checks": {
    "redis": {
      "status": "healthy",
      "message": "Redis connection OK"
    }
  }
}
```

### Monitor Active Calls

```python
from src.core.state_manager_factory import get_state_manager

manager = await get_state_manager()

# Get count of active calls
count = await manager.get_active_calls_count()
print(f"Active calls: {count}")

# Get all call SIDs
call_sids = await manager.get_all_call_sids()
print(f"Call SIDs: {call_sids}")
```

### Redis CLI Monitoring

```bash
# Connect to Redis
redis-cli

# List all conversation states
KEYS voiceagent:state:*

# Get specific state
GET voiceagent:state:CA1234567890abcdef

# Check TTL
TTL voiceagent:state:CA1234567890abcdef

# Monitor commands in real-time
MONITOR
```

---

## Migration from In-Memory

### Zero-Downtime Migration

1. **Set up Redis** (see Quick Start above)

2. **Enable Redis** in environment:
   ```bash
   USE_REDIS=true
   REDIS_URL=redis://localhost:6379/0
   ```

3. **Rolling deployment:**
   - Deploy new instances with Redis enabled
   - Existing in-memory calls continue normally
   - New calls use Redis automatically
   - Scale down old instances after calls complete

### Gradual Rollout

Test Redis with a subset of traffic:

```python
# In state_manager_factory.py
import random

@classmethod
async def create_state_manager(cls) -> StateManagerBase:
    settings = get_settings()

    # 50% traffic to Redis, 50% to in-memory
    if settings.use_redis and random.random() < 0.5:
        return await cls._create_redis_manager(settings)
    else:
        return InMemoryStateManager()
```

---

## Troubleshooting

### Connection Refused

**Error:** `redis.exceptions.ConnectionError: Error connecting to Redis`

**Solutions:**
1. Verify Redis is running: `redis-cli ping` → should return `PONG`
2. Check `REDIS_HOST` and `REDIS_PORT` in `.env`
3. Check firewall rules
4. For Docker: ensure Redis container is on same network

### Authentication Failed

**Error:** `redis.exceptions.AuthenticationError: Authentication required`

**Solutions:**
1. Set `REDIS_PASSWORD` in `.env`
2. Or use full URL: `redis://:password@host:port/0`

### Slow Performance

**Symptoms:** High latency, slow API responses

**Solutions:**
1. **Use hiredis:** Already included in `requirements.txt` - faster Redis protocol parser
2. **Check network latency:** Use Redis in same region/data center as app
3. **Connection pooling:** Already handled by `redis-py`
4. **Monitor Redis:** `redis-cli --latency` to check Redis response times

### State Not Persisting

**Symptoms:** State lost between requests

**Debug:**
```bash
# Check if keys are being created
redis-cli KEYS voiceagent:state:*

# Check TTL
redis-cli TTL voiceagent:state:CA1234567890abcdef

# Check logs
# Should see: "Created conversation state in Redis"
```

### Memory Usage Growing

**Symptoms:** Redis memory keeps growing

**Solutions:**
1. **Verify TTL is set:** Default 1 hour should auto-expire states
2. **Manual cleanup:**
   ```bash
   # Delete all conversation states
   redis-cli KEYS "voiceagent:state:*" | xargs redis-cli DEL
   ```
3. **Reduce TTL:** Set lower TTL in `RedisStateManager` init

---

## Performance Benchmarks

### Latency Comparison

| Operation | In-Memory | Redis (Local) | Redis (Remote) |
|-----------|-----------|---------------|----------------|
| Create State | 0.1ms | 1-2ms | 10-20ms |
| Get State | 0.05ms | 0.5-1ms | 5-10ms |
| Update State | 0.1ms | 1-2ms | 10-20ms |

### Scalability

| Metric | In-Memory | Redis |
|--------|-----------|-------|
| Max Instances | 1 | Unlimited |
| Max Concurrent Calls | ~100/instance | ~1000+/instance |
| State Persistence | ❌ | ✅ |
| Failover | ❌ | ✅ (with Redis Sentinel/Cluster) |

---

## Best Practices

### Development
- Use **in-memory** for local development (faster, simpler)
- Use **Redis** for integration testing (matches production)

### Production
- Always use **Redis** in production
- Enable Redis **persistence** (RDB + AOF)
- Use Redis **Sentinel** or **Cluster** for high availability
- Monitor Redis **memory usage**
- Set appropriate **TTL** based on average call duration

### Security
- **Password-protect** Redis in production
- Use **SSL/TLS** for remote connections
- **Firewall** Redis port (6379) - only allow app servers
- **Backup** Redis data regularly (Render does this automatically)

---

## Advanced Configuration

### Redis Clustering

For massive scale (1000+ concurrent calls):

```bash
# Use Redis Cluster URL
REDIS_URL=redis-cluster://node1:6379,node2:6379,node3:6379/0
```

### Redis Sentinel (High Availability)

```python
from redis.sentinel import Sentinel

sentinel = Sentinel([
    ('sentinel1', 26379),
    ('sentinel2', 26379),
    ('sentinel3', 26379)
])
redis_client = sentinel.master_for('mymaster', socket_timeout=0.1)
```

### Custom State Manager

Extend `StateManagerBase` for custom backends:

```python
from src.core.state_manager_base import StateManagerBase

class PostgresStateManager(StateManagerBase):
    # Implement all abstract methods
    async def create_state(self, call_sid: str) -> ConversationState:
        # Custom implementation
        ...
```

---

## FAQ

**Q: Will existing calls be dropped when switching to Redis?**
A: No. Existing in-memory calls continue normally. New calls use Redis.

**Q: Can I use Redis for some calls and in-memory for others?**
A: Not recommended. Choose one backend globally via `USE_REDIS` setting.

**Q: What happens if Redis goes down?**
A: Factory falls back to in-memory automatically (with warning logged).

**Q: How much does Redis cost?**
A: Render Starter: $7/month. AWS ElastiCache: ~$15/month. Self-hosted: free.

**Q: Do I need to change my code to use Redis?**
A: No! The state manager interface is identical. Just set `USE_REDIS=true`.

---

## Support

For issues or questions:
1. Check logs for Redis connection errors
2. Test Redis connection: `redis-cli ping`
3. Review this guide's Troubleshooting section
4. Open an issue on GitHub with logs

---

**Last Updated:** November 2025
**Redis Version:** 7.x
**Python Redis Client:** redis-py 5.x
