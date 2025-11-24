"""Pipeline factory for creating VoiceAgent conversation pipelines.

This module handles the creation and configuration of the Pipecat processing
pipeline, including STT, TTS, and handler services.
"""
import asyncio
import time
import logging
import aiohttp
from deepgram import LiveOptions
from pipecat.pipeline.pipeline import Pipeline
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.deepgram.tts import DeepgramTTSService
from pipecat.transports.network.fastapi_websocket import FastAPIWebsocketTransport

from src.config.settings import get_settings
from src.core.conversation_state import state_manager
from src.handlers.voice_handler import VoiceHandler
from src.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def create_pipeline(call_sid: str, transport: FastAPIWebsocketTransport) -> Pipeline:
    """Create the main conversation pipeline with transport IO.

    Args:
        call_sid: Twilio call SID for this conversation
        transport: FastAPI WebSocket transport for audio I/O

    Returns:
        Configured Pipeline instance ready to run

    Raises:
        Exception: If any service creation fails
    """
    # NOTE: No OpenAI LLM service needed - VoiceHandler generates complete responses directly
    logger.debug(f"Skipping OpenAI LLM service - VoiceHandler handles responses directly for call {call_sid}")

    # Create Deepgram STT service
    stt_service = await _create_deepgram_stt(call_sid)

    # Create Deepgram TTS service
    tts_service = await _create_deepgram_tts(call_sid)

    # Create conversation state
    logger.debug(f"Creating conversation state for call {call_sid}")
    try:
        await state_manager.create_state(call_sid)
        logger.info(f"Conversation state created for call {call_sid}")
    except Exception as e:
        logger.error(f"Conversation state error for call {call_sid}: {e}")
        raise

    # Initialize main handler
    logger.debug(f"Creating voice handler for call {call_sid}")
    try:
        voice_handler = VoiceHandler(call_sid)
        logger.info(f"Voice handler created for call {call_sid}")
    except Exception as e:
        logger.error(f"Voice handler error for call {call_sid}: {e}")
        raise

    # Optionally run echo test pipeline when diagnostics enabled
    if getattr(settings, 'echo_test', False):
        logger.info(f"TEST PIPELINE ENABLED: audio will echo back directly for call {call_sid}")
        pipeline = Pipeline([
            transport.input(),
            transport.output(),
        ])
        return pipeline

    # Build pipeline with transport in/out
    logger.info(f"Assembling pipeline components for call {call_sid}")
    try:
        pipeline = Pipeline(
            [
                transport.input(),
                stt_service,
                voice_handler,
                tts_service,
                transport.output(),
            ]
        )
        logger.info(f"Pipeline assembled successfully for call {call_sid}")
    except Exception as e:
        logger.error(f"Pipeline assembly error for call {call_sid}: {e}")
        raise

    return pipeline


async def _create_deepgram_stt(call_sid: str) -> DeepgramSTTService:
    """Create and configure Deepgram STT service.

    Args:
        call_sid: Twilio call SID for logging context

    Returns:
        Configured DeepgramSTTService instance

    Raises:
        Exception: If STT service creation fails
    """
    logger.debug(f"Creating Deepgram STT service for call {call_sid}")
    logger.info(f"Creating Deepgram STT service for call {call_sid}")
    try:
        # Enable ALL debug logging for Deepgram
        deepgram_logger = logging.getLogger("pipecat.services.deepgram")
        deepgram_logger.setLevel(logging.DEBUG)

        # Configure Deepgram for telephony
        model_name = settings.deepgram_model
        live_options = LiveOptions(
            language="en-US",
            model=model_name,
            punctuate=True,
            interim_results=True,
            endpointing=settings.deepgram_endpointing_ms,
            smart_format=True,
            profanity_filter=False,
            redact=False,
            # Let Deepgram auto-detect encoding from stream bridging
            channels=1,
        )

        stt_service = DeepgramSTTService(
            api_key=settings.deepgram_api_key,
            sample_rate=8000,  # Match Twilio's sample rate
            live_options=live_options,
        )

        # Test Deepgram credentials immediately
        if not settings.deepgram_api_key or len(settings.deepgram_api_key) < 10:
            logger.warning(f"Deepgram API key appears invalid for call {call_sid}")
        else:
            logger.info(f"Deepgram API key format looks valid for call {call_sid}")

        logger.info(f"Deepgram configured for call {call_sid}: {model_name}, 8kHz, encoding={settings.deepgram_encoding}, endpointing={settings.deepgram_endpointing_ms}ms")
        logger.debug(f"Deepgram debug logging ENABLED for call {call_sid}")
        logger.info(f"Deepgram STT service created successfully for call {call_sid}")

        # Add callback to monitor Deepgram connection status
        original_connect = stt_service._connect

        async def debug_connect(*args, **kwargs):
            logger.debug(f"Deepgram connecting for call {call_sid}")
            try:
                result = await original_connect(*args, **kwargs)
                logger.info(f"Deepgram connection successful for call {call_sid}")
                return result
            except Exception as e:
                logger.error(f"Deepgram connection failed for {call_sid}: {e}")
                raise

        stt_service._connect = debug_connect
        return stt_service

    except Exception as e:
        logger.error(f"Deepgram STT service error for call {call_sid}: {e}")
        raise


async def _create_deepgram_tts(call_sid: str) -> DeepgramTTSService:
    """Create and configure Deepgram TTS service.

    Args:
        call_sid: Twilio call SID for logging context

    Returns:
        Configured DeepgramTTSService instance

    Raises:
        Exception: If TTS service creation fails
    """
    logger.info(f"Creating Deepgram TTS service for call {call_sid}")
    try:
        # Add debug logging for Deepgram TTS
        deepgram_logger = logging.getLogger("pipecat.services.deepgram")
        deepgram_logger.setLevel(logging.DEBUG)

        # Test Deepgram API key immediately
        logger.debug(f"Validating Deepgram TTS API key for call {call_sid}")
        if not settings.deepgram_api_key or len(settings.deepgram_api_key) < 20:
            logger.warning(f"Deepgram API key appears invalid for call {call_sid}")
        else:
            logger.info(f"Deepgram TTS API key format looks valid for call {call_sid}")

        # SIMPLE TTS FIX: Force fresh HTTP sessions without breaking framework
        logger.debug(f"Creating TTS with ANTI-CACHE session for call {call_sid}")

        # Create session with aggressive anti-caching
        tts_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(
                limit=1,
                force_close=True,  # Forces new connection each time
                use_dns_cache=False,  # No DNS caching
                enable_cleanup_closed=True
            ),
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
                'Connection': 'close'  # HTTP/1.1 close connection
            }
        )

        tts_service = DeepgramTTSService(
            aiohttp_session=tts_session,
            api_key=settings.deepgram_api_key,
            voice="aura-asteria-en",
            sample_rate=8000,
            encoding="linear16",
            container="none",
        )

        logger.info(f"TTS service with anti-cache session created for call {call_sid}")

        # Add debugging wrapper to monitor TTS frame processing
        original_process_frame = tts_service.process_frame

        async def debug_tts_process_frame(frame, direction):
            frame_type = type(frame).__name__
            logger.debug(f"TTS Service received {frame_type} (direction: {direction}) for call {call_sid}")

            if frame_type == "TextFrame":
                text_content = getattr(frame, 'text', '')[:50]
                logger.debug(f"TTS Received TextFrame: '{text_content}...' - processing with Deepgram for call {call_sid}")
            elif frame_type == "StartFrame":
                logger.debug(f"TTS Received StartFrame - should initialize and send TTSStartedFrame for call {call_sid}")
            elif frame_type == "TTSStartedFrame":
                logger.debug(f"TTS sending TTSStartedFrame downstream - VoiceHandler should receive this for call {call_sid}")
            elif frame_type == "TTSStoppedFrame":
                logger.debug(f"TTS sending TTSStoppedFrame downstream for call {call_sid}")
            elif frame_type == "AudioRawFrame":
                if not hasattr(debug_tts_process_frame, '_audio_count'):
                    debug_tts_process_frame._audio_count = 0
                debug_tts_process_frame._audio_count += 1
                if debug_tts_process_frame._audio_count == 1:
                    logger.info(f"TTS generating first audio frame - speech synthesis working for call {call_sid}")

            t0 = time.time()
            result = await original_process_frame(frame, direction)
            t1 = time.time()
            logger.debug(f"TTS process_frame duration for {frame_type}: {(t1 - t0)*1000:.1f} ms for call {call_sid}")

            if frame_type == "TextFrame":
                # measure time until BotStartedSpeaking arrives using a simple flag
                try:
                    setattr(debug_tts_process_frame, "_last_textframe_time", t0)
                except Exception:
                    pass
                logger.debug(f"TTS Processed TextFrame - should generate audio now for call {call_sid}")
            elif frame_type == "StartFrame":
                logger.debug(f"TTS Processed StartFrame - initialization complete for call {call_sid}")

            return result

        tts_service.process_frame = debug_tts_process_frame
        logger.debug(f"Enhanced TTS debug wrapper installed successfully for call {call_sid}")

        # Give TTS service time to fully initialize internal queues
        logger.debug(f"Allowing TTS service to fully initialize for call {call_sid}")
        await asyncio.sleep(0.5)  # Reduce startup delay for faster greeting

        logger.info(f"DeepgramTTSService created and initialized for call {call_sid}")
        logger.info(f"TTS Configuration for call {call_sid}: aura-asteria-en voice, 8kHz linear16, container=none (transport will convert)")
        logger.debug(f"Deepgram TTS debug logging ENABLED for call {call_sid}")

        return tts_service

    except Exception as e:
        logger.error(f"Deepgram TTS service error for call {call_sid}: {e}")
        raise
