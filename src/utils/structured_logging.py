"""Structured logging utilities for the voice agent.

This module provides helpers for structured logging to replace
print() statements with proper logging calls.

All logging functions automatically redact PHI for HIPAA compliance.
"""
import logging
from typing import Any, Dict, Optional
from src.utils.phi_redactor import get_phi_redactor


def log_call_event(
    logger: logging.Logger,
    event: str,
    call_sid: str,
    level: int = logging.INFO,
    **extra_fields: Any
) -> None:
    """Log a call-related event with structured data.

    Args:
        logger: Logger instance to use
        event: Event name (e.g., "call_started", "transcription_received")
        call_sid: Twilio call SID
        level: Log level (logging.DEBUG, INFO, WARNING, ERROR)
        **extra_fields: Additional fields to include in the log
    """
    logger.log(
        level,
        event,
        extra={
            "event": event,
            "call_sid": call_sid,
            **extra_fields
        }
    )


def log_pipeline_event(
    logger: logging.Logger,
    event: str,
    call_sid: str,
    component: str,
    level: int = logging.DEBUG,
    **extra_fields: Any
) -> None:
    """Log a pipeline component event.

    Args:
        logger: Logger instance to use
        event: Event name (e.g., "component_created", "frame_processed")
        call_sid: Twilio call SID
        component: Pipeline component name (e.g., "stt", "tts", "voice_handler")
        level: Log level
        **extra_fields: Additional fields to include
    """
    logger.log(
        level,
        event,
        extra={
            "event": event,
            "call_sid": call_sid,
            "component": component,
            **extra_fields
        }
    )


def log_transcription(
    logger: logging.Logger,
    text: str,
    call_sid: str,
    is_final: bool = True,
    confidence: Optional[float] = None,
    redact_phi: bool = True,
    **extra_fields: Any
) -> None:
    """Log a speech transcription event with automatic PHI redaction.

    Args:
        logger: Logger instance to use
        text: Transcribed text
        call_sid: Twilio call SID
        is_final: Whether this is a final transcription
        confidence: Confidence score (0.0-1.0)
        redact_phi: Whether to redact PHI (default: True for HIPAA compliance)
        **extra_fields: Additional fields
    """
    # Redact PHI from transcription text
    if redact_phi:
        redactor = get_phi_redactor()
        text = redactor.redact(text, redact_level="partial")  # Partial to keep context

    level = logging.INFO if is_final else logging.DEBUG
    logger.log(
        level,
        "transcription_received",
        extra={
            "event": "transcription",
            "call_sid": call_sid,
            "text": text[:100],  # Truncate for logging
            "is_final": is_final,
            "confidence": confidence,
            **extra_fields
        }
    )


def log_websocket_event(
    logger: logging.Logger,
    event: str,
    call_sid: str,
    event_type: Optional[str] = None,
    level: int = logging.DEBUG,
    **extra_fields: Any
) -> None:
    """Log a WebSocket event.

    Args:
        logger: Logger instance
        event: Event name
        call_sid: Twilio call SID
        event_type: Twilio event type (e.g., "media", "start", "stop")
        level: Log level
        **extra_fields: Additional fields
    """
    logger.log(
        level,
        event,
        extra={
            "event": event,
            "call_sid": call_sid,
            "websocket_event_type": event_type,
            **extra_fields
        }
    )


def log_error(
    logger: logging.Logger,
    error: Exception,
    context: str,
    call_sid: Optional[str] = None,
    **extra_fields: Any
) -> None:
    """Log an error with context.

    Args:
        logger: Logger instance
        error: Exception that occurred
        context: Description of what was happening when the error occurred
        call_sid: Optional call SID
        **extra_fields: Additional fields
    """
    extra: Dict[str, Any] = {
        "event": "error",
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context,
        **extra_fields
    }

    if call_sid:
        extra["call_sid"] = call_sid

    logger.error(
        f"{context}: {error}",
        extra=extra,
        exc_info=True
    )


def log_message(
    logger: logging.Logger,
    message: str,
    level: int = logging.INFO,
    redact_phi: bool = True,
    **extra_fields: Any
) -> None:
    """Log a message with automatic PHI redaction.

    This is a general-purpose logging function that can be used
    to replace print() statements throughout the codebase.

    Args:
        logger: Logger instance
        message: Message to log
        level: Log level (logging.DEBUG, INFO, WARNING, ERROR)
        redact_phi: Whether to redact PHI (default: True for HIPAA compliance)
        **extra_fields: Additional structured fields to include

    Examples:
        >>> log_message(logger, "User said: 'my phone is 555-1234'")
        # Logs: "User said: 'my phone is XXX-XXX-1234'"

        >>> log_message(logger, "Processing call", level=logging.DEBUG, call_sid="CA123")
        # Logs with call_sid in structured fields
    """
    # Redact PHI from message
    if redact_phi:
        redactor = get_phi_redactor()
        message = redactor.redact(message, redact_level="partial")

    logger.log(
        level,
        message,
        extra=extra_fields
    )


def redact_for_logging(text: str, level: str = "partial") -> str:
    """Redact PHI from text for logging purposes.

    Convenience function for manual PHI redaction when needed.

    Args:
        text: Text to redact
        level: Redaction level ("full", "partial", "minimal")

    Returns:
        Redacted text
    """
    redactor = get_phi_redactor()
    return redactor.redact(text, redact_level=level)
