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
# Removed CartesiaTTSService - using DeepgramTTSService instead
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
    print(f"🔧 Skipping OpenAI LLM service - VoiceHandler handles responses directly")

    print(f"🔧 Creating Deepgram STT service...")
    logger.info(f"Creating Deepgram STT service for call {call_sid}")
    try:
        from deepgram import LiveOptions
        
        # Enable ALL debug logging for Deepgram
        import logging
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
            print(f"⚠️ WARNING: Deepgram API key appears invalid!")
            logger.warning(f"Deepgram API key appears invalid for call {call_sid}")
        else:
            print(f"✅ Deepgram API key format looks valid")
        
        print(f"🎤 Deepgram configured: {model_name}, 8kHz, encoding={settings.deepgram_encoding}, endpointing={settings.deepgram_endpointing_ms}ms")
        print(f"🔍 Deepgram debug logging ENABLED")
        print(f"✅ Deepgram STT service created!")
        logger.info(f"Deepgram STT service created successfully for call {call_sid}")
        
        # Add callback to monitor Deepgram connection status
        original_connect = stt_service._connect
        async def debug_connect(*args, **kwargs):
            print(f"🔌 Deepgram connecting...")
            try:
                result = await original_connect(*args, **kwargs)
                print(f"✅ Deepgram connection successful!")
                return result
            except Exception as e:
                print(f"❌ Deepgram connection failed: {e}")
                logger.error(f"Deepgram connection failed for {call_sid}: {e}")
                raise
        stt_service._connect = debug_connect
    except Exception as e:
        print(f"❌ Deepgram STT service error: {e}")
        logger.error(f"Deepgram STT service error for call {call_sid}: {e}")
        raise

    print(f"🔧 Creating DeepgramTTSService...")
    logger.info(f"Creating Deepgram TTS service for call {call_sid}")
    try:
        # Add debug logging for Deepgram TTS  
        import logging
        deepgram_logger = logging.getLogger("pipecat.services.deepgram")
        deepgram_logger.setLevel(logging.DEBUG)
        
        # Test Deepgram API key immediately
        print(f"🔑 Validating Deepgram TTS API key...")
        if not settings.deepgram_api_key or len(settings.deepgram_api_key) < 20:
            print(f"⚠️ WARNING: Deepgram API key appears invalid!")
            logger.warning(f"Deepgram API key appears invalid for call {call_sid}")
        else:
            print(f"✅ Deepgram TTS API key format looks valid")
        
        # Switch to Deepgram TTS - optimized for telephony 
        from pipecat.services.deepgram.tts import DeepgramTTSService
        
        # SIMPLE TTS FIX: Force fresh HTTP sessions without breaking framework
        print(f"🔧 Creating TTS with ANTI-CACHE session")
        
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
        
        print(f"🚀 TTS service with anti-cache session created")
        
        # Add debugging wrapper to monitor TTS frame processing
        original_process_frame = tts_service.process_frame
        async def debug_tts_process_frame(frame, direction):
            frame_type = type(frame).__name__
            print(f"🔍 TTS Service received {frame_type} (direction: {direction})")
            
            if frame_type == "TextFrame":
                text_content = getattr(frame, 'text', '')[:50]
                print(f"🔤 TTS Received TextFrame: '{text_content}...' - processing with Deepgram")
            elif frame_type == "StartFrame":
                print(f"🚀 TTS Received StartFrame - should initialize and send TTSStartedFrame")
            elif frame_type == "TTSStartedFrame":
                print(f"📡 TTS sending TTSStartedFrame downstream - VoiceHandler should receive this!")
            elif frame_type == "TTSStoppedFrame":
                print(f"🛑 TTS sending TTSStoppedFrame downstream")
            elif frame_type == "AudioRawFrame":
                if not hasattr(debug_tts_process_frame, '_audio_count'):
                    debug_tts_process_frame._audio_count = 0
                debug_tts_process_frame._audio_count += 1
                if debug_tts_process_frame._audio_count == 1:
                    print(f"🎵 TTS generating first audio frame - speech synthesis working!")
                
            import time as _time
            t0 = _time.time()
            result = await original_process_frame(frame, direction)
            t1 = _time.time()
            print(f"⏱️ TTS process_frame duration for {frame_type}: {(t1 - t0)*1000:.1f} ms")
            if frame_type == "TextFrame":
                # measure time until BotStartedSpeaking arrives using a simple flag
                try:
                    setattr(debug_tts_process_frame, "_last_textframe_time", t0)
                except Exception:
                    pass
            
            if frame_type == "TextFrame":
                print(f"📢 TTS Processed TextFrame - should generate audio now")
            elif frame_type == "StartFrame":
                print(f"✅ TTS Processed StartFrame - initialization complete")
                
            return result
        tts_service.process_frame = debug_tts_process_frame
        print(f"🔍 Enhanced TTS debug wrapper installed successfully")
        
        # Give TTS service time to fully initialize internal queues
        print(f"⏳ Allowing TTS service to fully initialize...")
        import asyncio
        await asyncio.sleep(0.5)  # Reduce startup delay for faster greeting
        
        print(f"✅ DeepgramTTSService created and initialized!")
        print(f"🎯 TTS Configuration: aura-asteria-en voice, 8kHz linear16, container=none (transport will convert)")
        print(f"🔍 Deepgram TTS debug logging ENABLED")
        logger.info(f"Deepgram TTS service created successfully for call {call_sid}")
    except Exception as e:
        print(f"❌ DeepgramTTSService error: {e}")
        logger.error(f"Deepgram TTS service error for call {call_sid}: {e}")
        raise

    # Create conversation state
    print(f"🔧 Creating conversation state...")
    try:
        await state_manager.create_state(call_sid)
        print(f"✅ Conversation state created!")
    except Exception as e:
        print(f"❌ Conversation state error: {e}")
        raise

    # Initialize main handler
    print(f"🔧 Creating voice handler...")
    try:
        voice_handler = VoiceHandler(call_sid)
        print(f"✅ Voice handler created!")
    except Exception as e:
        print(f"❌ Voice handler error: {e}")
        raise

    # Optionally run echo test pipeline when diagnostics enabled
    from src.config.settings import get_settings as _get_settings
    _s = _get_settings()
    if getattr(_s, 'echo_test', False):
        print(f"🔊 TEST PIPELINE ENABLED: audio will echo back directly")
        pipeline = Pipeline([
            transport.input(),
            transport.output(),
        ])
        return pipeline

    # Build pipeline with transport in/out
    print(f"🔧 Assembling pipeline components...")
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
        print(f"✅ Pipeline assembled successfully!")
        logger.info(f"Pipeline assembled successfully for call {call_sid}")
    except Exception as e:
        print(f"❌ Pipeline assembly error: {e}")
        logger.error(f"Pipeline assembly error for call {call_sid}: {e}")
        raise

    return pipeline


@app.post("/voice/answer")
async def handle_incoming_call(request: Request):
    """Handle incoming Twilio call from any configured number."""
    print(f"🚨 IMMEDIATE DEBUG: /voice/answer endpoint called!")
    # Validate request signature in production
    if not await _validate_twilio_request(request):
        logger.warning("Twilio signature validation failed for /voice/answer")
        raise HTTPException(status_code=403, detail="Forbidden")
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    from_number = form_data.get("From", "")
    to_number = form_data.get("To", "")
    print(f"🚨 IMMEDIATE DEBUG: Call {call_sid} from {from_number} to {to_number}")

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
    print(f"🚨🚨 WEBSOCKET DEBUG: Starting handler for {call_sid}")
    try:
        print(f"🔗 WebSocket connection attempt for call_sid: {call_sid}")
        print(f"🔗 Client: {websocket.client}")
        print(f"🔗 Headers: {dict(websocket.headers)}")
        logger.info(f"MediaStream connected for {call_sid}")
        
        # Accept WebSocket connection
        print(f"🔗 Accepting WebSocket connection...")
        await websocket.accept()
        print(f"✅ WebSocket connection accepted!")
        # Twilio sends a JSON {"event":"start", "start": {..., "streamSid": ..., "callSid": ...}}
        # Robustly consume up to a few initial messages to extract streamSid without assuming order
        stream_sid = ""
        media_frame_count = 0
        try:
            for i in range(5):
                msg_text = await websocket.receive_text()
                preview = msg_text[:200]
                print(f"🔍 WS msg[{i}]: {preview}...")
                logger.debug(f"WS message[{i}] for {call_sid}: {msg_text}")
                try:
                    payload = json.loads(msg_text)
                    event_type = payload.get("event")
                    
                    # Log media frames to verify audio data is flowing
                    if event_type == "media":
                        media_frame_count += 1
                        media_data = payload.get("media", {})
                        payload_data = media_data.get("payload", "")
                        print(f"📡 MEDIA FRAME #{media_frame_count}: payload_len={len(payload_data)} bytes")
                        logger.debug(f"Media frame {media_frame_count} for {call_sid}: {len(payload_data)} bytes")
                        
                except Exception as parse_error:
                    # Not JSON we care about; continue
                    logger.debug(f"Non-JSON message: {parse_error}")
                    continue
                    
                if event_type == "start" or ("start" in payload and isinstance(payload["start"], dict)):
                    start_obj = payload.get("start", {})
                    stream_sid = start_obj.get("streamSid", "")
                    call_sid_ws = start_obj.get("callSid", call_sid)
                    print(f"🔍 Extracted stream_sid: {stream_sid}")
                    print(f"🔍 Extracted call_sid: {call_sid_ws}")
                    if call_sid_ws:
                        call_sid = call_sid_ws
                    break
        except Exception as e:
            logger.warning(f"Error while parsing initial WS messages: {e}")
            print(f"⚠️ WS initial parse error: {e}")

        print(f"🔊 DEBUG: Deepgram model={settings.deepgram_model}, endpointing={settings.deepgram_endpointing_ms}ms")
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

        # 🔧 HYBRID FIX: Add direct Deepgram STT connection (bypassing Pipecat STT issues)
        print(f"🔧 Setting up DIRECT Deepgram STT connection (bypassing Pipecat)")
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
        
        print(f"✅ Direct Deepgram STT connection ready")
        last_audio_time = time.time()
        
        # 🔧 Direct Deepgram event handlers (from working fixed_tts_agent.py)
        async def on_deepgram_message(self, result, **kwargs):
            nonlocal last_audio_time
            last_audio_time = time.time()
            
            if result.channel.alternatives[0].transcript:
                sentence = result.channel.alternatives[0].transcript.strip()
                
                if result.is_final:
                    if sentence:
                        print(f"🗣️ DIRECT DEEPGRAM FINAL: User said: '{sentence}'")
                        logger.info(f"Direct Deepgram final transcription: '{sentence}' for {call_sid}")
                        # TODO: Forward to VoiceHandler via TextFrame injection
                        await forward_transcription_to_pipeline(sentence)
                else:
                    if sentence:
                        print(f"🎤 DIRECT DEEPGRAM INTERIM: '{sentence}'")

        async def on_deepgram_error(self, error, **kwargs):
            print(f"❌ Direct Deepgram error: {error}")
            logger.error(f"Direct Deepgram error for {call_sid}: {error}")
            
        # Forward transcription to our existing pipeline
        pipeline_task = None  # Will be set after pipeline creation
        async def forward_transcription_to_pipeline(text: str):
            """Forward direct Deepgram transcription to VoiceHandler pipeline"""
            nonlocal pipeline_task
            try:
                if pipeline_task is None:
                    print(f"⚠️ No pipeline_task available to forward transcription: '{text}'")
                    return
                from pipecat.frames.frames import TranscriptionFrame
                print(f"🚀 Forwarding transcription to pipeline: '{text}'")
                transcription_frame = TranscriptionFrame(text=text, user_id=call_sid, timestamp=time.time())
                await pipeline_task.queue_frame(transcription_frame)
                print(f"✅ Queued TranscriptionFrame to pipeline")
            except Exception as e:
                print(f"❌ Failed forwarding transcription to pipeline: {e}")

        print(f"🔧 Creating FastAPIWebsocketTransport for {call_sid}...")
        print(f"🔍 Transport params - audio_in: True, audio_out: True, vad: {vad_analyzer is not None}")
        print(f"🔍 Serializer: {type(serializer).__name__} with stream_sid: {stream_sid}")
        
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
        print(f"✅ FastAPIWebsocketTransport created for {call_sid}")
        logger.info(f"Transport ready (audio_in/out enabled) for {call_sid}")
        
        # Enable debug logging for transport and services
        import logging
        logging.getLogger("pipecat.transports.network.fastapi_websocket").setLevel(logging.DEBUG)
        # Keep transport debug, but avoid excessive STT debug spam in production
        logging.getLogger("pipecat.services.deepgram.stt").setLevel(logging.DEBUG)
        print(f"🔍 FastAPIWebsocketTransport debug enabled; Deepgram STT set to DEBUG (temporary)")

        # Create pipeline with transport IO
        print(f"🔧 Creating pipeline...")
        print(f"🚨 PIPELINE DEBUG: About to call create_pipeline({call_sid}, transport)")
        try:
            pipeline = await create_pipeline(call_sid, transport)
            print(f"✅ Pipeline created successfully!")
        except Exception as e:
            print(f"🚨🚨 CRITICAL ERROR in create_pipeline: {e}")
            print(f"🚨 Error type: {type(e).__name__}")
            import traceback
            print(f"🚨 Full traceback: {traceback.format_exc()}")
            logger.error(f"Pipeline creation failed: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

        # Create and run task
        print(f"🔧 Creating pipeline task...")
        logger.info(f"Creating pipeline task for call {call_sid}")
        task = PipelineTask(pipeline)
        print(f"✅ Pipeline task created!")
        logger.info(f"Pipeline task created for call {call_sid}")
        
        # 🔧 HYBRID FIX: Set pipeline_task reference for transcription forwarding
        pipeline_task = task
        print(f"✅ Pipeline task reference set for direct Deepgram forwarding")
        
        # CRITICAL: Send StartFrame to initialize all processors BEFORE starting runner
        from pipecat.frames.frames import StartFrame
        print(f"🚀 Sending StartFrame to initialize pipeline...")
        await task.queue_frame(StartFrame())
        # Remove extra warm-up frames to reduce initial latency
        print(f"✅ StartFrame queued!")
        
        # 🔧 HYBRID FIX: Start direct Deepgram connection (from fixed_tts_agent.py)
        print(f"🔧 Starting DIRECT Deepgram STT connection...")
        direct_dg_connection.on(LiveTranscriptionEvents.Transcript, on_deepgram_message)
        direct_dg_connection.on(LiveTranscriptionEvents.Error, on_deepgram_error)
        await direct_dg_connection.start(direct_live_options)
        print(f"✅ Direct Deepgram STT connection started!")
        
        # Aggressive keepalive task (from fixed_tts_agent.py)
        async def send_keepalive():
            nonlocal last_audio_time
            try:
                await asyncio.sleep(0.5)  # Brief delay to let connection settle
                await direct_dg_connection.keep_alive()
                print(f"💓 Initial Deepgram KeepAlive sent!")
            except Exception as e:
                print(f"❌ Initial KeepAlive error: {e}")
                
            while True:
                try:
                    current_time = time.time()
                    if current_time - last_audio_time > 2:
                        print(f"💓 Sending Deepgram KeepAlive... (last audio: {current_time - last_audio_time:.1f}s ago)")
                        await direct_dg_connection.keep_alive()
                    await asyncio.sleep(0.2)  # Check every 2 seconds
                except Exception as e:
                    print(f"❌ KeepAlive error: {e}")
                    break
                    
        keepalive_task = asyncio.create_task(send_keepalive())
        print(f"✅ Deepgram keepalive task started")

        # Remove greeting scheduling here; VoiceHandler will produce the greeting
        
        global runner
        runner = PipelineRunner()
        print(f"🔧 Starting pipeline runner...")
        logger.info(f"Starting pipeline runner for call {call_sid}")
        
        # Let FastAPIWebsocketTransport consume all remaining messages
        print(f"🔧 Ready to start pipeline runner - FastAPIWebsocketTransport will handle all remaining messages")
        
        # 🔧 HYBRID FIX: Enhanced WebSocket monitoring with direct Deepgram audio forwarding
        print(f"🔍 Adding WebSocket message monitoring + audio forwarding for {call_sid}...")
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
                        
                        # 🔧 CRITICAL: Forward audio to direct Deepgram (from fixed_tts_agent.py)
                        if payload_data:
                            try:
                                audio_chunk = base64.b64decode(payload_data)
                                await direct_dg_connection.send(audio_chunk)
                                last_audio_time = time.time()  # Update for keepalive
                            except Exception as e:
                                print(f"❌ Failed to forward audio to direct Deepgram: {e}")
                        
                        # Reduced logging - only log every 100th frame to avoid spam
                        if int(media_data.get('timestamp', 0)) % 2000 == 0:  # Every 2 seconds
                            print(f"📡 AUDIO FLOWING: payload_len={len(payload_data)} bytes, timestamp={media_data.get('timestamp', 'N/A')} → Deepgram")
                    elif event_type == "start":
                        start = payload.get("start", {})
                        fmt = start.get("mediaFormat", {})
                        if fmt:
                            print(f"🔍 Twilio start.mediaFormat: {fmt}")
                    elif event_type not in ["connected", "start"]:
                        print(f"🔍 WS Event: {event_type}")
                except Exception:
                    print(f"🔍 Non-JSON WS message: {message[:100]}...")
                return message
            except Exception as e:
                print(f"⚠️ WebSocket receive error: {e}")
                raise
        websocket.receive_text = debug_receive_text
        
        try:
            print(f"🚀 Pipeline runner starting for {call_sid}...")
            logger.info(f"About to call runner.run(task) for {call_sid}")
            
            # Let VoiceHandler send greeting naturally when TTS is ready
            print(f"🎙️ VoiceHandler will send greeting when TTS service signals readiness")
            
            await runner.run(task)
            print(f"✅ Pipeline runner finished normally for {call_sid}")
            logger.info(f"Pipeline runner finished for call {call_sid}")
        except asyncio.CancelledError:
            print(f"⚠️ Pipeline runner cancelled for {call_sid}")
            logger.warning(f"Pipeline runner cancelled for call {call_sid}")
            raise
        except Exception as e:
            print(f"❌ Pipeline runner error for {call_sid}: {e}")
            logger.error(f"Pipeline runner error for call {call_sid}: {e}")
            raise
        finally:
            # Send EndFrame to properly close pipeline and stop all processors
            print(f"🛑 Sending EndFrame to close pipeline for {call_sid}")
            try:
                from pipecat.frames.frames import EndFrame
                await task.queue_frame(EndFrame())
                logger.info(f"EndFrame sent to pipeline for {call_sid}")
                await asyncio.sleep(0.5)  # Give time for processors to cleanup
            except Exception as e:
                logger.error(f"Error sending EndFrame for {call_sid}: {e}")
                
            # 🔧 HYBRID FIX: Cleanup direct Deepgram connection and keepalive
            print(f"🧹 Cleaning up direct Deepgram connection for {call_sid}")
            try:
                if 'keepalive_task' in locals():
                    keepalive_task.cancel()
                    print(f"✅ Keepalive task cancelled")
            except Exception as e:
                print(f"⚠️ Keepalive cleanup error: {e}")
                
            try:
                await direct_dg_connection.finish()
                print(f"✅ Direct Deepgram connection closed")
            except Exception as e:
                print(f"⚠️ Deepgram cleanup error: {e}")
        
    except Exception as e:
        logger.error(f"Error in media stream for {call_sid}: {e}")
    finally:
        await state_manager.cleanup_state(call_sid)
        print(f"🔌 MediaStream disconnected for {call_sid}")
        logger.info(f"MediaStream disconnected for {call_sid}")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "healthcare-voice-agent"}


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
    
    print(f"🚀 Starting server on port {port}")
    
    # Run with the dynamic port
    uvicorn.run(
        "src.main:app",  # or just app if running directly
        host="0.0.0.0",
        port=port,
        log_level="info"
    )