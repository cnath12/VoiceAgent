"""Prometheus metrics for VoiceAgent application.

This module defines and exports all Prometheus metrics used throughout
the application for monitoring and observability.

Metrics Categories:
- Call Metrics: Track call lifecycle and outcomes
- Pipeline Metrics: Track processing pipeline performance
- State Management: Track conversation state operations
- External Services: Track third-party API latencies and errors
- TTS/STT Metrics: Track speech processing performance
"""

from prometheus_client import Counter, Histogram, Gauge, Info
from src.config.constants import MetricsConfig

# =============================================================================
# Application Info
# =============================================================================

app_info = Info('voiceagent_app', 'VoiceAgent application information')
app_info.info({
    'version': '1.0.0',
    'environment': 'production',
    'description': 'Healthcare voice AI agent'
})

# =============================================================================
# Call Metrics
# =============================================================================

# Active calls gauge
active_calls = Gauge(
    'voiceagent_active_calls',
    'Number of currently active phone calls'
)

# Total calls counter
total_calls = Counter(
    'voiceagent_calls_total',
    'Total number of calls handled',
    ['status']  # Labels: success, error, cancelled
)

# Call duration histogram
call_duration = Histogram(
    'voiceagent_call_duration_seconds',
    'Duration of phone calls in seconds',
    buckets=MetricsConfig.CALL_DURATION_BUCKETS
)

# Calls by phase counter
calls_by_phase = Counter(
    'voiceagent_calls_by_phase_total',
    'Number of calls reaching each conversation phase',
    ['phase']  # GREETING, INSURANCE, CHIEF_COMPLAINT, etc.
)

# Call completion rate
call_completions = Counter(
    'voiceagent_call_completions_total',
    'Calls that reached COMPLETE phase',
    ['success']  # true/false
)

# =============================================================================
# Pipeline Metrics
# =============================================================================

# Pipeline processing time
pipeline_processing_time = Histogram(
    'voiceagent_pipeline_processing_seconds',
    'Time spent processing frames in the pipeline',
    ['frame_type'],  # TextFrame, AudioFrame, etc.
    buckets=MetricsConfig.LATENCY_BUCKETS
)

# Pipeline errors
pipeline_errors = Counter(
    'voiceagent_pipeline_errors_total',
    'Total number of pipeline processing errors',
    ['error_type', 'component']  # component: stt, tts, handler, transport
)

# Frame processing counter
frames_processed = Counter(
    'voiceagent_frames_processed_total',
    'Total number of frames processed',
    ['frame_type', 'direction']  # direction: inbound, outbound
)

# =============================================================================
# State Management Metrics
# =============================================================================

# State operations counter
state_operations = Counter(
    'voiceagent_state_operations_total',
    'Total number of state management operations',
    ['operation', 'backend']  # operation: create, get, update, cleanup; backend: redis, memory
)

# State operation duration
state_operation_duration = Histogram(
    'voiceagent_state_operation_duration_seconds',
    'Duration of state management operations',
    ['operation', 'backend'],
    buckets=MetricsConfig.LATENCY_BUCKETS
)

# Redis connection status
redis_connected = Gauge(
    'voiceagent_redis_connected',
    'Redis connection status (1=connected, 0=disconnected)'
)

# State cache hits/misses
state_cache_hits = Counter(
    'voiceagent_state_cache_hits_total',
    'Number of state cache hits'
)

state_cache_misses = Counter(
    'voiceagent_state_cache_misses_total',
    'Number of state cache misses'
)

# =============================================================================
# External Service Metrics
# =============================================================================

# Deepgram STT metrics
deepgram_stt_requests = Counter(
    'voiceagent_deepgram_stt_requests_total',
    'Total Deepgram STT requests',
    ['status']  # success, error
)

deepgram_stt_latency = Histogram(
    'voiceagent_deepgram_stt_latency_seconds',
    'Deepgram STT transcription latency',
    buckets=MetricsConfig.LATENCY_BUCKETS
)

# Deepgram TTS metrics
deepgram_tts_requests = Counter(
    'voiceagent_deepgram_tts_requests_total',
    'Total Deepgram TTS requests',
    ['status']  # success, error
)

deepgram_tts_latency = Histogram(
    'voiceagent_deepgram_tts_latency_seconds',
    'Deepgram TTS synthesis latency',
    buckets=MetricsConfig.LATENCY_BUCKETS
)

# OpenAI LLM metrics
openai_requests = Counter(
    'voiceagent_openai_requests_total',
    'Total OpenAI API requests',
    ['model', 'status']  # model: gpt-4, gpt-3.5-turbo; status: success, error
)

openai_latency = Histogram(
    'voiceagent_openai_latency_seconds',
    'OpenAI API request latency',
    ['model'],
    buckets=MetricsConfig.LATENCY_BUCKETS
)

openai_tokens = Counter(
    'voiceagent_openai_tokens_total',
    'Total OpenAI tokens consumed',
    ['model', 'token_type']  # token_type: prompt, completion
)

# Twilio metrics
twilio_webhooks = Counter(
    'voiceagent_twilio_webhooks_total',
    'Total Twilio webhook calls',
    ['webhook_type', 'status']  # webhook_type: answer, stream, recording
)

twilio_errors = Counter(
    'voiceagent_twilio_errors_total',
    'Total Twilio API errors',
    ['error_type']
)

# SMTP/Email metrics
email_sent = Counter(
    'voiceagent_emails_sent_total',
    'Total emails sent',
    ['status']  # success, error
)

email_latency = Histogram(
    'voiceagent_email_send_latency_seconds',
    'Email sending latency',
    buckets=MetricsConfig.LATENCY_BUCKETS
)

# USPS Address Validation metrics
usps_requests = Counter(
    'voiceagent_usps_requests_total',
    'Total USPS address validation requests',
    ['status']  # success, error
)

usps_latency = Histogram(
    'voiceagent_usps_latency_seconds',
    'USPS API request latency',
    buckets=MetricsConfig.LATENCY_BUCKETS
)

# =============================================================================
# TTS/STT Performance Metrics
# =============================================================================

# Transcription metrics
transcriptions = Counter(
    'voiceagent_transcriptions_total',
    'Total transcriptions received',
    ['is_final', 'source']  # is_final: true/false; source: pipecat, direct
)

transcription_confidence = Histogram(
    'voiceagent_transcription_confidence',
    'Transcription confidence scores',
    buckets=[0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0]
)

# TTS synthesis metrics
tts_syntheses = Counter(
    'voiceagent_tts_syntheses_total',
    'Total TTS synthesis operations',
    ['status']  # success, error
)

tts_character_count = Counter(
    'voiceagent_tts_characters_total',
    'Total characters synthesized by TTS'
)

# Audio processing metrics
audio_frames_processed = Counter(
    'voiceagent_audio_frames_total',
    'Total audio frames processed',
    ['direction']  # inbound, outbound
)

audio_processing_errors = Counter(
    'voiceagent_audio_errors_total',
    'Total audio processing errors',
    ['error_type']
)

# =============================================================================
# Business Logic Metrics
# =============================================================================

# Insurance provider distribution
insurance_providers = Counter(
    'voiceagent_insurance_providers_total',
    'Distribution of insurance providers',
    ['provider']  # Blue Cross, Aetna, etc.
)

# Chief complaints distribution
chief_complaints = Counter(
    'voiceagent_chief_complaints_total',
    'Distribution of chief complaints',
    ['complaint_category']  # respiratory, cardiac, etc.
)

# Appointment scheduling
appointments_scheduled = Counter(
    'voiceagent_appointments_scheduled_total',
    'Total appointments scheduled',
    ['status']  # success, failed
)

# PHI redaction metrics
phi_redactions = Counter(
    'voiceagent_phi_redactions_total',
    'Total PHI redaction operations',
    ['phi_type']  # ssn, phone, email, address, etc.
)

# =============================================================================
# Error Tracking
# =============================================================================

# HTTP errors
http_requests = Counter(
    'voiceagent_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# WebSocket errors
websocket_errors = Counter(
    'voiceagent_websocket_errors_total',
    'Total WebSocket errors',
    ['error_type']
)

# Validation errors
validation_errors = Counter(
    'voiceagent_validation_errors_total',
    'Total validation errors',
    ['field', 'validation_type']
)

# =============================================================================
# Helper Functions
# =============================================================================

def increment_call_phase(phase: str) -> None:
    """Increment counter for calls reaching a specific phase."""
    calls_by_phase.labels(phase=phase).inc()


def track_external_request(service: str, duration: float, success: bool) -> None:
    """Track external service request metrics.

    Args:
        service: Name of the service (openai, deepgram_stt, deepgram_tts, etc.)
        duration: Request duration in seconds
        success: Whether the request succeeded
    """
    status = 'success' if success else 'error'

    if service == 'openai':
        openai_requests.labels(model='gpt-4', status=status).inc()
        openai_latency.labels(model='gpt-4').observe(duration)
    elif service == 'deepgram_stt':
        deepgram_stt_requests.labels(status=status).inc()
        deepgram_stt_latency.observe(duration)
    elif service == 'deepgram_tts':
        deepgram_tts_requests.labels(status=status).inc()
        deepgram_tts_latency.observe(duration)
    elif service == 'usps':
        usps_requests.labels(status=status).inc()
        usps_latency.observe(duration)


def track_state_operation(operation: str, backend: str, duration: float) -> None:
    """Track state management operation metrics.

    Args:
        operation: Type of operation (create, get, update, cleanup)
        backend: State backend (redis, memory)
        duration: Operation duration in seconds
    """
    state_operations.labels(operation=operation, backend=backend).inc()
    state_operation_duration.labels(operation=operation, backend=backend).observe(duration)


def track_frame_processing(frame_type: str, direction: str, duration: float) -> None:
    """Track pipeline frame processing metrics.

    Args:
        frame_type: Type of frame (TextFrame, AudioRawFrame, etc.)
        direction: Direction of processing (inbound, outbound)
        duration: Processing duration in seconds
    """
    frames_processed.labels(frame_type=frame_type, direction=direction).inc()
    pipeline_processing_time.labels(frame_type=frame_type).observe(duration)
