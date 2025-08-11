# 🏗️ Architecture

## System Overview

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Caller    │────▶│    Twilio    │────▶│  FastAPI    │
└─────────────┘     └──────────────┘     └─────────────┘
                           │                      │
                    MediaStream              Pipecat
                           │                 Pipeline
                           ▼                      │
                    ┌──────────────┐              ▼
                    │  WebSocket   │     ┌─────────────┐
                    └──────────────┘     │   Handlers  │
                                         └─────────────┘
                                                 │
                    ┌────────────────────────────┴───┐
                    ▼                ▼               ▼
             ┌──────────┐    ┌──────────┐    ┌──────────┐
             │ Deepgram │    │  OpenAI  │    │ Cartesia │
             │   STT    │    │   LLM    │    │   TTS    │
             └──────────┘    └──────────┘    └──────────┘
```

## 📁 Project Structure

```
voice-healthcare-agent/
├── src/
│   ├── config/         # Configuration and prompts
│   ├── core/           # Core models and state management
│   ├── handlers/       # Conversation phase handlers
│   ├── services/       # External service integrations
│   ├── utils/          # Utilities and logging
│   └── main.py         # Application entry point
├── tests/              # Unit tests
├── deployment/         # Docker and deployment configs
├── logs/               # Application logs
└── README.md           # This file
```

## 🧪 Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_conversation_flow.py -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html
```

## 🚢 Deployment

### Deploy to Render

1. Fork this repository
2. Connect your GitHub account to Render
3. Create a new Web Service
4. Select this repository
5. Use the render.yaml configuration
6. Add environment variables in Render dashboard
7. Deploy!

### Manual Docker Deployment

```bash
# Build image
docker build -f deployment/Dockerfile -t healthcare-voice-agent .

# Run container
docker run -p 8000:8000 --env-file .env healthcare-voice-agent
```