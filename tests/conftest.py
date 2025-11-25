"""Pytest configuration and shared fixtures."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.core.models import ConversationState, PatientInfo, Insurance
from src.core.conversation_state import ConversationStateManager


@pytest.fixture
def mock_settings():
    """Mock settings for testing with valid format values."""
    from src.config.settings import Settings

    settings = Settings(
        # Twilio - must start with AC and be 30+ chars
        twilio_account_sid="AC" + "a" * 32,
        twilio_auth_token="a" * 32,  # SecretStr, 30+ chars
        twilio_phone_number="+15555555555",
        # API keys - must be 20+ chars
        openai_api_key="sk-" + "a" * 48,  # OpenAI format
        deepgram_api_key="a" * 40,
        app_env="testing",
        smtp_email="test@example.com",
        smtp_password="test_password_123456"
    )
    return settings


@pytest.fixture
def test_call_sid():
    """Test call SID."""
    return "CA1234567890abcdef"


@pytest.fixture
async def conversation_state(test_call_sid):
    """Create a test conversation state."""
    state = ConversationState(call_sid=test_call_sid)
    return state


@pytest.fixture
async def state_manager():
    """Create a fresh state manager for each test."""
    manager = ConversationStateManager()
    yield manager
    # Cleanup after test
    manager._states.clear()


@pytest.fixture
def sample_patient_info():
    """Sample patient information for testing."""
    return PatientInfo(
        insurance=Insurance(
            payer_name="Blue Cross Blue Shield",
            member_id="ABC123456"
        ),
        chief_complaint="headache",
        symptom_duration="3 days",
        urgency_level=5,
        phone_number="5551234567",
        email="patient@example.com"
    )


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client."""
    mock = AsyncMock()
    mock.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[
                MagicMock(
                    message=MagicMock(content="Test response")
                )
            ]
        )
    )
    return mock


@pytest.fixture
def mock_deepgram_client():
    """Mock Deepgram client."""
    mock = AsyncMock()
    return mock


@pytest.fixture
def mock_twilio_client():
    """Mock Twilio client."""
    mock = MagicMock()
    return mock
