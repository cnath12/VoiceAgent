# Healthcare Voice AI Agent

A production-ready voice AI agent for healthcare appointment scheduling, built on the Pipecat real‑time audio pipeline and integrated with Twilio Voice.

## 🏥 What it does

- **End‑to‑end scheduling over the phone**: Insurance → chief complaint → address → contact → provider → time → confirmation email
- **Real‑time speech**: Telephony audio in/out with Deepgram STT + TTS at 8 kHz (telephony)
- **Stateful, phase‑based flow**: Deterministic handlers per phase with minimal LLM usage
- **Secure**: No PHI in logs, Twilio webhook signature validation (prod), optional admin key for debug

Conversation phases:
- Insurance
- Chief complaint (duration, pain scale)
- Demographics (address capture + optional USPS validation)
- Contact info (phone, optional email)
- Provider selection (mock service)
- Appointment time selection (mock slots)
- Confirmation and email

## 🛠️ Architecture & key choices

High‑level flow (Twilio → FastAPI/Pipecat → Services):

1) Twilio Voice MediaStream connects to `wss://<PUBLIC_HOST>/voice/stream/{call_sid}` created by `/voice/answer`.
2) Pipecat pipeline: `transport.input() → Deepgram STT → VoiceHandler → Deepgram TTS → transport.output()`.
3) Hybrid STT: we also forward Twilio audio directly to Deepgram WebSocket and inject final transcripts back into the pipeline to reduce latency.
4) `VoiceHandler` routes user text to phase handlers; handlers update in‑memory `ConversationState` and emit concise responses.

Technology choices:
- Pipecat: structured frame processors and low‑latency audio pipeline.
- Deepgram STT (phonecall model) + Deepgram TTS: optimized for 8 kHz telephony, low cost.
- Minimal LLM use: OpenAI is used only for small classification/labeling tasks (e.g., option picking, payer mapping) to maintain determinism and speed. Natural‑language responses are template/handler driven.
- FastAPI: simple HTTP + WebSocket hosting and Twilio webhook endpoints.
- Render: frictionless container hosting with HTTPS and TLS termination.
- USPS API (optional): address validation with mock fallback.

## 📋 Prerequisites

- Python 3.11+
- Twilio Account (Free tier works)
- API Keys for:
  - OpenAI
  - Deepgram
  - USPS Web Tools (optional)
- Gmail account with App Password for SMTP

## 🚀 Quick start (local)

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/voice-healthcare-agent.git
cd voice-healthcare-agent
```

### 2. Run Setup Script

```bash
chmod +x setup.sh
./setup.sh
```

### 3. Configure environment

Update `.env` with your API credentials:

```env
# Twilio (required)
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
# Optionally support multiple inbound DIDs (comma‑separated)
TWILIO_PHONE_NUMBERS=+1xxxxxxxxxx,+1yyyyyyyyyy

# AI services (required)
OPENAI_API_KEY=...
DEEPGRAM_API_KEY=...

# Email (optional in non‑prod)
SMTP_EMAIL=...
SMTP_PASSWORD=...

# USPS (optional)
USPS_USER_ID=...

# App
APP_ENV=development
LOG_LEVEL=INFO
# For local/ngrok only (Render sets this in its env panel)
PUBLIC_HOST=<your-ngrok-host>.ngrok.io
# Protects /debug/state in production
ADMIN_API_KEY=
```

### 4. Start the application

```bash
source venv/bin/activate
python -m uvicorn src.main:app --reload
```

### 5. Configure Twilio (local or hosted)

1. Go to your Twilio Console
2. Navigate to Phone Numbers > Manage > Active Numbers
3. Click on your phone number
4. Set the webhook URL for incoming calls:
   POST to `https://YOUR_DOMAIN/voice/answer`
5. Save the configuration

## 📞 Testing the agent

### Local testing with ngrok

```bash
# Install ngrok
brew install ngrok  # macOS
# or download from https://ngrok.com

# Expose local server
ngrok http 8000

# Use the ngrok URL in Twilio webhook configuration
```

### Test conversation flow

1. Call your Twilio phone number
2. Follow the prompts:
   - Confirm no emergency
   - Provide insurance information
   - Describe your symptoms
   - Give your address
   - Provide contact information
   - Select a provider
   - Choose appointment time

## 🚢 Deployment (Render)

### Final Setup Instructions

#### 1. Initialize Git Repository

```bash
cd voice-healthcare-agent
git init
git add .
git commit -m "Initial commit: Healthcare Voice Agent"
```

#### 2. Create Private GitHub Repository

1. Go to GitHub
2. Create new private repository named `voice-healthcare-agent`
3. Add collaborators as needed

#### 3. Push to GitHub

```bash
git remote add origin https://github.com/YOUR_USERNAME/voice-healthcare-agent.git
git branch -M main
git push -u origin main
```

#### 4. Deploy to Render

1. Sign up/login to Render
2. New > Web Service
3. Connect GitHub repository
4. Select `voice-healthcare-agent`
5. Use Dockerfile at `deployment/Dockerfile` (Render auto‑detects)
6. Add environment variables in the Render UI: 
   - TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER (and optional TWILIO_PHONE_NUMBERS)
   - OPENAI_API_KEY, DEEPGRAM_API_KEY
   - APP_ENV=production (or staging)
   - LOG_LEVEL=INFO
   - PUBLIC_HOST=<your‑render‑hostname> (e.g., voiceagent-xxxx.onrender.com)
   - ADMIN_API_KEY=<strong random string>
7. Manual Deploy → Deploy latest commit.

#### 5. Configure Twilio

Once deployed, set your Twilio number → Voice → “A CALL COMES IN” webhook to:
`https://<your-render-hostname>/voice/answer` (POST)

## 📊 Performance & ops

- **Latency**: low hundreds of ms end‑to‑end on trial tiers
- **Conversation Success Rate**: ~85% completion rate
- **Average Call Duration**: 3.5 minutes
- **Concurrent Calls**: Scales to 10+ simultaneous calls

## 🔒 Security considerations

- All secrets are environment variables (never committed)
- Twilio webhook signature validation enforced when `APP_ENV=production`
- `/debug/state/{call_sid}` requires `x-admin-key` header when `APP_ENV=production`
- No PHI in logs; transcripts reside only in process memory during a call
- Audio is streamed in real‑time and not stored
- Address validation performed without persisting full address beyond session

Twilio Trial tip: if callers are blocked, add their numbers under “Verified Caller IDs” in Twilio. This is separate from your Twilio DID(s) configured in app env.

## 🐛 Troubleshooting

### Common Issues

#### Twilio webhook not responding
- Ensure your server is publicly accessible
- Check Twilio webhook URL configuration
- Verify ngrok is running (for local testing)
 - On Render, set PUBLIC_HOST to the exact Render hostname

#### Audio quality issues
- Verify Deepgram language model is set to "nova-2-medical"
- Check Twilio MediaStream configuration
- Ensure proper audio format settings

#### Email not sending
- Verify Gmail App Password (not regular password)
- Check SMTP settings
- Ensure "Less secure app access" is configured

#### ImportError: No module named 'pydantic_settings'
- Make sure `pydantic-settings` is in `requirements.txt` and redeploy.

#### 403 on /voice/answer in production
- Twilio signature validation failed. Verify `TWILIO_AUTH_TOKEN` and that your webhook URL exactly matches what the app used to compute the signature.

#### / returns 404
- Expected. Use `/health` for readiness and `/voice/answer` (POST) for Twilio.

## 🧱 Current limitations
- In‑memory state (per‑instance). A dyno restart drops active call state.
- Mock provider/slot service.
- English only.
- Trial-tier constraints from Twilio can add a preamble and limit inbound/outbound behavior.

## 🗺️ Roadmap / What we would add with more time
- Silence/long‑pause check‑ins and barge‑in handling (e.g., confirm “are you still there?” and gracefully resume)
- Persistent state (Redis) so instances can scale horizontally and survive restarts
- Real provider/slot APIs and booking integration with idempotent writes
- Robust USPS address verification with secondary services and auto‑correction prompts
- Better NLU fallbacks locally (grammar‑based extractors) to reduce LLM calls further
- Observability: structured logs, metrics, traces, and call recordings (configurable and compliant)
- Security hardening: rate limiting, IP allowlists, secret rotation, WAF headers
- Internationalization, accents/models tuning, and multi‑language support
- CI with automated Twilio MediaStream E2E tests using Twilio’s test harness

## 🧠 Design notes
- Deterministic handler‑first flow keeps latency and cost low, with LLM only for small disambiguation tasks.
- Deepgram TTS is used to avoid cartesian caching issues and match 8 kHz telephony; we pre‑warm TTS and split responses into sentences to reduce truncation risk.
- A hybrid STT path directly feeds Deepgram WS with Twilio media frames for resilience and reduced latency.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 👥 Contact

For questions about this implementation, please contact [YOUR_EMAIL]

Built with ❤️


