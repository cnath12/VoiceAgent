# VoiceAgent Architecture

A production-ready healthcare voice AI agent that conducts patient intake interviews over the phone, collecting insurance information, symptoms, demographics, and scheduling appointments through natural conversation.

---

## System Overview

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

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Framework** | FastAPI | Async HTTP/WebSocket, high performance |
| **Telephony** | Twilio | PSTN gateway, WebSocket MediaStream |
| **STT** | Deepgram | Real-time speech-to-text (<300ms) |
| **TTS** | Deepgram Aura | Ultra-low latency text-to-speech |
| **LLM** | OpenAI GPT-4 | Classification and extraction |
| **State** | Redis | Distributed state, horizontal scaling |
| **Pipeline** | Pipecat | Frame-based voice AI processing |
| **Monitoring** | Prometheus | 35+ metrics for observability |

---

## Project Structure

```
VoiceAgent/
├── src/
│   ├── main.py                   # FastAPI app entry point
│   ├── api/                      # API endpoints
│   │   ├── health.py            # Health checks (liveness, readiness)
│   │   ├── metrics.py           # Prometheus /metrics endpoint
│   │   ├── webhooks.py          # Twilio webhook handlers
│   │   └── websocket.py         # WebSocket media stream handler
│   ├── pipeline/
│   │   └── factory.py           # Pipecat pipeline creation
│   ├── config/
│   │   ├── settings.py          # Pydantic configuration
│   │   ├── constants.py         # Application constants
│   │   └── prompts.py           # Conversation prompts
│   ├── core/
│   │   ├── models.py            # Pydantic data models
│   │   ├── conversation_state.py # State manager interface
│   │   ├── redis_state_manager.py # Redis implementation
│   │   ├── memory_state_manager.py # In-memory fallback
│   │   ├── shutdown.py          # Graceful shutdown handler
│   │   └── validators.py        # Input validation
│   ├── handlers/
│   │   ├── voice_handler.py     # Main conversation orchestrator
│   │   ├── insurance_handler.py # Insurance collection
│   │   ├── symptom_handler.py   # Chief complaint extraction
│   │   ├── demographics_handler.py # Address and contact
│   │   └── scheduling_handler.py # Appointment scheduling
│   ├── services/
│   │   ├── llm_service.py       # OpenAI integration
│   │   ├── email_service.py     # SMTP confirmation emails
│   │   ├── provider_service.py  # Provider/appointment data
│   │   └── address_service.py   # USPS address validation
│   └── utils/
│       ├── logger.py            # Logging configuration
│       ├── metrics.py           # Prometheus metrics
│       ├── phi_redactor.py      # HIPAA-compliant PHI redaction
│       └── structured_logging.py # Structured log helpers
├── tests/                        # Test suite
├── docs/                         # Technical documentation
├── deployment/                   # Docker, Render configs
└── requirements.txt              # Python dependencies
```

---

## Conversation Flow

The system implements a 10-phase state machine:

```
GREETING → INSURANCE → CHIEF_COMPLAINT → DEMOGRAPHICS → CONTACT_INFO
    ↓
PROVIDER_SELECTION → APPOINTMENT_SCHEDULING → CONFIRMATION → COMPLETED
```

| Phase | Data Collected |
|-------|---------------|
| **GREETING** | Introduction, explain process |
| **INSURANCE** | Payer name, member ID |
| **CHIEF_COMPLAINT** | Symptoms, duration, pain level |
| **DEMOGRAPHICS** | Address (USPS validated) |
| **CONTACT_INFO** | Phone, email |
| **PROVIDER_SELECTION** | Doctor selection (insurance-matched) |
| **APPOINTMENT_SCHEDULING** | Date and time selection |
| **CONFIRMATION** | Review and confirm |
| **COMPLETED** | Email confirmation, end call |

---

## Key Architectural Decisions

### 1. Hybrid STT Approach
**Problem:** Pipecat's STT had reliability issues  
**Solution:** Direct Deepgram WebSocket + inject transcriptions into Pipecat pipeline  
**Trade-off:** More complexity, but reliable transcription

### 2. Redis State Management
**Problem:** In-memory state prevents horizontal scaling  
**Solution:** Redis with abstract interface + in-memory fallback  
**Trade-off:** Infrastructure cost, but production-ready scaling

### 3. Modular Architecture
**Problem:** Original 755-line monolithic main.py  
**Solution:** Extracted into focused modules (83% size reduction)  
**Trade-off:** More files, but much more maintainable

### 4. Graceful Shutdown
**Problem:** Calls dropped on deployment  
**Solution:** SIGTERM handling + 30s timeout for active calls  
**Trade-off:** Slower deployments, but zero-downtime

### 5. PHI Redaction
**Problem:** Patient data logged in plaintext  
**Solution:** Automatic regex-based redaction in all logs  
**Trade-off:** Slightly more processing, but HIPAA compliant

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/voice/answer` | POST | Twilio incoming call webhook |
| `/voice/stream/{call_sid}` | WebSocket | Real-time audio streaming |
| `/voice/recording` | POST | Recording callback |
| `/health` | GET | Basic health check |
| `/health/detailed` | GET | Dependency verification |
| `/health/live` | GET | Kubernetes liveness probe |
| `/health/ready` | GET | Kubernetes readiness probe |
| `/metrics` | GET | Prometheus metrics |
| `/debug/state/{call_sid}` | GET | Debug state (admin only) |

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| STT Latency | <300ms |
| TTS Latency | <400ms |
| LLM Latency | 1-3s |
| State Operations | <1ms (Redis) |
| Total Response Time | 1.5-4s |
| Concurrent Calls | ~50-100 per instance |
| Call Completion Rate | ~85% |
| Average Call Duration | ~3.5 minutes |

---

## Security & Compliance

### HIPAA Compliance
- ✅ Automatic PHI redaction in all logs
- ✅ TLS 1.3 everywhere (WSS, HTTPS, STARTTLS)
- ✅ 1-hour TTL on Redis state (auto cleanup)
- ✅ No PHI in URLs or query parameters
- ✅ Audit trail with redacted logs

### Authentication
- ✅ Twilio signature validation (production)
- ✅ Admin API key for debug endpoints
- ✅ Environment-based secrets management

---

## Deployment

### Local Development
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
uvicorn src.main:app --reload
```

### Production (Docker)
```bash
docker build -f deployment/Dockerfile -t voiceagent .
docker run -p 8000:8000 --env-file .env voiceagent
```

### Kubernetes
The application includes:
- Health check endpoints (`/health/live`, `/health/ready`)
- Graceful shutdown (30s timeout)
- Prometheus metrics (`/metrics`)
- Horizontal scaling via Redis state

---

## Documentation

| Document | Description |
|----------|-------------|
| [README.md](README.md) | Quick start and usage |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup and guidelines |
| [docs/QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md) | Quick reference card |
| [docs/SYSTEM_DEEP_DIVE.md](docs/SYSTEM_DEEP_DIVE.md) | Detailed system walkthrough |
| [docs/METRICS.md](docs/METRICS.md) | Prometheus metrics reference |
| [docs/REDIS_STATE_MANAGEMENT.md](docs/REDIS_STATE_MANAGEMENT.md) | Redis setup guide |
| [docs/LOGGING_MIGRATION.md](docs/LOGGING_MIGRATION.md) | Structured logging guide |

---

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/handlers/test_insurance_handler.py -v
```

---

*Last Updated: November 2025*
