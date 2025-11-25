"""Twilio webhook handlers for VoiceAgent.

This module handles incoming Twilio webhooks including call initiation
and recording callbacks.
"""
from fastapi import Request, Response, HTTPException
from twilio.request_validator import RequestValidator

from src.config.settings import get_settings
from src.utils.logger import get_logger
from src.utils.metrics import twilio_webhooks

logger = get_logger(__name__)
settings = get_settings()


def is_production() -> bool:
    """Check if running in production environment.

    Returns:
        True if app_env is 'production', False otherwise
    """
    try:
        return settings.app_env.lower() == "production"
    except Exception:
        return False


async def validate_twilio_request(request: Request) -> bool:
    """Validate Twilio webhook signature in production.

    Args:
        request: FastAPI Request object

    Returns:
        True if valid or validation is skipped (non-production), False otherwise
    """
    if not is_production():
        return True
    try:
        validator = RequestValidator(settings.get_twilio_auth_token())
        # Build expected URL using https and the effective host
        configured_host = settings.public_host.strip()
        header_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        host = configured_host or header_host or request.url.hostname
        scheme = request.headers.get("x-forwarded-proto", "https")
        expected_url = f"{scheme}://{host}{request.url.path}"
        # Read form data for validation
        form = await request.form()
        params = dict(form)
        signature = request.headers.get("x-twilio-signature", "")
        return bool(validator.validate(expected_url, params, signature))
    except Exception:
        return False


async def handle_incoming_call(request: Request) -> Response:
    """Handle incoming Twilio call from any configured number.

    Args:
        request: FastAPI Request object with Twilio webhook data

    Returns:
        Response with TwiML directing Twilio to connect to WebSocket stream

    Raises:
        HTTPException: If Twilio signature validation fails
    """
    logger.debug("/voice/answer endpoint called")

    # Track webhook call
    twilio_webhooks.labels(webhook_type='answer', status='received').inc()

    # Validate request signature in production
    if not await validate_twilio_request(request):
        logger.warning("Twilio signature validation failed for /voice/answer")
        twilio_webhooks.labels(webhook_type='answer', status='auth_failed').inc()
        raise HTTPException(status_code=403, detail="Forbidden")

    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    from_number = form_data.get("From", "")
    to_number = form_data.get("To", "")
    logger.debug(f"Call {call_sid} from {from_number} to {to_number}")

    logger.info(f"Incoming call: {call_sid} from {from_number} to {to_number}")
    try:
        logger.debug(f"Full Twilio form payload: {dict(form_data)}")
    except Exception:
        pass

    # Optional: Verify the dialed number belongs to our configured list
    try:
        allowed = settings.phone_numbers_list
        if to_number and allowed and to_number not in allowed:
            logger.warning(f"Call to unconfigured number: {to_number} (allowed: {allowed})")
    except Exception:
        # Non-fatal; proceed
        pass

    # Determine public host for Twilio Stream
    configured_host = settings.public_host.strip()
    header_host = request.headers.get('x-forwarded-host') or request.headers.get('host')
    host = configured_host or header_host or request.url.hostname
    stream_url = f"wss://{host}/voice/stream/{call_sid}"
    logger.info(f"Using stream URL: {stream_url}")

    # TwiML: simplified; only connect the stream
    twiml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
    <Response>
        <Connect>
            <Stream url=\"{stream_url}\" />
        </Connect>
    </Response>"""
    logger.debug(f"Generated TwiML for {call_sid}: {twiml}")

    return Response(content=twiml, media_type="application/xml")


async def handle_recording(request: Request) -> Response:
    """Handle recording callback from Twilio.

    Args:
        request: FastAPI Request object with recording callback data

    Returns:
        Response with TwiML thanking the caller and hanging up

    Raises:
        HTTPException: If Twilio signature validation fails
    """
    if not await validate_twilio_request(request):
        logger.warning("Twilio signature validation failed for /voice/recording")
        raise HTTPException(status_code=403, detail="Forbidden")

    form_data = await request.form()
    recording_url = form_data.get("RecordingUrl", "")
    call_sid = form_data.get("CallSid", "")

    logger.info(f"Recording received for call {call_sid}: {recording_url}")

    twiml = """<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say voice="alice">Thank you for your response. Our system is working correctly. This concludes the test call.</Say>
        <Hangup/>
    </Response>"""

    return Response(content=twiml, media_type="application/xml")
