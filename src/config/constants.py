"""Configuration constants for the voice agent.

This module centralizes all magic numbers and configuration values
used throughout the application for better maintainability.
"""

# ============================================================================
# PIPELINE CONFIGURATION
# ============================================================================

class PipelineConfig:
    """Pipeline and audio processing configuration."""

    # TTS Initialization
    TTS_INIT_DELAY_SEC = 0.5
    """Delay to allow TTS service to fully initialize"""

    TTS_WARMUP_DELAY_SEC = 0.15
    """Delay for TTS warmup before first TextFrame"""

    TTS_RETRY_DELAY_SEC = 0.5
    """Delay before retrying failed TTS push"""

    # Audio Configuration
    AUDIO_SAMPLE_RATE = 8000
    """Sample rate for telephony audio (Hz)"""

    AUDIO_CHANNELS = 1
    """Mono audio for telephony"""

    # Keepalive Settings
    KEEPALIVE_INTERVAL_SEC = 0.2
    """Interval for checking keepalive conditions"""

    KEEPALIVE_THRESHOLD_SEC = 2.0
    """Send keepalive if no audio for this many seconds"""

    KEEPALIVE_INITIAL_DELAY_SEC = 0.5
    """Initial delay before first keepalive"""

    # Shutdown
    SHUTDOWN_CLEANUP_DELAY_SEC = 0.5
    """Time to allow processors to cleanup on shutdown"""


# ============================================================================
# CONVERSATION CONFIGURATION
# ============================================================================

class ConversationConfig:
    """Conversation flow and interaction settings."""

    # Repetition Prevention
    MAX_SAME_RESPONSE_COUNT = 2
    """Maximum times to repeat the same question"""

    # Context Window
    MAX_CONVERSATION_HISTORY = 6
    """Maximum conversation exchanges to keep in context"""

    # Error Handling
    MAX_ERROR_COUNT = 3
    """Maximum errors before escalation"""

    # Retry Logic
    MAX_RETRY_ATTEMPTS = 3
    """Maximum retry attempts for validation"""


# ============================================================================
# EMAIL CONFIGURATION
# ============================================================================

class EmailConfig:
    """Email service configuration."""

    # Retry Settings
    MAX_RETRY_ATTEMPTS = 3
    """Maximum email send retry attempts"""

    RETRY_BASE_DELAY_SEC = 2
    """Base delay for exponential backoff (seconds)"""

    # SMTP Settings
    SMTP_TIMEOUT_SEC = 30
    """SMTP connection timeout"""


# ============================================================================
# LLM CONFIGURATION
# ============================================================================

class LLMConfig:
    """LLM service configuration."""

    # Model Settings
    DEFAULT_MODEL = "gpt-3.5-turbo"
    """Default OpenAI model for general responses"""

    # Temperature Settings
    TEMPERATURE_DETERMINISTIC = 0.0
    """Temperature for classification (deterministic)"""

    TEMPERATURE_LOW = 0.1
    """Temperature for extraction tasks"""

    TEMPERATURE_MEDIUM = 0.7
    """Temperature for conversational responses"""

    # Token Limits
    MAX_TOKENS_CLASSIFICATION = 60
    """Max tokens for classification tasks"""

    MAX_TOKENS_EXTRACTION = 100
    """Max tokens for information extraction"""

    MAX_TOKENS_RESPONSE = 150
    """Max tokens for conversational responses"""

    # Penalty Settings
    PRESENCE_PENALTY = 0.3
    """Presence penalty for response generation"""

    FREQUENCY_PENALTY = 0.3
    """Frequency penalty for response generation"""


# ============================================================================
# API TIMEOUTS
# ============================================================================

class APITimeouts:
    """Timeout configuration for external API calls."""

    # USPS API
    USPS_TIMEOUT_SEC = 5
    """Timeout for USPS address validation"""

    # Deepgram API
    DEEPGRAM_CONNECTION_TIMEOUT_SEC = 10
    """Timeout for Deepgram connection establishment"""

    # OpenAI API
    OPENAI_TIMEOUT_SEC = 30
    """Timeout for OpenAI API calls"""

    # HTTP Client
    HTTP_TOTAL_TIMEOUT_SEC = 30
    """Total timeout for HTTP requests"""


# ============================================================================
# WEBSOCKET CONFIGURATION
# ============================================================================

class WebSocketConfig:
    """WebSocket handling configuration."""

    # Message Handling
    INITIAL_MESSAGE_COUNT = 5
    """Number of initial messages to parse for stream_sid"""

    # Media Frame Logging
    MEDIA_FRAME_LOG_INTERVAL = 2000
    """Log media frame every N milliseconds"""

    # Graceful Shutdown
    GRACEFUL_SHUTDOWN_TIMEOUT_SEC = 30
    """Maximum time to wait for active calls to finish"""

    SHUTDOWN_CHECK_INTERVAL_SEC = 1
    """Interval for checking shutdown status"""


# ============================================================================
# VALIDATION CONFIGURATION
# ============================================================================

class ValidationConfig:
    """Input validation settings."""

    # Phone Number
    PHONE_MIN_LENGTH = 10
    """Minimum phone number length"""

    PHONE_MAX_LENGTH = 15
    """Maximum phone number length"""

    # Member ID
    MEMBER_ID_MIN_LENGTH = 5
    """Minimum insurance member ID length"""

    # ZIP Code
    ZIP_CODE_SHORT_LENGTH = 5
    """Standard ZIP code length"""

    ZIP_CODE_LONG_LENGTH = 9
    """ZIP+4 code length"""

    # API Key Validation
    API_KEY_MIN_LENGTH = 20
    """Minimum API key length for validation"""


# ============================================================================
# HEALTH CHECK CONFIGURATION
# ============================================================================

class HealthCheckConfig:
    """Health check settings."""

    # Timeout for dependency checks
    DEPENDENCY_CHECK_TIMEOUT_SEC = 5
    """Timeout for individual dependency health checks"""

    # Cache TTL
    HEALTH_CHECK_CACHE_TTL_SEC = 10
    """Cache health check results for this many seconds"""


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

class LoggingConfig:
    """Logging configuration."""

    # Message Preview
    MAX_LOG_TEXT_LENGTH = 50
    """Maximum text length for log previews"""

    MAX_LOG_MESSAGE_LENGTH = 200
    """Maximum message length for WebSocket logs"""

    # Audio Logging
    AUDIO_FRAME_LOG_COUNT = 100
    """Log every Nth audio frame to reduce spam"""


# ============================================================================
# CACHE CONFIGURATION
# ============================================================================

class CacheConfig:
    """Caching configuration."""

    # Provider Cache
    PROVIDER_CACHE_TTL_SEC = 300
    """Cache provider data for 5 minutes"""

    PROVIDER_CACHE_MAX_SIZE = 100
    """Maximum number of cached provider entries"""

    # Settings Cache
    DNS_CACHE_TTL_SEC = 300
    """DNS cache TTL for HTTP connections"""


# ============================================================================
# HTTP CONNECTION POOL CONFIGURATION
# ============================================================================

class ConnectionPoolConfig:
    """HTTP connection pool settings."""

    # Pool Limits
    TOTAL_CONNECTIONS = 100
    """Total connection pool size"""

    CONNECTIONS_PER_HOST = 10
    """Max connections per host"""

    # Timeouts
    KEEPALIVE_TIMEOUT_SEC = 60
    """Connection keepalive timeout"""


# ============================================================================
# RATE LIMITING CONFIGURATION
# ============================================================================

class RateLimitConfig:
    """Rate limiting settings."""

    # API Endpoints
    CALLS_PER_MINUTE = 10
    """Maximum calls per minute per IP for /voice/answer"""

    WEBSOCKET_PER_MINUTE = 20
    """Maximum WebSocket connections per minute per IP"""

    DEBUG_PER_MINUTE = 30
    """Maximum debug endpoint calls per minute"""


# ============================================================================
# METRICS CONFIGURATION
# ============================================================================

class MetricsConfig:
    """Metrics and monitoring configuration."""

    # Histogram Buckets
    LATENCY_BUCKETS = [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    """Histogram buckets for latency metrics (seconds)"""

    # Call Duration Buckets
    CALL_DURATION_BUCKETS = [30, 60, 120, 180, 300, 600]
    """Histogram buckets for call duration (seconds)"""
