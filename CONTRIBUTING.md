# Contributing to VoiceAgent

Thank you for your interest in contributing to VoiceAgent! This guide will help you get started with development.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Making Changes](#making-changes)
- [Debugging](#debugging)
- [Common Tasks](#common-tasks)

---

## Development Setup

### Prerequisites

- **Python 3.11** or higher
- **Redis** (optional, for state management - future feature)
- **ngrok** (required for local Twilio testing)
- **Git** for version control

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/cnath12/VoiceAgent.git
   cd VoiceAgent
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   # Production dependencies
   pip install -r requirements.txt

   # Development dependencies (linting, testing, etc.)
   pip install -r requirements-dev.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and credentials
   ```

   Required variables:
   - `TWILIO_ACCOUNT_SID` - Your Twilio account SID
   - `TWILIO_AUTH_TOKEN` - Your Twilio auth token
   - `TWILIO_PHONE_NUMBER` - Your Twilio phone number
   - `OPENAI_API_KEY` - Your OpenAI API key
   - `DEEPGRAM_API_KEY` - Your Deepgram API key

   Optional variables:
   - `SMTP_EMAIL` / `SMTP_PASSWORD` - For email confirmations
   - `USPS_USER_ID` - For address validation
   - `LOG_LEVEL` - Set to `DEBUG` for verbose logging

5. **Verify installation**
   ```bash
   python -c "import src; print('Installation successful!')"
   ```

---

## Project Structure

```
VoiceAgent/
├── src/
│   ├── api/                 # API endpoints and routers
│   │   └── health.py       # Health check endpoints
│   ├── config/             # Configuration management
│   │   ├── settings.py     # Pydantic settings
│   │   ├── prompts.py      # Conversation prompts
│   │   └── constants.py    # Application constants
│   ├── core/               # Core business logic
│   │   ├── models.py       # Pydantic data models
│   │   ├── conversation_state.py  # State management
│   │   └── validators.py   # Input validation
│   ├── handlers/           # Phase-specific handlers
│   │   ├── voice_handler.py       # Main orchestrator
│   │   ├── insurance_handler.py   # Insurance collection
│   │   ├── symptom_handler.py     # Symptom collection
│   │   ├── demographics_handler.py # Address/contact
│   │   └── scheduling_handler.py  # Appointment scheduling
│   ├── services/           # External service integrations
│   │   ├── llm_service.py         # OpenAI wrapper
│   │   ├── email_service.py       # SMTP emails
│   │   ├── provider_service.py    # Provider matching
│   │   └── address_service.py     # USPS validation
│   ├── utils/              # Utility functions
│   │   └── logger.py       # Logging configuration
│   └── main.py             # FastAPI application entry point
├── tests/                  # Test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── conftest.py        # Pytest fixtures
├── deployment/            # Deployment configurations
│   ├── Dockerfile
│   └── render.yaml
├── .env.example           # Example environment variables
├── requirements.txt       # Production dependencies
├── requirements-dev.txt   # Development dependencies
├── pytest.ini            # Pytest configuration
└── Makefile              # Common development tasks
```

---

## Running Tests

### Run all tests
```bash
pytest
```

### Run specific test types
```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage report
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/handlers/test_insurance_handler.py

# Run specific test function
pytest tests/unit/handlers/test_insurance_handler.py::test_insurance_collection
```

### View coverage report
```bash
# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Open in browser (macOS)
open htmlcov/index.html

# Open in browser (Linux)
xdg-open htmlcov/index.html
```

### Test markers
```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only smoke tests (fast validation)
pytest -m smoke

# Skip slow tests
pytest -m "not slow"
```

---

## Code Style

We follow PEP 8 and use automated tools for consistency.

### Linting and Formatting

```bash
# Format code with black
black src/ tests/

# Sort imports with isort
isort src/ tests/

# Lint with ruff
ruff check src/ tests/

# Type checking with mypy
mypy src/

# Run all checks
make lint  # or manually run all the above
```

### Pre-commit Hooks (Recommended)

```bash
# Install pre-commit hooks
pre-commit install

# Run on all files
pre-commit run --all-files
```

### Code Style Guidelines

1. **Type Hints**: Use type hints for all function signatures
   ```python
   # Good
   async def process_input(self, user_input: str, state: ConversationState) -> str:
       ...

   # Bad
   async def process_input(self, user_input, state):
       ...
   ```

2. **Docstrings**: Use Google-style docstrings
   ```python
   def calculate_score(value: int, threshold: int = 10) -> float:
       """Calculate normalized score.

       Args:
           value: The raw value to normalize
           threshold: The normalization threshold

       Returns:
           Normalized score between 0 and 1

       Raises:
           ValueError: If threshold is zero
       """
       ...
   ```

3. **Logging**: Use structured logging, not print()
   ```python
   # Good
   logger.info("Processing transcription", extra={
       "call_sid": call_sid,
       "text": text[:50]
   })

   # Bad
   print(f"🗣️ USER SAID: {text}")
   ```

4. **Constants**: Extract magic numbers to `config/constants.py`
   ```python
   # Good
   from src.config.constants import PipelineConfig
   await asyncio.sleep(PipelineConfig.TTS_INIT_DELAY_SEC)

   # Bad
   await asyncio.sleep(0.5)  # magic number
   ```

---

## Making Changes

### Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/bug-description
   ```

2. **Make your changes**
   - Write code
   - Add tests
   - Update documentation

3. **Run tests locally**
   ```bash
   # Run all tests
   pytest

   # Run linting
   ruff check src/ tests/
   mypy src/
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   ```

   Commit message format:
   - `feat:` - New feature
   - `fix:` - Bug fix
   - `docs:` - Documentation changes
   - `test:` - Test additions/changes
   - `refactor:` - Code refactoring
   - `perf:` - Performance improvements
   - `chore:` - Maintenance tasks

5. **Push and create PR**
   ```bash
   git push -u origin feature/your-feature-name
   ```

### Code Review Checklist

Before submitting a PR, ensure:
- [ ] All tests pass (`pytest`)
- [ ] Code is formatted (`black`, `isort`)
- [ ] Linting passes (`ruff check`)
- [ ] Type checking passes (`mypy`)
- [ ] Coverage hasn't decreased
- [ ] Documentation is updated
- [ ] Commit messages are clear
- [ ] No sensitive data in commits

---

## Debugging

### Local Development

1. **Start the server**
   ```bash
   # With auto-reload
   uvicorn src.main:app --reload --log-level debug

   # Or use the Makefile
   make run
   ```

2. **Expose with ngrok**
   ```bash
   ngrok http 8000
   ```

   Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`) and configure it in Twilio:
   - Twilio Console → Phone Numbers → Your Number
   - Voice & Fax → A CALL COMES IN
   - Webhook: `https://abc123.ngrok.io/voice/answer`

3. **Test with a real call**
   - Call your Twilio number
   - Watch the console for logs
   - Check `http://localhost:8000/debug/state/{call_sid}` for state

### VS Code Debugging

1. **Install recommended extensions**
   - Python
   - Pylance
   - Python Debugger

2. **Use launch configuration**
   Create `.vscode/launch.json`:
   ```json
   {
     "version": "0.2.0",
     "configurations": [
       {
         "name": "FastAPI",
         "type": "python",
         "request": "launch",
         "module": "uvicorn",
         "args": [
           "src.main:app",
           "--reload",
           "--log-level", "debug"
         ],
         "envFile": "${workspaceFolder}/.env",
         "console": "integratedTerminal"
       },
       {
         "name": "Pytest",
         "type": "python",
         "request": "launch",
         "module": "pytest",
         "args": ["-v"],
         "console": "integratedTerminal"
       }
     ]
   }
   ```

3. **Set breakpoints and debug**
   - Press F5 to start debugging
   - Set breakpoints in your code
   - Make a test call

### Common Debug Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Detailed health check
curl http://localhost:8000/health/detailed

# Get conversation state (requires ADMIN_API_KEY in production)
curl -H "x-admin-key: your-key" \
  http://localhost:8000/debug/state/CA1234567890abcdef
```

### Debugging Tips

1. **Enable debug logging**
   ```bash
   export LOG_LEVEL=DEBUG
   uvicorn src.main:app --reload
   ```

2. **Check Twilio logs**
   - Twilio Console → Monitor → Logs → Calls
   - Look for webhook errors

3. **Test individual components**
   ```python
   # In Python REPL
   from src.handlers.insurance_handler import InsuranceHandler
   from src.core.conversation_state import state_manager

   handler = InsuranceHandler("test-call-sid")
   # Test handler logic
   ```

4. **Use ipdb for interactive debugging**
   ```python
   import ipdb; ipdb.set_trace()
   ```

---

## Common Tasks

### Run the application
```bash
make run
# or
uvicorn src.main:app --reload
```

### Run tests
```bash
make test
# or
pytest
```

### Run linting
```bash
make lint
# or
ruff check src/ tests/
mypy src/
```

### Format code
```bash
make format
# or
black src/ tests/
isort src/ tests/
```

### Clean generated files
```bash
make clean
# Removes __pycache__, .pytest_cache, htmlcov, .coverage
```

### Build Docker image
```bash
docker build -t voiceagent -f deployment/Dockerfile .
```

### Run with Docker
```bash
docker run -p 8000:8000 --env-file .env voiceagent
```

---

## Getting Help

- **Documentation**: See `README.md`, `ARCHITECTURE_DETAILED.md`, `IMPROVEMENT_ANALYSIS.md`
- **Issues**: Check existing issues or create a new one
- **Questions**: Reach out to the maintainers

---

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pipecat Documentation](https://github.com/pipecat-ai/pipecat)
- [Twilio Voice Documentation](https://www.twilio.com/docs/voice)
- [Deepgram API Documentation](https://developers.deepgram.com/)
- [Pytest Documentation](https://docs.pytest.org/)

---

Thank you for contributing to VoiceAgent! 🎉
