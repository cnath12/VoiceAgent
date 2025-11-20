"""Main entry point for the healthcare voice agent."""
import asyncio
import json
import aiohttp
import time
import base64
from typing import Optional
from fastapi import FastAPI, Request, Response, HTTPException, WebSocket
from contextlib import asynccontextmanager

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.frames.frames import Frame
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.deepgram.stt import DeepgramSTTService
# ADD: Direct Deepgram client for STT (bypassing Pipecat issues)
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)
from pipecat.serializers.twilio import TwilioFrameSerializer

from twilio.request_validator import RequestValidator

from src.config.settings import get_settings
from src.core.conversation_state import state_manager
from src.handlers.voice_handler import VoiceHandler
from src.utils.logger import get_logger
from src.utils.structured_logging import log_pipeline_event
from src.api.health import router as health_router
import logging

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


def _is_production() -> bool:
    try:
        return settings.app_env.lower() == "production"
    except Exception:
        return False


async def _validate_twilio_request(request: Request) -> bool:
    """Validate Twilio webhook signature in production.

    Returns True if valid or validation is skipped (non-production), False otherwise.
    """
    if not _is_production():
        return True
    try:
        validator = RequestValidator(settings.twilio_auth_token)
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


async def create_pipeline(call_sid: str, transport: FastAPIWebsocketTransport) -> Pipeline:
    """Create the main conversation pipeline with transport IO."""

    # NOTE: No OpenAI LLM service needed - VoiceHandler generates complete responses directly
    logger.debug(f"Skipping OpenAI LLM service - VoiceHandler handles responses directly for call {call_sid}")

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
    except Exception as e:
        logger.error(f"Deepgram STT service error for call {call_sid}: {e}")
        raise

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
        
        # Switch to Deepgram TTS - optimized for telephony
        from pipecat.services.deepgram.tts import DeepgramTTSService

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

            if frame_type == "TextFrame":
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
    except Exception as e:
        logger.error(f"Deepgram TTS service error for call {call_sid}: {e}")
        raise

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


@app.post("/voice/answer")
async def handle_incoming_call(request: Request):
    """Handle incoming Twilio call from any configured number."""
    logger.debug("/voice/answer endpoint called")
    # Validate request signature in production
    if not await _validate_twilio_request(request):
        logger.warning("Twilio signature validation failed for /voice/answer")
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


@app.post("/voice/recording")
async def handle_recording(request: Request):
    """Handle recording callback from Twilio."""
    if not await _validate_twilio_request(request):
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


@app.websocket("/voice/stream/{call_sid}")
async def handle_media_stream(websocket: WebSocket, call_sid: str):
    """Handle Twilio MediaStream WebSocket connection."""
    logger.debug(f"WEBSOCKET DEBUG: Starting handler for {call_sid}")
    try:
        logger.debug(f"WebSocket connection attempt for call_sid: {call_sid}")
        logger.debug(f"Client: {websocket.client} for call {call_sid}")
        logger.debug(f"Headers: {dict(websocket.headers)} for call {call_sid}")
        logger.info(f"MediaStream connected for {call_sid}")

        # Accept WebSocket connection
        logger.debug(f"Accepting WebSocket connection for call {call_sid}")
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for call {call_sid}")
        # Twilio sends a JSON {"event":"start", "start": {..., "streamSid": ..., "callSid": ...}}
        # Robustly consume up to a few initial messages to extract streamSid without assuming order
        stream_sid = ""
        media_frame_count = 0
        try:
            for i in range(5):
                msg_text = await websocket.receive_text()
                preview = msg_text[:200]
                logger.debug(f"WS msg[{i}]: {preview}... for call {call_sid}")
                logger.debug(f"WS message[{i}] for {call_sid}: {msg_text}")
                try:
                    payload = json.loads(msg_text)
                    event_type = payload.get("event")

                    # Log media frames to verify audio data is flowing
                    if event_type == "media":
                        media_frame_count += 1
                        media_data = payload.get("media", {})
                        payload_data = media_data.get("payload", "")
                        logger.debug(f"MEDIA FRAME #{media_frame_count}: payload_len={len(payload_data)} bytes for call {call_sid}")
                        logger.debug(f"Media frame {media_frame_count} for {call_sid}: {len(payload_data)} bytes")

                except Exception as parse_error:
                    # Not JSON we care about; continue
                    logger.debug(f"Non-JSON message: {parse_error}")
                    continue

                if event_type == "start" or ("start" in payload and isinstance(payload["start"], dict)):
                    start_obj = payload.get("start", {})
                    stream_sid = start_obj.get("streamSid", "")
                    call_sid_ws = start_obj.get("callSid", call_sid)
                    logger.debug(f"Extracted stream_sid: {stream_sid} for call {call_sid}")
                    logger.debug(f"Extracted call_sid: {call_sid_ws}")
                    if call_sid_ws:
                        call_sid = call_sid_ws
                    break
        except Exception as e:
            logger.warning(f"Error while parsing initial WS messages: {e}")
            logger.warning(f"WS initial parse error for call {call_sid}: {e}")

        logger.debug(f"DEBUG: Deepgram model={settings.deepgram_model}, endpointing={settings.deepgram_endpointing_ms}ms for call {call_sid}")
        serializer = TwilioFrameSerializer(
            stream_sid=stream_sid,
            call_sid=call_sid,
            account_sid=settings.twilio_account_sid,
            auth_token=settings.twilio_auth_token,
        )
        if not stream_sid:
            logger.warning(f"No stream_sid extracted for {call_sid}. Downstream audio may fail.")
        else:
            logger.info(f"Twilio serializer initialized with stream_sid={stream_sid} for {call_sid}")

        # Disable VAD (pipecat.vad not available in this build). Deepgram endpointing handles finalization.
        vad_analyzer = None
        logger.info("VAD disabled; relying on Deepgram endpointing")

        # HYBRID FIX: Add direct Deepgram STT connection (bypassing Pipecat STT issues)
        logger.debug(f"Setting up DIRECT Deepgram STT connection (bypassing Pipecat) for call {call_sid}")
        direct_deepgram_client = DeepgramClient(settings.deepgram_api_key)
        direct_dg_connection = direct_deepgram_client.listen.asyncwebsocket.v("1")

        # Direct Deepgram options (from working fixed_tts_agent.py)
        direct_live_options = LiveOptions(
            model=settings.deepgram_model,
            encoding="mulaw",  # Twilio audio format
            sample_rate=8000,
            channels=1,
            interim_results=True,
            endpointing=settings.deepgram_endpointing_ms,
            smart_format=True
        )

        logger.info(f"Direct Deepgram STT connection ready for call {call_sid}")
        last_audio_time = time.time()

        # Direct Deepgram event handlers (from working fixed_tts_agent.py)
        async def on_deepgram_message(self, result, **kwargs):
            nonlocal last_audio_time
            last_audio_time = time.time()

            if result.channel.alternatives[0].transcript:
                sentence = result.channel.alternatives[0].transcript.strip()

                if result.is_final:
                    if sentence:
                        logger.info(f"Direct Deepgram final transcription: '{sentence}' for {call_sid}")
                        # TODO: Forward to VoiceHandler via TextFrame injection
                        await forward_transcription_to_pipeline(sentence)
                else:
                    if sentence:
                        logger.debug(f"Direct Deepgram interim transcription: '{sentence}' for call {call_sid}")

        async def on_deepgram_error(self, error, **kwargs):
            logger.error(f"Direct Deepgram error for {call_sid}: {error}")
            
        # Forward transcription to our existing pipeline
        pipeline_task = None  # Will be set after pipeline creation
        async def forward_transcription_to_pipeline(text: str):
            """Forward direct Deepgram transcription to VoiceHandler pipeline"""
            nonlocal pipeline_task
            try:
                if pipeline_task is None:
                    logger.warning(f"No pipeline_task available to forward transcription: '{text}' for call {call_sid}")
                    return
                from pipecat.frames.frames import TranscriptionFrame
                logger.debug(f"Forwarding transcription to pipeline: '{text}' for call {call_sid}")
                transcription_frame = TranscriptionFrame(text=text, user_id=call_sid, timestamp=time.time())
                await pipeline_task.queue_frame(transcription_frame)
                logger.debug(f"Queued TranscriptionFrame to pipeline for call {call_sid}")
            except Exception as e:
                logger.error(f"Failed forwarding transcription to pipeline for call {call_sid}: {e}")

        logger.debug(f"Creating FastAPIWebsocketTransport for {call_sid}")
        logger.debug(f"Transport params - audio_in: True, audio_out: True, vad: {vad_analyzer is not None} for call {call_sid}")
        logger.debug(f"Serializer: {type(serializer).__name__} with stream_sid: {stream_sid} for call {call_sid}")
        
        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=False,
                vad_analyzer=vad_analyzer,
                serializer=serializer,
                audio_in_sample_rate=8000,   # Match Twilio input sample rate
                audio_out_sample_rate=8000,  # Match Deepgram TTS output sample rate
                audio_in_channels=1,         # Mono audio for telephony
                audio_out_channels=1,        # Mono audio for telephony
            ),
        )
        logger.info(f"FastAPIWebsocketTransport created for {call_sid}")
        logger.info(f"Transport ready (audio_in/out enabled) for {call_sid}")

        # Enable debug logging for transport and services
        logging.getLogger("pipecat.transports.network.fastapi_websocket").setLevel(logging.DEBUG)
        # Keep transport debug, but avoid excessive STT debug spam in production
        logging.getLogger("pipecat.services.deepgram.stt").setLevel(logging.DEBUG)
        logger.debug(f"FastAPIWebsocketTransport debug enabled; Deepgram STT set to DEBUG (temporary) for call {call_sid}")

        # Create pipeline with transport IO
        logger.debug(f"Creating pipeline for call {call_sid}")
        try:
            pipeline = await create_pipeline(call_sid, transport)
            logger.info(f"Pipeline created successfully for call {call_sid}")
        except Exception as e:
            logger.error(f"CRITICAL ERROR in create_pipeline for call {call_sid}: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise

        # Create and run task
        logger.info(f"Creating pipeline task for call {call_sid}")
        task = PipelineTask(pipeline)
        logger.info(f"Pipeline task created for call {call_sid}")

        # HYBRID FIX: Set pipeline_task reference for transcription forwarding
        pipeline_task = task
        logger.debug(f"Pipeline task reference set for direct Deepgram forwarding for call {call_sid}")

        # CRITICAL: Send StartFrame to initialize all processors BEFORE starting runner
        from pipecat.frames.frames import StartFrame
        logger.debug(f"Sending StartFrame to initialize pipeline for call {call_sid}")
        await task.queue_frame(StartFrame())
        # Remove extra warm-up frames to reduce initial latency
        logger.debug(f"StartFrame queued for call {call_sid}")

        # HYBRID FIX: Start direct Deepgram connection (from fixed_tts_agent.py)
        logger.debug(f"Starting DIRECT Deepgram STT connection for call {call_sid}")
        direct_dg_connection.on(LiveTranscriptionEvents.Transcript, on_deepgram_message)
        direct_dg_connection.on(LiveTranscriptionEvents.Error, on_deepgram_error)
        await direct_dg_connection.start(direct_live_options)
        logger.info(f"Direct Deepgram STT connection started for call {call_sid}")
        
        # Aggressive keepalive task (from fixed_tts_agent.py)
        async def send_keepalive():
            nonlocal last_audio_time
            try:
                await asyncio.sleep(0.5)  # Brief delay to let connection settle
                await direct_dg_connection.keep_alive()
                logger.debug(f"Initial Deepgram KeepAlive sent for call {call_sid}")
            except Exception as e:
                logger.error(f"Initial KeepAlive error for call {call_sid}: {e}")

            while True:
                try:
                    current_time = time.time()
                    if current_time - last_audio_time > 2:
                        logger.debug(f"Sending Deepgram KeepAlive for call {call_sid} (last audio: {current_time - last_audio_time:.1f}s ago)")
                        await direct_dg_connection.keep_alive()
                    await asyncio.sleep(0.2)  # Check every 2 seconds
                except Exception as e:
                    logger.error(f"KeepAlive error for call {call_sid}: {e}")
                    break

        keepalive_task = asyncio.create_task(send_keepalive())
        logger.debug(f"Deepgram keepalive task started for call {call_sid}")

        # Remove greeting scheduling here; VoiceHandler will produce the greeting

        global runner
        runner = PipelineRunner()
        logger.info(f"Starting pipeline runner for call {call_sid}")

        # Let FastAPIWebsocketTransport consume all remaining messages
        logger.debug(f"Ready to start pipeline runner - FastAPIWebsocketTransport will handle all remaining messages for call {call_sid}")

        # HYBRID FIX: Enhanced WebSocket monitoring with direct Deepgram audio forwarding
        logger.debug(f"Adding WebSocket message monitoring + audio forwarding for {call_sid}")
        original_receive_text = websocket.receive_text
        async def debug_receive_text():
            nonlocal last_audio_time
            try:
                message = await original_receive_text()
                try:
                    payload = json.loads(message)
                    event_type = payload.get("event", "unknown")
                    if event_type == "media":
                        media_data = payload.get("media", {})
                        payload_data = media_data.get("payload", "")

                        # CRITICAL: Forward audio to direct Deepgram (from fixed_tts_agent.py)
                        if payload_data:
                            try:
                                audio_chunk = base64.b64decode(payload_data)
                                await direct_dg_connection.send(audio_chunk)
                                last_audio_time = time.time()  # Update for keepalive
                            except Exception as e:
                                logger.error(f"Failed to forward audio to direct Deepgram for call {call_sid}: {e}")

                        # Reduced logging - only log every 100th frame to avoid spam
                        if int(media_data.get('timestamp', 0)) % 2000 == 0:  # Every 2 seconds
                            logger.debug(f"AUDIO FLOWING: payload_len={len(payload_data)} bytes, timestamp={media_data.get('timestamp', 'N/A')} -> Deepgram for call {call_sid}")
                    elif event_type == "start":
                        start = payload.get("start", {})
                        fmt = start.get("mediaFormat", {})
                        if fmt:
                            logger.debug(f"Twilio start.mediaFormat: {fmt} for call {call_sid}")
                    elif event_type not in ["connected", "start"]:
                        logger.debug(f"WS Event: {event_type} for call {call_sid}")
                except Exception:
                    logger.debug(f"Non-JSON WS message: {message[:100]}... for call {call_sid}")
                return message
            except Exception as e:
                logger.warning(f"WebSocket receive error for call {call_sid}: {e}")
                raise
        websocket.receive_text = debug_receive_text

        try:
            logger.info(f"About to call runner.run(task) for {call_sid}")

            # Let VoiceHandler send greeting naturally when TTS is ready
            logger.info(f"VoiceHandler will send greeting when TTS service signals readiness for call {call_sid}")

            await runner.run(task)
            logger.info(f"Pipeline runner finished normally for {call_sid}")
        except asyncio.CancelledError:
            logger.warning(f"Pipeline runner cancelled for {call_sid}")
            raise
        except Exception as e:
            logger.error(f"Pipeline runner error for {call_sid}: {e}")
            raise
        finally:
            # Send EndFrame to properly close pipeline and stop all processors
            logger.debug(f"Sending EndFrame to close pipeline for {call_sid}")
            try:
                from pipecat.frames.frames import EndFrame
                await task.queue_frame(EndFrame())
                logger.info(f"EndFrame sent to pipeline for {call_sid}")
                await asyncio.sleep(0.5)  # Give time for processors to cleanup
            except Exception as e:
                logger.error(f"Error sending EndFrame for {call_sid}: {e}")

            # HYBRID FIX: Cleanup direct Deepgram connection and keepalive
            logger.debug(f"Cleaning up direct Deepgram connection for {call_sid}")
            try:
                if 'keepalive_task' in locals():
                    keepalive_task.cancel()
                    logger.debug(f"Keepalive task cancelled for call {call_sid}")
            except Exception as e:
                logger.warning(f"Keepalive cleanup error for call {call_sid}: {e}")

            try:
                await direct_dg_connection.finish()
                logger.debug(f"Direct Deepgram connection closed for call {call_sid}")
            except Exception as e:
                logger.warning(f"Deepgram cleanup error for call {call_sid}: {e}")

    except Exception as e:
        logger.error(f"Error in media stream for {call_sid}: {e}")
    finally:
        await state_manager.cleanup_state(call_sid)
        logger.info(f"MediaStream disconnected for {call_sid}")


@app.get("/debug/state/{call_sid}")
async def get_conversation_state(call_sid: str, request: Request):
    """Return the in-memory conversation state for debugging."""
    # Optional admin API key check (guard in production)
    if _is_production():
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
        "src.main:app",  # or just app if running directly
        host="0.0.0.0",
        port=port,
        log_level="info"
    )