"""WebSocket handler for Twilio MediaStream connections.

This module handles real-time audio streaming from Twilio via WebSocket,
processes audio through the voice agent pipeline, and returns synthesized responses.

HYBRID STT ARCHITECTURE
=======================

This module implements a "hybrid" speech-to-text architecture that uses
TWO parallel Deepgram connections:

1. PIPECAT STT (via pipeline/factory.py):
   - DeepgramSTTService is part of the Pipecat pipeline
   - Audio flows: transport.input() → DeepgramSTTService → VoiceHandler → TTS → output()
   - This is the "proper" way to handle STT in Pipecat

2. DIRECT DEEPGRAM (hybrid workaround):
   - A separate DeepgramClient WebSocket connection
   - Audio is manually forwarded from Twilio WebSocket to Deepgram
   - Transcriptions are injected into the pipeline via TranscriptionFrame
   - This was added to fix reliability issues with Pipecat's built-in STT

WHY THIS EXISTS:
During development, Pipecat's DeepgramSTTService exhibited reliability issues
(missing transcriptions, connection drops). The direct Deepgram connection
provides a fallback that has proven more reliable.

CONFIGURATION:
- Set ENABLE_DIRECT_STT=false to disable the hybrid approach
- Monitor metrics: voiceagent_transcriptions_total{source="direct|pipecat"}
  to see which path is providing transcriptions

FUTURE:
Once Pipecat's STT reliability is confirmed, set ENABLE_DIRECT_STT=false
and rely solely on the pipeline approach. This will reduce:
- API costs (only one Deepgram connection per call)
- Code complexity
- Potential for duplicate transcriptions
"""
import asyncio
import json
import time
import base64
import logging
from fastapi import WebSocket

from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.frames.frames import StartFrame, EndFrame, TranscriptionFrame
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
from pipecat.transports.network.fastapi_websocket import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)
from pipecat.serializers.twilio import TwilioFrameSerializer

from src.config.settings import get_settings
from src.core.conversation_state import state_manager
from src.core.shutdown import register_runner, unregister_runner, is_shutting_down
from src.utils.logger import get_logger
from src.pipeline.factory import create_pipeline
from src.utils.metrics import (
    active_calls,
    total_calls,
    call_duration,
    websocket_errors,
    track_transcription,
)

logger = get_logger(__name__)
settings = get_settings()


async def handle_media_stream(websocket: WebSocket, call_sid: str):
    """Handle Twilio MediaStream WebSocket connection."""
    logger.debug(f"WEBSOCKET DEBUG: Starting handler for {call_sid}")

    # Reject new calls during shutdown
    if is_shutting_down():
        logger.warning(f"Rejecting new call {call_sid} - system is shutting down")
        await websocket.close(code=1001, reason="Service shutting down")
        return

    # Track active call and start timer
    active_calls.inc()
    call_start_time = time.time()
    call_status = "error"  # Will be updated on successful completion

    # Initialize runner to None to avoid NameError in finally block
    runner = None

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

                except json.JSONDecodeError:
                    # Not JSON we care about; continue
                    logger.debug(f"Non-JSON WebSocket message received for call {call_sid}")
                    continue
                except KeyError as ke:
                    logger.debug(f"Missing expected key in message: {ke} for call {call_sid}")
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
        except asyncio.TimeoutError:
            logger.warning(f"Timeout while waiting for initial WS messages for call {call_sid}")
        except Exception as e:
            logger.warning(f"Error while parsing initial WS messages for call {call_sid}: {e}", exc_info=True)

        logger.debug(f"DEBUG: Deepgram model={settings.deepgram_model}, endpointing={settings.deepgram_endpointing_ms}ms for call {call_sid}")
        serializer = TwilioFrameSerializer(
            stream_sid=stream_sid,
            call_sid=call_sid,
            account_sid=settings.twilio_account_sid,
            auth_token=settings.get_twilio_auth_token(),
        )
        if not stream_sid:
            logger.warning(f"No stream_sid extracted for {call_sid}. Downstream audio may fail.")
        else:
            logger.info(f"Twilio serializer initialized with stream_sid={stream_sid} for {call_sid}")

        # Disable VAD (pipecat.vad not available in this build). Deepgram endpointing handles finalization.
        vad_analyzer = None
        logger.info("VAD disabled; relying on Deepgram endpointing")

        # =========================================================================
        # HYBRID STT ARCHITECTURE
        # =========================================================================
        # This creates a DIRECT Deepgram WebSocket connection in parallel with
        # Pipecat's built-in STT. This was added as a workaround for reliability
        # issues. Audio is forwarded to this direct connection, and transcriptions
        # are injected back into the pipeline via TranscriptionFrame.
        #
        # Set ENABLE_DIRECT_STT=false to disable and rely solely on Pipecat's STT.
        # Monitor metrics: voiceagent_transcriptions_total{source="direct|pipecat"}
        # =========================================================================
        direct_dg_connection = None
        direct_deepgram_client = None

        if settings.enable_direct_stt:
            logger.info(f"[HYBRID STT] Setting up DIRECT Deepgram connection for call {call_sid}")
            direct_deepgram_client = DeepgramClient(settings.get_deepgram_api_key())
            direct_dg_connection = direct_deepgram_client.listen.asyncwebsocket.v("1")
        else:
            logger.info(f"[HYBRID STT] Direct STT DISABLED - using Pipecat STT only for call {call_sid}")

        # Direct Deepgram options (only used when enable_direct_stt=True)
        direct_live_options = None
        if settings.enable_direct_stt:
            direct_live_options = LiveOptions(
                model=settings.deepgram_model,
                encoding="mulaw",  # Twilio audio format
                sample_rate=8000,
                channels=1,
                interim_results=True,
                endpointing=settings.deepgram_endpointing_ms,
                smart_format=True
            )
            logger.info(f"[HYBRID STT] Direct Deepgram STT connection ready for call {call_sid}")
        last_audio_time = time.time()

        # Direct Deepgram event handlers (HYBRID STT - direct path)
        # This provides transcriptions when Pipecat's built-in STT has issues
        async def on_deepgram_message(self, result, **kwargs):
            nonlocal last_audio_time
            last_audio_time = time.time()

            if result.channel.alternatives[0].transcript:
                sentence = result.channel.alternatives[0].transcript.strip()
                confidence = getattr(result.channel.alternatives[0], 'confidence', None)

                if result.is_final:
                    if sentence:
                        # Track metric: transcription from DIRECT Deepgram path
                        track_transcription(source='direct', is_final=True, confidence=confidence)
                        logger.info(f"[DIRECT STT] Final transcription: '{sentence}' for {call_sid}")
                        await forward_transcription_to_pipeline(sentence)
                else:
                    if sentence:
                        # Track interim transcription
                        track_transcription(source='direct', is_final=False, confidence=confidence)
                        logger.debug(f"[DIRECT STT] Interim: '{sentence}' for call {call_sid}")

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
        logging.getLogger("pipecat.transports.websocket.fastapi").setLevel(logging.DEBUG)
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

        # Set pipeline_task reference for direct Deepgram transcription forwarding
        pipeline_task = task
        if settings.enable_direct_stt:
            logger.debug(f"[HYBRID STT] Pipeline task reference set for transcription injection for call {call_sid}")

        # CRITICAL: Send StartFrame to initialize all processors BEFORE starting runner
        logger.debug(f"Sending StartFrame to initialize pipeline for call {call_sid}")
        await task.queue_frame(StartFrame())
        # Remove extra warm-up frames to reduce initial latency
        logger.debug(f"StartFrame queued for call {call_sid}")

        # Start direct Deepgram connection if enabled
        keepalive_task = None
        if settings.enable_direct_stt and direct_dg_connection:
            logger.debug(f"[HYBRID STT] Starting DIRECT Deepgram STT connection for call {call_sid}")
            direct_dg_connection.on(LiveTranscriptionEvents.Transcript, on_deepgram_message)
            direct_dg_connection.on(LiveTranscriptionEvents.Error, on_deepgram_error)
            await direct_dg_connection.start(direct_live_options)
            logger.info(f"[HYBRID STT] Direct Deepgram STT connection started for call {call_sid}")

            # Aggressive keepalive task for direct Deepgram connection
            async def send_keepalive():
                nonlocal last_audio_time
                try:
                    await asyncio.sleep(0.5)  # Brief delay to let connection settle
                    await direct_dg_connection.keep_alive()
                    logger.debug(f"[HYBRID STT] Initial KeepAlive sent for call {call_sid}")
                except Exception as e:
                    logger.error(f"[HYBRID STT] Initial KeepAlive error for call {call_sid}: {e}")

                while True:
                    try:
                        current_time = time.time()
                        if current_time - last_audio_time > 2:
                            logger.debug(f"[HYBRID STT] KeepAlive for call {call_sid} (last audio: {current_time - last_audio_time:.1f}s ago)")
                            await direct_dg_connection.keep_alive()
                        await asyncio.sleep(0.2)  # Check every 200ms
                    except Exception as e:
                        logger.error(f"[HYBRID STT] KeepAlive error for call {call_sid}: {e}")
                        break

            keepalive_task = asyncio.create_task(send_keepalive())
            logger.debug(f"[HYBRID STT] Keepalive task started for call {call_sid}")

        # Remove greeting scheduling here; VoiceHandler will produce the greeting

        # Create pipeline runner as LOCAL variable (not global)
        # Shutdown tracking is handled via register_runner/unregister_runner
        runner = PipelineRunner()
        register_runner(runner)  # Register for graceful shutdown tracking
        logger.info(f"Starting pipeline runner for call {call_sid}")

        # Let FastAPIWebsocketTransport consume all remaining messages
        logger.debug(f"Ready to start pipeline runner - FastAPIWebsocketTransport will handle all remaining messages for call {call_sid}")

        # WebSocket message monitoring with optional direct Deepgram audio forwarding
        if settings.enable_direct_stt:
            logger.debug(f"[HYBRID STT] Adding WebSocket audio forwarding for {call_sid}")
        else:
            logger.debug(f"WebSocket monitoring enabled for {call_sid}")

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

                        # Forward audio to direct Deepgram ONLY if enabled
                        if settings.enable_direct_stt and direct_dg_connection and payload_data:
                            try:
                                audio_chunk = base64.b64decode(payload_data)
                                await direct_dg_connection.send(audio_chunk)
                                last_audio_time = time.time()  # Update for keepalive
                            except Exception as e:
                                logger.error(f"[HYBRID STT] Failed to forward audio for call {call_sid}: {e}")

                        # Reduced logging - only log every 2 seconds to avoid spam
                        if int(media_data.get('timestamp', 0)) % 2000 == 0:
                            if settings.enable_direct_stt:
                                logger.debug(f"[HYBRID STT] AUDIO: {len(payload_data)} bytes -> Deepgram for call {call_sid}")
                            else:
                                logger.debug(f"AUDIO: {len(payload_data)} bytes for call {call_sid}")
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
            call_status = "success"  # Mark call as successful
        except asyncio.CancelledError:
            logger.warning(f"Pipeline runner cancelled for {call_sid}")
            call_status = "cancelled"
            raise
        except Exception as e:
            logger.error(f"Pipeline runner error for {call_sid}: {e}")
            call_status = "error"
            websocket_errors.labels(error_type='pipeline_error').inc()
            raise
        finally:
            # Send EndFrame to properly close pipeline and stop all processors
            logger.debug(f"Sending EndFrame to close pipeline for {call_sid}")
            try:
                await task.queue_frame(EndFrame())
                logger.info(f"EndFrame sent to pipeline for {call_sid}")
                await asyncio.sleep(0.5)  # Give time for processors to cleanup
            except Exception as e:
                logger.error(f"Error sending EndFrame for {call_sid}: {e}")

            # Cleanup direct Deepgram connection and keepalive (if enabled)
            if settings.enable_direct_stt:
                logger.debug(f"[HYBRID STT] Cleaning up direct Deepgram connection for {call_sid}")
                try:
                    if keepalive_task:
                        keepalive_task.cancel()
                        logger.debug(f"[HYBRID STT] Keepalive task cancelled for call {call_sid}")
                except Exception as e:
                    logger.warning(f"[HYBRID STT] Keepalive cleanup error for call {call_sid}: {e}")

                try:
                    if direct_dg_connection:
                        await direct_dg_connection.finish()
                        logger.debug(f"[HYBRID STT] Direct Deepgram connection closed for {call_sid}")
                except Exception as e:
                    logger.warning(f"[HYBRID STT] Deepgram cleanup error for call {call_sid}: {e}")

            # Unregister runner from shutdown tracking
            if runner:
                unregister_runner(runner)
                logger.debug(f"Unregistered pipeline runner for graceful shutdown tracking for call {call_sid}")

    except Exception as e:
        logger.error(f"Error in media stream for {call_sid}: {e}")
        call_status = "error"
        websocket_errors.labels(error_type='media_stream_error').inc()
    finally:
        # Record call metrics
        active_calls.dec()
        total_calls.labels(status=call_status).inc()
        call_duration_seconds = time.time() - call_start_time
        call_duration.observe(call_duration_seconds)
        logger.info(f"Call {call_sid} completed: status={call_status}, duration={call_duration_seconds:.2f}s")

        await state_manager.cleanup_state(call_sid)
        logger.info(f"MediaStream disconnected for {call_sid}")
