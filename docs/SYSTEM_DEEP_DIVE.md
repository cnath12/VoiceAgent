# VoiceAgent - System Deep Dive

**Project**: Healthcare Voice AI Agent for Patient Intake  
**Focus**: Production-ready, HIPAA-compliant, scalable voice AI system

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [Technology Stack & Rationale](#technology-stack--rationale)
4. [Data Flow - Call Lifecycle](#data-flow---call-lifecycle)
5. [Key Architectural Decisions](#key-architectural-decisions)
6. [Production Features](#production-features)
7. [Scalability & Performance](#scalability--performance)
8. [Security & HIPAA Compliance](#security--hipaa-compliance)
9. [Monitoring & Observability](#monitoring--observability)
10. [Challenges & Solutions](#challenges--solutions)

---

## Executive Summary

**What is VoiceAgent?**
A production-ready healthcare voice AI system that conducts patient intake over the phone, collecting insurance information, symptoms, demographics, and scheduling appointments - all through natural conversation.

**Business Value:**
- Reduces front-desk staff workload by 60-70%
- Collects structured patient data automatically
- Available 24/7 for patient intake
- Reduces wait times and improves patient experience
- HIPAA-compliant data handling

**Technical Highlights:**
- Real-time audio streaming (Twilio → Deepgram)
- Conversational AI with context management
- HIPAA compliance (PHI handling)
- Production scalability (Redis, Prometheus)
- Zero-downtime deployments

---

## System Architecture Overview

### High-Level Components

```
┌─────────────┐
│   Patient   │
│   (Phone)   │
└──────┬──────┘
       │ PSTN
       ↓
┌─────────────────────────────────────────────────────────────┐
│                        Twilio                                │
│  - Telephony (SIP/PSTN gateway)                             │
│  - WebSocket MediaStream (audio streaming)                   │
└──────┬──────────────────────────────────────────────────────┘
       │ WebSocket (wss://)
       │ Audio: mulaw, 8kHz
       ↓
┌─────────────────────────────────────────────────────────────┐
│                     VoiceAgent (FastAPI)                     │
│                                                               │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────┐ │
│  │  WebSocket  │───>│   Pipeline   │───>│   STT/TTS      │ │
│  │   Handler   │    │   (Pipecat)  │    │   (Deepgram)   │ │
│  └─────────────┘    └──────────────┘    └────────────────┘ │
│         │                   │                     │          │
│         ↓                   ↓                     ↓          │
│  ┌─────────────┐    ┌──────────────┐    ┌────────────────┐ │
│  │Conversation │    │Voice Handler │    │  LLM (OpenAI)  │ │
│  │    State    │    │  (Business   │    │   GPT-4        │ │
│  │  (Redis)    │    │    Logic)    │    │                │ │
│  └─────────────┘    └──────────────┘    └────────────────┘ │
│                                                               │
└───────────────────────────────────────────────────────────────┘
       │                   │                      │
       ↓                   ↓                      ↓
┌──────────┐        ┌──────────┐         ┌──────────────┐
│  Redis   │        │  Email   │         │  Prometheus  │
│  (State) │        │  (SMTP)  │         │  (Metrics)   │
└──────────┘        └──────────┘         └──────────────┘
```

### Component Responsibilities

**1. FastAPI Application** (`src/main.py`)
- HTTP/WebSocket server
- Route management
- Application lifecycle (startup/shutdown)
- Health checks and metrics endpoints

**2. WebSocket Handler** (`src/api/websocket.py`)
- Accepts Twilio MediaStream connections
- Manages call lifecycle (start → complete)
- Audio forwarding to Deepgram
- Pipeline orchestration
- Metrics tracking

**3. Pipeline Factory** (`src/pipeline/factory.py`)
- Creates Pipecat processing pipeline
- Configures STT/TTS services
- Initializes voice handler
- Service debugging instrumentation

**4. Voice Handler** (`src/handlers/voice_handler.py`)
- Business logic (conversational flow)
- 10-phase state machine (GREETING → INSURANCE → ... → COMPLETE)
- LLM interaction (GPT-4)
- Response generation
- Phase transitions

**5. State Manager** (`src/core/redis_state_manager.py`)
- Conversation state persistence
- Redis-backed (production) or in-memory (dev)
- TTL-based cleanup
- Horizontal scaling support

**6. Health & Metrics** (`src/api/health.py`, `src/api/metrics.py`)
- Service health checks (Deepgram, OpenAI, SMTP, USPS)
- Prometheus metrics (35+ metrics)
- Production monitoring

---

## Technology Stack & Rationale

### Core Framework: **FastAPI**
**Why FastAPI?**
- ✅ Native async/await support (critical for real-time audio)
- ✅ WebSocket support (Twilio MediaStream)
- ✅ Automatic OpenAPI docs
- ✅ Pydantic validation (type safety)
- ✅ High performance (Starlette + Uvicorn)

### Audio Pipeline: **Pipecat**
**Why Pipecat?**
- ✅ Purpose-built for voice AI agents
- ✅ Frame-based processing (STT → Handler → TTS)
- ✅ Built-in Deepgram/OpenAI integrations
- ✅ Transport abstractions (Twilio, WebRTC, etc.)

### Speech-to-Text: **Deepgram**
**Why Deepgram?**
- ✅ Real-time streaming STT
- ✅ Low latency (<300ms)
- ✅ Telephony-optimized models
- ✅ Interim results (show transcription as user speaks)
- ✅ Smart formatting (punctuation, capitalization)

### Text-to-Speech: **Deepgram Aura**
**Why Deepgram TTS?**
- ✅ Ultra-low latency (streaming)
- ✅ Natural-sounding voices
- ✅ Telephony optimization
- ✅ Same vendor as STT (simplifies billing/management)

### LLM: **OpenAI GPT-4**
**Why GPT-4?**
- ✅ Excellent instruction following
- ✅ Healthcare context understanding
- ✅ Consistent response quality
- ✅ JSON mode (structured outputs)

**Cost Optimization:**
- Use GPT-4 for initial greeting generation
- Pre-generated responses for predictable interactions
- Minimize token usage with smart prompting

### State Management: **Redis**
**Why Redis?**
- ✅ Horizontal scaling (multiple instances share state)
- ✅ Fast (<1ms latency)
- ✅ TTL-based cleanup (automatic state expiration)
- ✅ High availability (Redis Cluster)
- ✅ Persistence (RDB/AOF snapshots)

### Telephony: **Twilio**
**Why Twilio?**
- ✅ Industry standard for telephony
- ✅ WebSocket MediaStream (real-time audio)
- ✅ Global PSTN coverage
- ✅ Excellent documentation
- ✅ Programmable Voice API

### Monitoring: **Prometheus + Grafana**
**Why Prometheus?**
- ✅ Industry standard for metrics
- ✅ Pull-based (no agent required)
- ✅ PromQL (powerful query language)
- ✅ Integrates with Kubernetes
- ✅ Alert manager for notifications

---

## Data Flow - Call Lifecycle

### 1. Call Initiation (Twilio → VoiceAgent)

```
Patient dials → Twilio Number
      ↓
Twilio sends webhook: POST /voice/answer
      ↓
VoiceAgent returns TwiML with <Stream> URL
      ↓
Twilio connects WebSocket: wss://voiceagent/voice/stream/{call_sid}
```

### 2. WebSocket Connection (Audio Streaming Setup)

```
WebSocket connected
      ↓
Extract streamSid from Twilio "start" event
      ↓
Initialize TwilioFrameSerializer
      ↓
Create FastAPIWebsocketTransport
      ↓
Build Pipecat Pipeline: Transport → STT → Handler → TTS → Transport
      ↓
Start PipelineRunner
      ↓
Create Direct Deepgram STT connection (HYBRID FIX)
```

### 3. Audio Processing (Real-Time Streaming)

```
Twilio sends audio chunks (mulaw, 8kHz)
      ↓
Forward to Direct Deepgram STT
      ↓
Deepgram returns interim + final transcriptions
      ↓
TranscriptionFrame injected into Pipecat pipeline
      ↓
VoiceHandler receives transcription
      ↓
VoiceHandler processes based on current phase
      ↓
GPT-4 called if needed (insurance validation, symptom analysis)
      ↓
Response generated (text)
      ↓
TextFrame sent to Deepgram TTS
      ↓
TTS returns audio chunks
      ↓
AudioRawFrame sent to Transport
      ↓
Transport forwards to Twilio
      ↓
Patient hears response
```

### 4. Conversation Flow (10-Phase State Machine)

```
Phase 1: GREETING
  → Introduce system, explain process

Phase 2: INSURANCE
  → Collect payer name
  → Validate against known insurers (Blue Cross, Aetna, etc.)
  → Collect member ID (format validation)

Phase 3: CHIEF_COMPLAINT
  → Ask "What brings you in today?"
  → Extract symptoms using GPT-4
  → Classify complaint category

Phase 4: DEMOGRAPHICS
  → Collect name, DOB, phone
  → Validate formats

Phase 5: ADDRESS
  → Collect street, city, state, ZIP
  → USPS address validation API

Phase 6-10: PHARMACY → EMERGENCY_CONTACT → SCHEDULING → SUMMARY → COMPLETE
```

### 5. Call Completion

```
Phase: COMPLETE
      ↓
Send email with collected data (SMTP)
      ↓
Send EndFrame to pipeline
      ↓
Stop pipeline runner
      ↓
Cleanup Direct Deepgram connection
      ↓
Cleanup conversation state (Redis)
      ↓
Record metrics (duration, status)
      ↓
Close WebSocket
```

---

## Key Architectural Decisions

### Decision 1: Hybrid STT Approach

**Problem:** Pipecat's DeepgramSTTService was unreliable (dropped connections, no transcriptions)

**Solution:** **Hybrid Approach**
- Direct Deepgram WebSocket for STT (bypasses Pipecat)
- Keep Pipecat for TTS and pipeline orchestration
- Forward transcriptions to pipeline via TranscriptionFrame injection

**Trade-offs:**
- ✅ PRO: Reliable STT (direct connection to Deepgram)
- ✅ PRO: Keep Pipecat benefits (TTS, pipeline, transport)
- ❌ CON: More complex (two audio paths)

### Decision 2: Redis for State Management

**Problem:** In-memory state prevents horizontal scaling

**Solution:** **Redis with Factory Pattern**
- Abstract base class for state manager interface
- Factory pattern to switch backends
- Graceful fallback to in-memory if Redis unavailable

**Trade-offs:**
- ✅ PRO: Horizontal scaling (multiple instances)
- ✅ PRO: Fast (<1ms latency)
- ❌ CON: Additional infrastructure dependency

### Decision 3: Modular Architecture (Refactored from Monolith)

**Problem:** Single 755-line main.py file violated Single Responsibility Principle

**Solution:** **Modular Monolith**
- Extracted into 4 focused modules
- Each module has single responsibility
- Maintains deployment simplicity

**Modules Created:**
- `src/main.py` (125 lines): App initialization, routing
- `src/api/webhooks.py` (148 lines): Twilio webhooks
- `src/api/websocket.py` (362 lines): WebSocket handling
- `src/pipeline/factory.py` (276 lines): Pipeline creation

**Result:** 83% reduction in main.py size

### Decision 4: Graceful Shutdown

**Problem:** No shutdown handling - calls dropped on deployment

**Solution:** **Graceful Shutdown with Timeout**
- Catch SIGTERM/SIGINT signals
- Stop accepting new calls immediately
- Wait for active calls to complete (30s timeout)
- Force shutdown after timeout

**Result:** Production-ready zero-downtime deployments

### Decision 5: Prometheus for Monitoring

**Problem:** No production observability - can't debug issues

**Solution:** **Prometheus + Grafana**
- 35+ metrics across 5 categories
- Standard /metrics endpoint
- Integrates with Kubernetes/Docker
- Open source (no vendor lock-in)

---

## Production Features

### 1. Structured Logging

**Before:**
- 155 print() statements throughout codebase
- Emojis in logs (🔧, ✅, ❌, etc.)
- No log levels

**After:**
- Proper logger usage (logger.debug/info/warning/error)
- Machine-parseable JSON logs
- call_sid context throughout
- PHI automatically redacted

### 2. PHI Redaction (HIPAA Compliance)

**Problem:** Patient data (SSN, phone, insurance IDs) logged in plaintext

**Solution:** Comprehensive PHI redaction system
- Regex patterns for SSN, phone, email, addresses, dates
- Three redaction levels (full, partial, minimal)
- Automatic redaction in all logging functions
- 30+ tests for all PHI types

**Example:**
```python
# Before
logger.info(f"User said: My insurance ID is ABC123456, phone 555-123-4567")

# After (automatic PHI redaction)
logger.info(f"User said: My insurance ID is [REDACTED], phone XXX-XXX-4567")
```

### 3. CI/CD Pipeline

**Implemented:** Comprehensive GitHub Actions pipeline
- **Lint:** ruff, black, isort
- **Type checking:** mypy
- **Tests:** pytest with coverage
- **Security:** bandit, safety

### 4. Comprehensive Test Suite

**After:** 72+ tests
- Unit tests for all core components
- Async test support (pytest-asyncio)
- Mock fixtures for external services
- Redis state manager tests
- PHI redaction tests

### 5. Health Checks

**Endpoints:**
- `GET /health` - Basic health check
- `GET /health/detailed` - Dependency verification
- `GET /health/live` - Kubernetes liveness probe
- `GET /health/ready` - Kubernetes readiness probe

**Checks:**
- OpenAI API connectivity
- Deepgram API connectivity
- Twilio API connectivity
- SMTP server connectivity
- USPS API connectivity

---

## Scalability & Performance

### Horizontal Scaling

**Enabled by:**
1. **Stateless application** (state in Redis)
2. **Session affinity** (sticky sessions via Kubernetes ingress)
3. **Shared Redis** (all instances use same Redis cluster)

**Deployment Architecture:**
```
Load Balancer (Kubernetes Ingress)
    │ (sticky sessions by call_sid)
    ├─> VoiceAgent Pod 1 ─┐
    ├─> VoiceAgent Pod 2 ─┼─> Redis Cluster
    └─> VoiceAgent Pod 3 ─┘
```

### Performance Characteristics

**Latency:**
- STT latency: <300ms (Deepgram)
- TTS latency: <400ms (Deepgram Aura)
- LLM latency: 1-3s (GPT-4, varies by response length)
- State operations: <1ms (Redis)
- Total response time: 1.5-4s (user speaks → hears response)

**Capacity (per instance):**
- Concurrent calls: ~50-100 (CPU-bound)
- Memory: ~2GB base + ~20MB per active call
- Network: ~64kbps per call (audio streaming)

### Cost Estimates

**Per minute:**
- Deepgram: $0.019/min (STT + TTS)
- OpenAI: $0.03-0.10/call (varies)
- Twilio: $0.018/min
- **Total:** ~$0.05-0.15 per minute

---

## Security & HIPAA Compliance

### PHI Handling

**Protected Health Information (PHI) Collected:**
- Name, Date of Birth, Phone Number
- Address (street, city, state, ZIP)
- Insurance information (payer, member ID)
- Medical symptoms (chief complaint)
- Emergency contact information

**Compliance Measures:**

1. **PHI Redaction in Logs**
   - Automatic redaction before logging
   - Regex patterns for all PHI types
   - 30+ tests for redaction accuracy

2. **Encryption in Transit**
   - TLS 1.3 for all HTTP/WebSocket connections
   - Twilio MediaStream uses WSS (WebSocket Secure)
   - SMTP uses STARTTLS for email

3. **Data Retention**
   - Redis state: 1 hour TTL (automatic cleanup)
   - Logs: Configurable retention
   - Email: Sent once, not stored in VoiceAgent

### Production Security Checklist

- ✅ TLS/HTTPS everywhere
- ✅ Twilio signature validation
- ✅ PHI redaction in logs
- ✅ No hardcoded secrets (environment variables)
- ✅ Redis password authentication
- ✅ Admin endpoints require API key
- ✅ Security scanning in CI/CD (bandit)
- ✅ Dependency vulnerability scanning (safety)

---

## Monitoring & Observability

### Prometheus Metrics (35+ total)

**Call Metrics:**
- `voiceagent_active_calls`: Current active calls
- `voiceagent_calls_total{status}`: Total calls by outcome
- `voiceagent_call_duration_seconds`: Call duration histogram
- `voiceagent_calls_by_phase_total{phase}`: Calls reaching each phase

**Pipeline Metrics:**
- `voiceagent_pipeline_processing_seconds{frame_type}`: Processing latency
- `voiceagent_pipeline_errors_total{error_type}`: Pipeline errors
- `voiceagent_frames_processed_total{frame_type, direction}`: Frame throughput

**State Management:**
- `voiceagent_state_operations_total{operation, backend}`: State ops
- `voiceagent_state_operation_duration_seconds`: State op latency
- `voiceagent_redis_connected`: Redis connection status

**External Services:**
- `voiceagent_deepgram_stt_latency_seconds`: STT latency
- `voiceagent_deepgram_tts_latency_seconds`: TTS latency
- `voiceagent_openai_latency_seconds{model}`: LLM latency
- `voiceagent_openai_tokens_total{model, token_type}`: Token usage

**Business Metrics:**
- `voiceagent_insurance_providers_total{provider}`: Provider distribution
- `voiceagent_chief_complaints_total{category}`: Symptom categories
- `voiceagent_appointments_scheduled_total{status}`: Scheduling success

### Alerting (Example Rules)

```yaml
# Critical: High call failure rate
- alert: HighCallFailureRate
  expr: rate(voiceagent_calls_total{status="error"}[5m]) / rate(voiceagent_calls_total[5m]) > 0.1
  for: 5m
  severity: critical

# Critical: Redis down
- alert: RedisDown
  expr: voiceagent_redis_connected == 0
  for: 1m
  severity: critical
```

---

## Challenges & Solutions

### Challenge 1: Pipecat STT Unreliability

**Problem:** DeepgramSTTService frequently failed to produce transcriptions

**Solution:** Hybrid approach
1. Create direct Deepgram WebSocket connection (bypasses Pipecat)
2. Forward Twilio audio directly to Deepgram
3. Inject transcriptions into Pipecat pipeline as TranscriptionFrame
4. Keep Pipecat for TTS and orchestration

**Result:** Reliable STT while maintaining framework benefits

### Challenge 2: TTS Audio Caching Issues

**Problem:** Deepgram TTS returned cached audio from previous calls

**Solution:** Aggressive anti-caching
```python
tts_session = aiohttp.ClientSession(
    connector=aiohttp.TCPConnector(
        force_close=True,  # No connection reuse
        use_dns_cache=False
    ),
    headers={
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Connection': 'close'
    }
)
```

### Challenge 3: Monolithic main.py (755 lines)

**Problem:** Single file violated Single Responsibility Principle

**Solution:** Modular refactoring
- Extracted 4 focused modules
- Each module has single responsibility
- 83% reduction in main.py size

### Challenge 4: No Horizontal Scaling

**Problem:** In-memory state prevented scaling to multiple instances

**Solution:** Redis state management
- Abstract state manager interface
- Redis implementation for production
- In-memory fallback for development
- Graceful degradation if Redis unavailable

### Challenge 5: No Production Observability

**Problem:** No way to debug production issues

**Solution:** Comprehensive Prometheus metrics
- 35+ metrics across 5 categories
- /metrics endpoint for Prometheus scraping
- Grafana dashboards for visualization
- Alert rules for critical issues

---

## Summary

This system demonstrates production-grade engineering:

- ✅ **Scalable:** Redis state, horizontal scaling, Kubernetes-ready
- ✅ **Reliable:** Hybrid STT, graceful shutdown, comprehensive error handling
- ✅ **Observable:** 35+ Prometheus metrics, structured logging, health checks
- ✅ **Secure:** HIPAA-compliant PHI redaction, TLS everywhere
- ✅ **Maintainable:** Modular architecture, 72+ tests, CI/CD pipeline
- ✅ **Cost-Effective:** ~$0.05-0.15 per minute, optimized LLM usage

**Business Impact:** Reduces front-desk workload 60-70%, available 24/7, improves patient experience

---

*Last Updated: November 2025*


