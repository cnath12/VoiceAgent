"""Main entry point for the healthcare voice agent."""
from typing import Optional
from fastapi import FastAPI, Request, WebSocket
from contextlib import asynccontextmanager

from pipecat.pipeline.runner import PipelineRunner

from src.config.settings import get_settings
from src.core.conversation_state import state_manager
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

# Global pipeline runner
runner: Optional[PipelineRunner] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Starting healthcare voice agent...")
    yield
    logger.info("Shutting down healthcare voice agent...")
    if runner:
        try:
            stop = getattr(runner, "stop", None)
            if callable(stop):
                await stop()
        except Exception:
            # Runner is already finished or stop() is unavailable
            pass


app = FastAPI(lifespan=lifespan)

# Include health check router
app.include_router(health_router)

# Include Prometheus metrics router
app.include_router(metrics_router)


# Twilio webhook endpoints
@app.post("/voice/answer")
async def voice_answer_endpoint(request: Request):
    """Handle incoming Twilio call webhook."""
    return await handle_incoming_call(request)


@app.post("/voice/recording")
async def voice_recording_endpoint(request: Request):
    """Handle Twilio recording callback webhook."""
    return await handle_recording(request)


# WebSocket endpoint for media streaming
@app.websocket("/voice/stream/{call_sid}")
async def voice_stream_endpoint(websocket: WebSocket, call_sid: str):
    """Handle Twilio MediaStream WebSocket connection."""
    await handle_media_stream(websocket, call_sid)


# Debug endpoint
@app.get("/debug/state/{call_sid}")
async def get_conversation_state(call_sid: str, request: Request):
    """Return the conversation state for debugging.

    Args:
        call_sid: Twilio call SID
        request: FastAPI Request (for auth check)

    Returns:
        Dictionary containing conversation state data
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
