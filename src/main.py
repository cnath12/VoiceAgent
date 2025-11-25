"""Main entry point for the healthcare voice agent."""
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import aiohttp

from src.config.settings import get_settings
from src.config.constants import RateLimitConfig
from src.core.conversation_state import state_manager
from src.core.shutdown import init_shutdown_handler, shutdown
from src.utils.logger import get_logger
from src.api.health import router as health_router
from src.api.metrics import router as metrics_router
from src.api.webhooks import (
    handle_incoming_call,
    handle_recording,
    is_production,
)
from src.api.websocket import handle_media_stream

logger = get_logger(__name__)
settings = get_settings()

# Rate limiter - uses remote IP address as key
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle with graceful shutdown and connection pooling.

    Creates a shared aiohttp.ClientSession with connection pooling that can be
    reused across all HTTP requests. This avoids creating new TCP connections
    for each request, significantly improving latency and reducing resource usage.

    Usage in services:
        from fastapi import Request
        session = request.app.state.http_session
        async with session.get(url) as response:
            ...
    """
    # Startup
    logger.info("Starting healthcare voice agent...")
    init_shutdown_handler()

    # Create shared HTTP session with connection pooling
    # - limit: Maximum number of connections to keep in the pool
    # - limit_per_host: Maximum connections per host (prevents overloading a single service)
    # - ttl_dns_cache: Cache DNS lookups for 5 minutes (reduces DNS overhead)
    # - keepalive_timeout: How long to keep idle connections alive
    connector = aiohttp.TCPConnector(
        limit=100,               # Total connection pool size
        limit_per_host=20,       # Max connections per host
        ttl_dns_cache=300,       # 5 minute DNS cache
        keepalive_timeout=30,    # Keep connections alive for 30s
    )
    app.state.http_session = aiohttp.ClientSession(
        connector=connector,
        timeout=aiohttp.ClientTimeout(total=30)  # 30 second timeout
    )
    logger.info("Shared HTTP session with connection pooling created")
    logger.info("Application started successfully")

    yield

    # Shutdown
    logger.info("Initiating graceful shutdown...")

    # Close the shared HTTP session
    if hasattr(app.state, "http_session"):
        await app.state.http_session.close()
        logger.info("Shared HTTP session closed")

    # Close the fallback HTTP session (if used)
    from src.utils.http_client import close_fallback_session
    await close_fallback_session()

    await shutdown()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Healthcare Voice Agent",
    description="AI-powered voice agent for healthcare appointment scheduling",
    version="1.0.0",
    lifespan=lifespan
)

# Add rate limiter to app state
app.state.limiter = limiter

# Add rate limit exceeded handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include health check router
app.include_router(health_router)

# Include Prometheus metrics router
app.include_router(metrics_router)


# Twilio webhook endpoints with rate limiting
@app.post("/voice/answer")
@limiter.limit(f"{RateLimitConfig.CALLS_PER_MINUTE}/minute")
async def voice_answer_endpoint(request: Request):
    """Handle incoming Twilio call webhook.

    Rate limited to prevent abuse.
    """
    return await handle_incoming_call(request)


@app.post("/voice/recording")
@limiter.limit(f"{RateLimitConfig.CALLS_PER_MINUTE}/minute")
async def voice_recording_endpoint(request: Request):
    """Handle Twilio recording callback webhook."""
    return await handle_recording(request)


# WebSocket endpoint for media streaming
# Note: WebSocket connections have their own connection limits via the transport layer
@app.websocket("/voice/stream/{call_sid}")
async def voice_stream_endpoint(websocket: WebSocket, call_sid: str):
    """Handle Twilio MediaStream WebSocket connection."""
    await handle_media_stream(websocket, call_sid)


# Debug endpoint with rate limiting
@app.get("/debug/state/{call_sid}")
@limiter.limit(f"{RateLimitConfig.DEBUG_PER_MINUTE}/minute")
async def get_conversation_state(call_sid: str, request: Request):
    """Return the conversation state for debugging.

    Args:
        call_sid: Twilio call SID
        request: FastAPI Request (for auth check)

    Returns:
        Dictionary containing conversation state data

    Raises:
        HTTPException: If admin key required but not provided/invalid
    """
    # Optional admin API key check (guard in production)
    if is_production():
        from fastapi import HTTPException
        api_key = settings.admin_api_key.strip()
        incoming = request.headers.get("x-admin-key", "").strip()
        if api_key and incoming != api_key:
            raise HTTPException(status_code=403, detail="Forbidden")

    state = await state_manager.get_state(call_sid)
    if not state:
        return {"error": "unknown call_sid"}

    # Pydantic model is JSON serializable via .model_dump()
    try:
        return state.model_dump()
    except Exception:
        # Fallback minimal dict
        return {
            "call_sid": state.call_sid,
            "phase": state.phase,
            "patient_info": state.patient_info.model_dump() if hasattr(state.patient_info, "model_dump") else str(state.patient_info),
            "transcript": state.transcript,
            "error_count": state.error_count,
        }


if __name__ == "__main__":
    import uvicorn
    import os

    # Use PORT from environment variable (Render provides this)
    port = int(os.environ.get("PORT", 8000))

    logger.info(f"Starting server on port {port}")

    # Run with the dynamic port
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
