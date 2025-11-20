"""Prometheus metrics endpoint for VoiceAgent.

Exposes application metrics in Prometheus format for scraping.
"""

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter()


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.

    Returns:
        Response: Metrics data in Prometheus format

    Example:
        ```
        curl http://localhost:8000/metrics
        ```

    Metrics exposed:
        - voiceagent_active_calls: Current active calls
        - voiceagent_calls_total: Total calls handled
        - voiceagent_call_duration_seconds: Call duration histogram
        - voiceagent_pipeline_processing_seconds: Pipeline processing time
        - voiceagent_deepgram_stt_latency_seconds: STT latency
        - voiceagent_deepgram_tts_latency_seconds: TTS latency
        - voiceagent_openai_latency_seconds: OpenAI API latency
        - voiceagent_state_operations_total: State management operations
        - voiceagent_redis_connected: Redis connection status
        - ... and many more (see src/utils/metrics.py)
    """
    metrics_data = generate_latest()
    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST
    )
