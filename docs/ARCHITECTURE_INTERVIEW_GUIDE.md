# VoiceAgent Architecture - Interview Guide

**Project**: Healthcare Voice AI Agent for Patient Intake
**Role**: Senior Backend Engineer / Technical Lead
**Focus**: Production-ready, HIPAA-compliant, scalable voice AI system

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture Overview](#system-architecture-overview)
3. [Technology Stack & Rationale](#technology-stack--rationale)
4. [Data Flow - Call Lifecycle](#data-flow---call-lifecycle)
5. [Key Architectural Decisions](#key-architectural-decisions)
6. [Production Improvements Implemented](#production-improvements-implemented)
7. [Scalability & Performance](#scalability--performance)
8. [Security & HIPAA Compliance](#security--hipaa-compliance)
9. [Monitoring & Observability](#monitoring--observability)
10. [Challenges & Solutions](#challenges--solutions)
11. [Interview Talking Points](#interview-talking-points)

---

## Executive Summary

**What is VoiceAgent?**
A production-ready healthcare voice AI system that conducts patient intake interviews over the phone, collecting insurance information, symptoms, demographics, and scheduling appointments - all through natural conversation.

**Business Value:**
- Reduces front-desk staff workload by 60-70%
- Collects structured patient data automatically
- Available 24/7 for patient intake
- Reduces wait times and improves patient experience
- HIPAA-compliant data handling

**Technical Complexity:**
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

**Alternative Considered:** Flask
- ❌ No native async support
- ❌ Requires extensions for WebSocket

### Audio Pipeline: **Pipecat**
**Why Pipecat?**
- ✅ Purpose-built for voice AI agents
- ✅ Frame-based processing (STT → Handler → TTS)
- ✅ Built-in Deepgram/OpenAI integrations
- ✅ Transport abstractions (Twilio, WebRTC, etc.)

**Challenge:** Pipecat STT had reliability issues
**Solution:** Hybrid approach - direct Deepgram WebSocket for STT, Pipecat for TTS/pipeline

### Speech-to-Text: **Deepgram**
**Why Deepgram?**
- ✅ Real-time streaming STT
- ✅ Low latency (<300ms)
- ✅ Telephony-optimized models
- ✅ Interim results (show transcription as user speaks)
- ✅ Smart formatting (punctuation, capitalization)

**Alternative Considered:** Google Speech-to-Text
- ❌ Higher latency
- ❌ More complex setup

### Text-to-Speech: **Deepgram Aura**
**Why Deepgram TTS?**
- ✅ Ultra-low latency (streaming)
- ✅ Natural-sounding voices
- ✅ Telephony optimization
- ✅ Same vendor as STT (simplifies billing/management)

**Previous:** Cartesia (had caching issues causing TTS failures)

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

**Development:** In-memory state (faster, simpler)
**Production:** Redis (required for scaling)

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

**Code:** `src/api/webhooks.py:handle_incoming_call()`
- Validates Twilio signature (production only)
- Generates WebSocket stream URL
- Returns TwiML directing Twilio to connect

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

**Code:** `src/api/websocket.py:handle_media_stream()`
- Accepts WebSocket connection
- Extracts Twilio metadata (streamSid, callSid)
- Creates conversation state (Redis or in-memory)
- Builds processing pipeline
- Starts audio forwarding loop

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

**Key Files:**
- `src/api/websocket.py`: Audio forwarding loop
- `src/handlers/voice_handler.py`: Business logic
- `src/pipeline/factory.py`: STT/TTS configuration

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

Phase 6: PHARMACY
  → Collect preferred pharmacy name and location

Phase 7: EMERGENCY_CONTACT
  → Collect emergency contact details

Phase 8: SCHEDULING
  → Offer available appointment slots
  → Confirm selection

Phase 9: SUMMARY
  → Read back collected information
  → Request confirmation

Phase 10: COMPLETE
  → Send email with collected data
  → Thank patient, end call
```

**Code:** `src/handlers/voice_handler.py`
- State machine implementation
- Phase-specific logic
- Transition conditions
- Retry/error handling

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

**Code:** `src/api/websocket.py:handle_media_stream()` finally block
- Comprehensive cleanup
- Metrics recording
- State cleanup

---

## Key Architectural Decisions

### Decision 1: Hybrid STT Approach

**Problem:** Pipecat's DeepgramSTTService was unreliable (dropped connections, no transcriptions)

**Options Considered:**
1. Fix Pipecat STT (difficult - upstream issue)
2. Switch to different framework (major refactor)
3. Hybrid: Direct Deepgram + Pipecat TTS

**Decision:** **Hybrid Approach** (Option 3)
- Direct Deepgram WebSocket for STT (bypasses Pipecat)
- Keep Pipecat for TTS and pipeline orchestration
- Forward transcriptions to pipeline via TranscriptionFrame injection

**Trade-offs:**
- ✅ PRO: Reliable STT (direct connection to Deepgram)
- ✅ PRO: Keep Pipecat benefits (TTS, pipeline, transport)
- ❌ CON: More complex (two audio paths)
- ❌ CON: More debugging surface area

**Result:** Solved STT reliability issue while maintaining framework benefits

**Code:** `src/api/websocket.py:handle_media_stream()`
- Lines 111-130: Direct Deepgram setup
- Lines 137-152: Transcription forwarding
- Lines 270-320: Audio forwarding loop

### Decision 2: Redis for State Management

**Problem:** In-memory state prevents horizontal scaling

**Options Considered:**
1. Keep in-memory (simple, but can't scale)
2. Database (PostgreSQL) - full CRUD
3. Redis (fast, TTL, distributed)

**Decision:** **Redis** (Option 3)
- Abstract base class for state manager interface
- Factory pattern to switch backends
- Graceful fallback to in-memory if Redis unavailable

**Trade-offs:**
- ✅ PRO: Horizontal scaling (multiple instances)
- ✅ PRO: Fast (<1ms latency)
- ✅ PRO: Automatic TTL cleanup
- ✅ PRO: High availability with Redis Cluster
- ❌ CON: Additional infrastructure dependency
- ❌ CON: Cost (managed Redis)

**Result:** Production-ready scaling capability

**Code:**
- `src/core/state_manager_base.py`: Abstract interface
- `src/core/redis_state_manager.py`: Redis implementation
- `src/core/memory_state_manager.py`: In-memory fallback
- `src/core/state_manager_factory.py`: Factory with fallback

### Decision 3: Modular Architecture (Refactored from Monolith)

**Problem:** Single 755-line main.py file violated Single Responsibility Principle

**Options Considered:**
1. Keep monolithic (simple, but unmaintainable)
2. Microservices (too much for single app)
3. Modular monolith (focused modules, single deployment)

**Decision:** **Modular Monolith** (Option 3)
- Extracted into 4 focused modules
- Each module has single responsibility
- Maintains deployment simplicity

**Modules Created:**
- `src/main.py` (125 lines): App initialization, routing
- `src/api/webhooks.py` (148 lines): Twilio webhooks
- `src/api/websocket.py` (362 lines): WebSocket handling
- `src/pipeline/factory.py` (276 lines): Pipeline creation

**Trade-offs:**
- ✅ PRO: Much more maintainable (focused files)
- ✅ PRO: Easier testing (independent modules)
- ✅ PRO: Better code organization
- ✅ PRO: Reduced cognitive load
- ❌ CON: More files to navigate (minimal)

**Result:** 83% reduction in main.py size, much cleaner architecture

### Decision 4: Graceful Shutdown

**Problem:** No shutdown handling - calls dropped on deployment

**Options Considered:**
1. Ignore (fast deployments, but bad UX)
2. Simple shutdown (stop accepting new calls)
3. Graceful shutdown with timeout

**Decision:** **Graceful Shutdown with Timeout** (Option 3)
- Catch SIGTERM/SIGINT signals
- Stop accepting new calls immediately
- Wait for active calls to complete (30s timeout)
- Force shutdown after timeout

**Trade-offs:**
- ✅ PRO: Zero-downtime deployments
- ✅ PRO: Better patient experience
- ✅ PRO: Kubernetes-friendly
- ❌ CON: Longer deployment time (up to 30s)

**Result:** Production-ready zero-downtime deployments

**Code:** `src/core/shutdown.py`
- Signal handler registration
- Active call tracking
- Timeout-based force shutdown

### Decision 5: Prometheus for Monitoring

**Problem:** No production observability - can't debug issues

**Options Considered:**
1. CloudWatch (AWS-specific, vendor lock-in)
2. Datadog (expensive, SaaS)
3. Prometheus + Grafana (open source, standard)

**Decision:** **Prometheus + Grafana** (Option 3)
- 35+ metrics across 5 categories
- Standard /metrics endpoint
- Integrates with Kubernetes/Docker
- Open source (no vendor lock-in)

**Metrics Categories:**
1. Call metrics (active, duration, status)
2. Pipeline metrics (latency, errors, frames)
3. State management (operations, Redis status)
4. External services (Deepgram, OpenAI latency)
5. Business metrics (insurance providers, symptoms)

**Trade-offs:**
- ✅ PRO: Industry standard
- ✅ PRO: Powerful PromQL queries
- ✅ PRO: Alert manager integration
- ✅ PRO: No vendor lock-in
- ❌ CON: Requires Prometheus server setup

**Result:** Production-grade observability

**Code:**
- `src/utils/metrics.py`: All metric definitions
- `src/api/metrics.py`: /metrics endpoint
- Instrumentation in main.py, websocket.py, state managers

---

## Production Improvements Implemented

### Improvement 1: Structured Logging

**Before:**
- 155 print() statements throughout codebase
- Emojis in logs (🔧, ✅, ❌, etc.)
- No log levels
- Not machine-parseable

**After:**
- Proper logger usage (logger.debug/info/warning/error)
- No emojis (production-ready)
- Machine-parseable JSON logs
- call_sid context throughout
- PHI automatically redacted

**Impact:**
- ✅ Log aggregation (Datadog, ELK) possible
- ✅ Better debugging (log levels)
- ✅ HIPAA compliant (PHI redaction)
- ✅ Professional production logs

**Code:** 155 print statements replaced across:
- `src/main.py`
- `src/handlers/voice_handler.py`
- `src/handlers/insurance_handler.py`

### Improvement 2: PHI Redaction (HIPAA Compliance)

**Problem:** Patient data (SSN, phone, insurance IDs) logged in plaintext

**Solution:** Comprehensive PHI redaction system
- Regex patterns for SSN, phone, email, addresses, dates
- Three redaction levels (full, partial, minimal)
- Automatic redaction in all logging functions
- 30+ tests for all PHI types

**Impact:**
- ✅ HIPAA compliant logging
- ✅ Safe for log aggregation
- ✅ Audit trail without PHI exposure
- ✅ Legal compliance

**Example:**
```python
# Before
logger.info(f"User said: My insurance ID is ABC123456, phone 555-123-4567")

# After (automatic PHI redaction)
logger.info(f"User said: My insurance ID is [REDACTED], phone XXX-XXX-4567")
```

**Code:**
- `src/utils/phi_redactor.py`: Redaction engine
- `src/utils/structured_logging.py`: Auto-redaction in logging
- `tests/unit/utils/test_phi_redactor.py`: 30+ tests

### Improvement 3: CI/CD Pipeline

**Before:** No automated testing or deployment

**After:** Comprehensive GitHub Actions pipeline
- **Lint:** ruff, black, isort
- **Type checking:** mypy
- **Tests:** pytest with coverage
- **Security:** bandit, safety

**Impact:**
- ✅ Catch bugs before production
- ✅ Consistent code quality
- ✅ Security vulnerability scanning
- ✅ Automated deployments

**Code:** `.github/workflows/ci.yml`

### Improvement 4: Comprehensive Test Suite

**Before:** 1 test file, ~5% coverage

**After:** 72+ tests, 50%+ coverage target
- Unit tests for all core components
- Async test support (pytest-asyncio)
- Mock fixtures for external services
- Redis state manager tests
- PHI redaction tests

**Impact:**
- ✅ Confidence in refactoring
- ✅ Catch regressions early
- ✅ Documentation through tests
- ✅ Faster development (TDD)

**Code:** `tests/` directory with 7 test files

### Improvement 5: Health Checks

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

**Impact:**
- ✅ Kubernetes-ready health checks
- ✅ Automatic service recovery
- ✅ Dependency monitoring
- ✅ Traffic routing control

**Code:** `src/api/health.py`

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

**Considerations:**
- WebSocket connections require session affinity
- Redis should be clustered for HA
- Auto-scaling based on active_calls metric

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

**Bottlenecks:**
1. **LLM calls** (most expensive, 1-3s)
   - Mitigation: Pre-generated responses, caching
2. **Deepgram TTS** (400ms latency)
   - Mitigation: Streaming TTS (parallel synthesis)
3. **CPU (audio processing)**
   - Mitigation: Horizontal scaling

### Cost Optimization

**Deepgram:** $0.0043/min (STT) + $0.015/min (TTS) ≈ $0.019/min
**OpenAI GPT-4:** ~$0.03-0.10 per call (varies by conversation length)
**Twilio:** $0.013/min (inbound) + $0.005/min (outbound)
**Total:** ~$0.05-0.15 per minute of call

**Optimization Strategies:**
1. Pre-generate common responses (avoid LLM calls)
2. Use GPT-4 only when necessary (validation, complex extraction)
3. Cache insurance provider mappings
4. Minimize token usage with concise prompts

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

3. **Encryption at Rest**
   - Redis encryption at rest (managed Redis)
   - Email server encryption (managed service)

4. **Access Control**
   - Admin API endpoints require API key
   - Twilio signature validation in production
   - No PHI in URLs or query parameters

5. **Audit Trail**
   - All patient interactions logged (with PHI redacted)
   - Structured logs for compliance reporting
   - Call duration and outcome tracked

6. **Data Retention**
   - Redis state: 1 hour TTL (automatic cleanup)
   - Logs: 90 days retention (configurable)
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
- `voiceagent_phi_redactions_total{phi_type}`: PHI redaction tracking

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

# Warning: High latency
- alert: HighSTTLatency
  expr: histogram_quantile(0.95, voiceagent_deepgram_stt_latency_seconds_bucket) > 1.0
  for: 10m
  severity: warning
```

### Structured Logging

**Log Format:**
```json
{
  "timestamp": "2025-01-15T10:30:45Z",
  "level": "INFO",
  "message": "Call completed successfully",
  "call_sid": "CA1234567890abcdef",
  "duration_seconds": 245.3,
  "status": "success",
  "phase": "COMPLETE"
}
```

**Log Aggregation:**
- Compatible with ELK stack, Datadog, CloudWatch
- Machine-parseable JSON
- PHI automatically redacted
- call_sid for tracing

---

## Challenges & Solutions

### Challenge 1: Pipecat STT Unreliability

**Problem:** DeepgramSTTService frequently failed to produce transcriptions

**Symptoms:**
- User speaks, but no transcription received
- WebSocket connection to Deepgram drops silently
- No error messages or logs

**Root Cause:** Pipecat's STT implementation had bugs in connection handling

**Solution:** Hybrid approach
1. Create direct Deepgram WebSocket connection (bypasses Pipecat)
2. Forward Twilio audio directly to Deepgram
3. Inject transcriptions into Pipecat pipeline as TranscriptionFrame
4. Keep Pipecat for TTS and orchestration

**Trade-off:** More complex, but reliable STT

**Code:** `src/api/websocket.py` lines 111-320

### Challenge 2: TTS Audio Caching Issues

**Problem:** Deepgram TTS returned cached audio from previous calls

**Symptoms:**
- Patient A hears responses meant for Patient B
- Audio responses don't match current conversation context

**Root Cause:** HTTP session caching, Deepgram CDN caching

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

**Trade-off:** Slightly higher latency, but correct audio

**Code:** `src/pipeline/factory.py` lines 186-200

### Challenge 3: Monolithic main.py (755 lines)

**Problem:** Single file violated Single Responsibility Principle

**Symptoms:**
- Hard to navigate codebase
- Difficult to test components independently
- High cognitive load for new developers
- Merge conflicts

**Solution:** Modular refactoring
- Extracted 4 focused modules
- Each module has single responsibility
- 83% reduction in main.py size

**Trade-off:** More files, but much more maintainable

**Code:** Refactored into:
- `src/main.py` (125 lines)
- `src/api/webhooks.py` (148 lines)
- `src/api/websocket.py` (362 lines)
- `src/pipeline/factory.py` (276 lines)

### Challenge 4: No Horizontal Scaling

**Problem:** In-memory state prevented scaling to multiple instances

**Symptoms:**
- Can only run one instance
- No high availability
- Limited capacity (~50-100 concurrent calls)

**Solution:** Redis state management
- Abstract state manager interface
- Redis implementation for production
- In-memory fallback for development
- Graceful degradation if Redis unavailable

**Trade-off:** Additional infrastructure (Redis), but production-ready scaling

**Code:**
- `src/core/state_manager_base.py`
- `src/core/redis_state_manager.py`
- `src/core/state_manager_factory.py`

### Challenge 5: No Production Observability

**Problem:** No way to debug production issues

**Symptoms:**
- Can't see call metrics
- No latency tracking
- No error rates
- Blind to production issues

**Solution:** Comprehensive Prometheus metrics
- 35+ metrics across 5 categories
- /metrics endpoint for Prometheus scraping
- Grafana dashboards for visualization
- Alert rules for critical issues

**Trade-off:** Slight performance overhead (~5% CPU), but essential for production

**Code:**
- `src/utils/metrics.py`
- `src/api/metrics.py`
- `docs/METRICS.md`

---

## Interview Talking Points

### 1. Explain the System in 2 Minutes

"VoiceAgent is a production-ready healthcare voice AI that conducts patient intake over the phone. When a patient calls, Twilio connects to our FastAPI server via WebSocket, streaming audio in real-time. We use Deepgram for ultra-low-latency speech-to-text and text-to-speech. The conversation flows through a 10-phase state machine - collecting insurance, symptoms, demographics, and scheduling appointments. GPT-4 handles complex tasks like symptom extraction and insurance validation. We store conversation state in Redis for horizontal scaling. All PHI is automatically redacted from logs for HIPAA compliance. We track 35+ Prometheus metrics for production monitoring. The system handles graceful shutdowns for zero-downtime deployments."

### 2. Key Technical Achievements

**Architecture:**
- Refactored 755-line monolith into modular architecture (83% reduction)
- Implemented hybrid STT approach (solved Pipecat reliability issues)
- Redis state management for horizontal scaling

**Production Readiness:**
- Prometheus monitoring (35+ metrics)
- Graceful shutdown (zero-downtime deployments)
- Comprehensive health checks (Kubernetes-ready)
- CI/CD pipeline with automated testing

**Security & Compliance:**
- HIPAA-compliant PHI redaction
- Structured logging (machine-parseable)
- TLS everywhere, Twilio signature validation

### 3. Design Trade-offs Made

**Hybrid STT:**
- Trade-off: Complexity vs. Reliability
- Decision: Accepted complexity for reliable STT

**Redis for State:**
- Trade-off: Infrastructure cost vs. Scalability
- Decision: Redis required for production scaling

**Modular Architecture:**
- Trade-off: More files vs. Maintainability
- Decision: Maintainability wins (4 focused modules)

**Prometheus:**
- Trade-off: Performance overhead vs. Observability
- Decision: 5% overhead acceptable for visibility

### 4. Scalability Approach

**Current Capacity:** ~50-100 concurrent calls per instance
**Scaling Strategy:** Horizontal scaling with Redis + Kubernetes
**Bottlenecks:**
1. LLM calls (1-3s) → Mitigate with caching
2. CPU (audio processing) → Horizontal scaling
3. Deepgram TTS latency (400ms) → Streaming TTS

**Auto-scaling:** Based on `voiceagent_active_calls` metric

### 5. What Would You Improve Next?

**Short-term:**
1. Add comprehensive type hints (mypy strict mode)
2. Implement circuit breakers for external services
3. Add rate limiting (prevent abuse)
4. Connection pooling for Redis/HTTP

**Medium-term:**
1. Conversation analytics (track common drop-off points)
2. A/B testing framework (test different prompts)
3. Multi-language support (Spanish, etc.)
4. Voice biometric authentication

**Long-term:**
1. Real-time transcription display (web interface)
2. AI-powered appointment recommendation
3. Integration with EHR systems (HL7/FHIR)
4. Sentiment analysis for quality monitoring

### 6. Why These Technologies?

**FastAPI:** Native async, WebSocket support, high performance
**Pipecat:** Purpose-built for voice AI, frame-based processing
**Deepgram:** Best latency for real-time STT/TTS
**GPT-4:** Excellent healthcare context understanding
**Redis:** Fast, distributed, TTL support
**Prometheus:** Industry standard, Kubernetes integration

### 7. Handling Production Issues

**Monitoring:** 35+ Prometheus metrics + alerts
**Debugging:** Structured logs with call_sid tracing
**Health Checks:** Kubernetes liveness/readiness probes
**Graceful Degradation:** Redis fallback, error handling
**Rollback:** CI/CD pipeline, zero-downtime deployments

---

## Summary: Production-Ready Healthcare Voice AI

✅ **Scalable:** Redis state, horizontal scaling, Kubernetes-ready
✅ **Reliable:** Hybrid STT, graceful shutdown, comprehensive error handling
✅ **Observable:** 35+ Prometheus metrics, structured logging, health checks
✅ **Secure:** HIPAA-compliant PHI redaction, TLS everywhere
✅ **Maintainable:** Modular architecture, 72+ tests, CI/CD pipeline
✅ **Cost-Effective:** ~$0.05-0.15 per minute, optimized LLM usage

**Business Impact:** Reduces front-desk workload 60-70%, available 24/7, improves patient experience

**Technical Complexity:** Real-time audio streaming, conversational AI, HIPAA compliance, production scalability

This system demonstrates deep technical understanding of:
- Real-time systems (WebSocket, audio streaming)
- Distributed systems (Redis, horizontal scaling)
- Production engineering (monitoring, observability, reliability)
- Healthcare compliance (HIPAA, PHI handling)
- Modern architecture (modular design, clean code)
