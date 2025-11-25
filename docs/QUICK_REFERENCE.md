# VoiceAgent - Quick Reference

Quick reference for the healthcare voice AI system.

---

## 30-Second Summary

Production-ready healthcare voice AI that conducts patient intake over the phone. Built with FastAPI, Deepgram for speech, GPT-4 for intelligence. Handles real-time audio streaming via Twilio WebSocket. Redis for horizontal scaling. HIPAA-compliant with PHI redaction. 35+ Prometheus metrics for observability. Graceful shutdown for zero-downtime deployments.

---

## Tech Stack

| Component | Technology | Why? |
|-----------|------------|------|
| Framework | FastAPI | Async/await, WebSocket, high performance |
| Telephony | Twilio | Industry standard, WebSocket MediaStream |
| STT | Deepgram | Real-time, <300ms latency, telephony-optimized |
| TTS | Deepgram Aura | Ultra-low latency, natural voices |
| LLM | GPT-4 | Best healthcare context understanding |
| State | Redis | Fast, distributed, TTL, horizontal scaling |
| Pipeline | Pipecat | Purpose-built for voice AI |
| Monitoring | Prometheus | Industry standard, Kubernetes integration |
| CI/CD | GitHub Actions | Automated testing, security scanning |

---

## System Flow

```
Patient calls Twilio number
    ↓
Twilio webhook → POST /voice/answer
    ↓
Return TwiML with WebSocket stream URL
    ↓
Twilio connects WebSocket (audio streaming starts)
    ↓
Audio forwarded to Deepgram STT → Transcription
    ↓
VoiceHandler processes (10-phase state machine)
    ↓
GPT-4 called if needed (validation, extraction)
    ↓
Response → Deepgram TTS → Audio
    ↓
Audio sent back to Twilio → Patient hears response
    ↓
State stored in Redis (horizontal scaling)
    ↓
Metrics tracked in Prometheus
    ↓
Call completes → Send email summary
```

---

## 10-Phase Conversation Flow

1. **GREETING** - Introduce system
2. **INSURANCE** - Collect payer name + member ID
3. **CHIEF_COMPLAINT** - "What brings you in today?"
4. **DEMOGRAPHICS** - Name, DOB, phone
5. **ADDRESS** - Street, city, state, ZIP (USPS validation)
6. **PHARMACY** - Preferred pharmacy
7. **EMERGENCY_CONTACT** - Emergency contact details
8. **SCHEDULING** - Available appointment slots
9. **SUMMARY** - Confirm all collected data
10. **COMPLETE** - Send email, end call

---

## Key Architectural Decisions

### 1. Hybrid STT Approach
**Problem:** Pipecat STT unreliable  
**Solution:** Direct Deepgram WebSocket + inject transcriptions into Pipecat  
**Trade-off:** Complexity vs. reliability

### 2. Redis State Management
**Problem:** In-memory prevents scaling  
**Solution:** Redis with abstract interface + fallback  
**Trade-off:** Infrastructure cost vs. horizontal scaling

### 3. Modular Architecture
**Problem:** 755-line monolithic main.py  
**Solution:** Extracted 4 focused modules (83% reduction)  
**Trade-off:** More files vs. maintainability

### 4. Graceful Shutdown
**Problem:** Calls dropped on deployment  
**Solution:** SIGTERM handling + 30s timeout for active calls  
**Trade-off:** Slower deployments vs. zero-downtime

### 5. Prometheus Monitoring
**Problem:** No production observability  
**Solution:** 35+ metrics across 5 categories  
**Trade-off:** 5% overhead vs. visibility

---

## Production Features

| Feature | Before | After | Impact |
|---------|--------|-------|--------|
| **Logging** | 155 print() | Structured logging | HIPAA compliance, log aggregation |
| **PHI Redaction** | Plaintext logs | Auto-redaction | HIPAA compliance |
| **State Management** | In-memory | Redis | Horizontal scaling |
| **Architecture** | 755-line monolith | 4 modules (125 lines) | 83% reduction, maintainable |
| **Monitoring** | None | 35+ Prometheus metrics | Production visibility |
| **Testing** | 1 file (~5%) | 72+ tests (50%+) | Confidence, regression prevention |
| **CI/CD** | Manual | GitHub Actions | Automated quality |
| **Shutdown** | Abrupt | Graceful (30s timeout) | Zero-downtime deployments |

---

## Performance & Scalability

**Latency:**
- STT: <300ms
- TTS: <400ms
- LLM: 1-3s
- State ops: <1ms
- **Total:** 1.5-4s (user speaks → hears response)

**Capacity (per instance):**
- Concurrent calls: ~50-100
- Memory: ~2GB + 20MB/call
- Network: ~64kbps/call

**Cost:** ~$0.05-0.15 per minute
- Deepgram: $0.019/min
- OpenAI: $0.03-0.10/call
- Twilio: $0.018/min

**Scaling:** Horizontal with Kubernetes + Redis

---

## Security & HIPAA

✅ PHI automatically redacted from logs (30+ tests)  
✅ TLS 1.3 everywhere (WSS, HTTPS, STARTTLS)  
✅ Twilio signature validation  
✅ Redis encryption at rest  
✅ Admin endpoints require API key  
✅ 1-hour TTL on Redis state (auto cleanup)  
✅ Structured logs for audit trail  
✅ Security scanning in CI/CD

**PHI Collected:**
- Name, DOB, phone, address
- Insurance (payer, member ID)
- Symptoms, emergency contact

---

## Monitoring (35+ Metrics)

**Call Metrics:**
- `voiceagent_active_calls` - Current active calls
- `voiceagent_calls_total{status}` - Total by outcome
- `voiceagent_call_duration_seconds` - Duration histogram

**Pipeline Metrics:**
- `voiceagent_pipeline_processing_seconds` - Latency
- `voiceagent_pipeline_errors_total` - Errors

**State Metrics:**
- `voiceagent_redis_connected` - Redis status
- `voiceagent_state_operation_duration_seconds` - State op latency

**External Services:**
- `voiceagent_deepgram_stt_latency_seconds` - STT latency
- `voiceagent_openai_latency_seconds` - LLM latency
- `voiceagent_openai_tokens_total` - Token usage

**Business Metrics:**
- `voiceagent_insurance_providers_total{provider}` - Provider distribution
- `voiceagent_chief_complaints_total{category}` - Symptoms

---

## Module Breakdown

```
src/
├── main.py (125 lines)           # App initialization, routing
├── api/
│   ├── health.py                 # Health checks
│   ├── metrics.py                # Prometheus /metrics endpoint
│   ├── webhooks.py (148 lines)   # Twilio webhooks
│   └── websocket.py (362 lines)  # WebSocket handler
├── pipeline/
│   └── factory.py (276 lines)    # Pipeline creation (STT/TTS)
├── core/
│   ├── models.py                 # Pydantic models
│   ├── state_manager_base.py     # Abstract interface
│   ├── redis_state_manager.py    # Redis implementation
│   ├── memory_state_manager.py   # In-memory fallback
│   ├── state_manager_factory.py  # Factory pattern
│   └── shutdown.py               # Graceful shutdown
├── handlers/
│   ├── voice_handler.py          # Main business logic (10 phases)
│   ├── insurance_handler.py      # Insurance validation
│   ├── demographics_handler.py   # Demographics extraction
│   ├── symptom_handler.py        # Symptom extraction
│   └── scheduling_handler.py     # Appointment scheduling
├── utils/
│   ├── logger.py                 # Logger setup
│   ├── structured_logging.py     # Logging helpers
│   ├── phi_redactor.py           # PHI redaction engine
│   └── metrics.py                # Prometheus metrics
└── config/
    ├── settings.py               # Pydantic settings
    └── constants.py              # Configuration constants
```

---

## Key Numbers

- **155** print statements → structured logging
- **755** lines → **125** lines (83% reduction)
- **72+** tests (from 1 test file)
- **35+** Prometheus metrics
- **10** conversation phases
- **50-100** concurrent calls per instance
- **<300ms** STT latency
- **~$0.10** per minute cost
- **30s** graceful shutdown timeout
- **1 hour** Redis TTL
- **30+** PHI redaction tests

---

## Deployment Architecture

```
┌─────────────────────────────────────────┐
│     Kubernetes Cluster                  │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  Ingress (Load Balancer)        │   │
│  │  - Sticky sessions by call_sid  │   │
│  └────────┬────────────────────────┘   │
│           │                             │
│  ┌────────┴─────────────────────────┐  │
│  │  VoiceAgent Pods (3 replicas)    │  │
│  │  - Auto-scaling (based on calls) │  │
│  └────────┬─────────────────────────┘  │
│           │                             │
│  ┌────────┴─────────────────────────┐  │
│  │  Redis Cluster                   │  │
│  │  - High Availability             │  │
│  │  - Persistence (RDB/AOF)         │  │
│  └──────────────────────────────────┘  │
│                                         │
└─────────────────────────────────────────┘
           │              │
           ↓              ↓
    ┌──────────┐   ┌──────────┐
    │Prometheus│   │Grafana   │
    │(Metrics) │   │(Dashboards)│
    └──────────┘   └──────────┘
```

---

## Quick Commands

```bash
# Start development server
uvicorn src.main:app --reload

# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Build Docker image
docker build -f deployment/Dockerfile -t voiceagent .

# Run with Docker
docker run -p 8000:8000 --env-file .env voiceagent

# Health check
curl http://localhost:8000/health

# Detailed health check
curl http://localhost:8000/health/detailed
```

---

*Last Updated: November 2025*


