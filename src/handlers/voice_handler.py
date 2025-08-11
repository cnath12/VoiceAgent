"""Main voice conversation handler."""
from typing import AsyncGenerator, List, Optional
import json

from pipecat.frames.frames import (
    Frame, TextFrame, StartFrame, TranscriptionFrame, InterimTranscriptionFrame,
    UserStartedSpeakingFrame, UserStoppedSpeakingFrame,
    TTSStartedFrame, TTSStoppedFrame, EndFrame, AudioRawFrame
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

from src.core.conversation_state import state_manager, ConversationPhase
from src.core.models import ConversationState
from src.config.prompts import SYSTEM_PROMPT, PHASE_PROMPTS, ERROR_PROMPTS
from src.handlers.insurance_handler import InsuranceHandler
from src.handlers.symptom_handler import SymptomHandler
from src.handlers.demographics_handler import DemographicsHandler
from src.handlers.scheduling_handler import SchedulingHandler
from src.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceHandler(FrameProcessor):
    """Main handler coordinating all conversation phases."""
    
    def __init__(self, call_sid: str):
        super().__init__()
        self.call_sid = call_sid
        
        # Initialize phase handlers
        self.phase_handlers = {
            ConversationPhase.INSURANCE: InsuranceHandler(call_sid),
            ConversationPhase.CHIEF_COMPLAINT: SymptomHandler(call_sid),
            ConversationPhase.DEMOGRAPHICS: DemographicsHandler(call_sid),
            ConversationPhase.PROVIDER_SELECTION: SchedulingHandler(call_sid),
            ConversationPhase.APPOINTMENT_SCHEDULING: SchedulingHandler(call_sid),
        }
        
        self._current_phase_handler = None
        self._speaking = False
        self._last_user_input_time = None
        self._silence_check_task = None
        self._initialized = False
        # Greeting sent in StartFrame handler only (no duplicates)
        self._tts_warmed_up = False
        
        # Prevent question repetition
        self._last_response = None
        self._response_count = 0
        self._max_same_response = 2  # Maximum times to ask same question
    
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Process incoming frames."""
        
        # Targeted logging: show only meaningful events; silence raw audio frame spam
        frame_type = type(frame).__name__
        frame_info = f"{frame_type} direction={direction}"
        if hasattr(frame, 'text') and hasattr(frame, '__dict__'):
            frame_info += f" text='{getattr(frame, 'text', '')[:50]}...'"
        elif hasattr(frame, 'audio') and hasattr(frame, '__dict__'):
            audio_data = getattr(frame, 'audio', b'')
            frame_info += f" audio_len={len(audio_data) if audio_data else 0}"

        # Only print important events; skip AudioRawFrame/InputAudioRawFrame noise
        important_frames = {
            "TextFrame",
            "TranscriptionFrame",
            "InterimTranscriptionFrame",
            "StartFrame",
            "EndFrame",
            "UserStartedSpeakingFrame",
            "UserStoppedSpeakingFrame",
            "TTSStartedFrame",
            "TTSStoppedFrame",
        }
        if frame_type in important_frames:
            print(f"🔥 IMPORTANT FRAME: {frame_info} for {self.call_sid}")
        # Always keep a debug log line for diagnostics (respects logger level)
        logger.debug(f"VoiceHandler processing frame: {frame_info} for {self.call_sid}")
        
        # Handle StartFrame - MUST pass through first, then initialize
        if isinstance(frame, StartFrame):
            print(f"🚀 VoiceHandler received StartFrame - processing and forwarding")
            
            # Only process the FIRST StartFrame to avoid duplicate greetings
            if hasattr(self, '_start_frame_processed'):
                print(f"⚠️ StartFrame already processed - skipping duplicate greeting")
                await super().process_frame(frame, direction)
                await self.push_frame(frame, direction)
                return
            
            # Mark StartFrame as processed to prevent duplicates    
            self._start_frame_processed = True
            
            # Handle internal Pipecat state first
            await super().process_frame(frame, direction)
            print(f"🔧 VoiceHandler internal state processed, now forwarding to TTS")
            # CRITICAL: Explicitly forward to TTS service
            await self.push_frame(frame, direction)
            print(f"✅ StartFrame forwarded to TTS service")

            if not self._initialized:
                self._initialized = True
                logger.info(f"VoiceHandler initialized for {self.call_sid}")
                
                # DEEPGRAM TTS FIX: Send greeting immediately since DeepgramTTS doesn't send TTSStartedFrame
                print(f"🎯 CONTINUOUS GREETING: Sending uninterrupted greeting")
                
                # Make greeting more TTS-friendly with natural pauses but no breaks
                greeting = ("Hello! This is Assort Health, your AI appointment scheduler. "
                           "I'm here to help you schedule your appointment today. "
                           "First, are you experiencing a medical emergency?")
                
                print(f"🗣️ Sending continuous greeting (length: {len(greeting)} chars)")
                print(f"🗣️ Greeting text: '{greeting}'")
                logger.info(f"Sending initial greeting to {self.call_sid}")
                
                # Create TextFrame with explicit handling
                greeting_frame = TextFrame(text=greeting)
                print(f"🔥 Created greeting TextFrame: {greeting_frame}")
                await self.push_frame(greeting_frame, FrameDirection.DOWNSTREAM)
                print(f"✅ Continuous greeting TextFrame sent to TTS service!")
            return
        
        # Handle speech events
        elif isinstance(frame, TTSStartedFrame):
            print(f"🔊 TTS STARTED FRAME received for {self.call_sid}")
            logger.info(f"TTS started frame received for {self.call_sid}")
            
            # NO GREETING HERE - greeting already sent in StartFrame handler to prevent duplicates
            print(f"🚫 Skipping TTSStartedFrame greeting - already sent in StartFrame handler")
            await self.push_frame(frame, direction)
            
        elif isinstance(frame, TTSStoppedFrame):
            print(f"🛑 TTS STOPPED FRAME received for {self.call_sid}")
            logger.info(f"TTS stopped frame received for {self.call_sid}")
            await self.push_frame(frame, direction)

        elif isinstance(frame, UserStartedSpeakingFrame):
            self._speaking = True
            logger.info(f"User started speaking in {self.call_sid}")
        
        elif isinstance(frame, UserStoppedSpeakingFrame):
            self._speaking = False
            logger.info(f"User stopped speaking in {self.call_sid}")
        
        # Handle transcription frames from Deepgram STT
        # Some STT implementations may deliver transcriptions in either direction.
        # Process final transcriptions regardless of direction to avoid missing user speech.
        elif isinstance(frame, TranscriptionFrame):
            print(f"🎯 RECEIVED TRANSCRIPTION FRAME: text='{frame.text}' confidence={getattr(frame, 'confidence', 'N/A')}")
            logger.info(f"Received TranscriptionFrame: '{frame.text}' for {self.call_sid}")
            
            if frame.text and frame.text.strip():
                print(f"\n🗣️ ===== USER SAID: '{frame.text}' ===== (Final Transcription)")
                logger.info(f"🗣️ USER TRANSCRIPTION: '{frame.text}' for {self.call_sid}")
                logger.info(f"Processing transcription: '{frame.text}' for {self.call_sid}")
                import asyncio as _asyncio
                async for response_frame in self._handle_user_input(frame.text):
                    print(f"🚀 Preparing to push response frame: {type(response_frame).__name__}")
                    # Warm up TTS on the very first TextFrame by ensuring a StartFrame reached it
                    if (
                        not self._tts_warmed_up
                        and isinstance(response_frame, TextFrame)
                    ):
                        try:
                            print("🔊 Warming up TTS: sending downstream StartFrame before first TextFrame")
                            await self.push_frame(StartFrame(), FrameDirection.DOWNSTREAM)
                            await _asyncio.sleep(0.15)
                            self._tts_warmed_up = True
                        except Exception as e:
                            logger.warning(f"Failed to warm up TTS with StartFrame: {e}")

                    try:
                        await self.push_frame(response_frame, FrameDirection.DOWNSTREAM)
                    except Exception as e:
                        # Retry once after a short delay if Cartesia wasn't ready
                        logger.error(f"Push TextFrame failed ({e}); retrying after short delay...")
                        await _asyncio.sleep(0.5)
                        try:
                            await self.push_frame(response_frame, FrameDirection.DOWNSTREAM)
                            logger.info("Retry succeeded for TextFrame push")
                        except Exception as e2:
                            logger.error(f"Retry failed for TextFrame push: {e2}")
            else:
                print(f"⚠️ Received empty or whitespace-only TranscriptionFrame: '{frame.text}'")
                logger.warning(f"Empty TranscriptionFrame received for {self.call_sid}: '{frame.text}'")
            return  # Don't pass through the TranscriptionFrame

        # First audio frame debug to confirm transport IO
        elif isinstance(frame, AudioRawFrame):
            if not hasattr(self, '_audio_received'):
                try:
                    audio_len = len(getattr(frame, 'audio', b''))
                except Exception:
                    audio_len = -1
                self._audio_received = True
                print(f"🔊 AUDIO IS FLOWING! First audio frame received: {audio_len} bytes for {self.call_sid}")
                logger.info(f"First audio frame received in VoiceHandler for {self.call_sid}: {audio_len} bytes")
        
        # Handle interim transcription frames (log but don't process)
        elif isinstance(frame, InterimTranscriptionFrame):
            if frame.text and frame.text.strip():
                print(f"🎤 INTERIM TRANSCRIPTION: '{frame.text}' for {self.call_sid} (confidence: {getattr(frame, 'confidence', 'N/A')}) - NOT PROCESSED")
                logger.info(f"Interim transcription received: '{frame.text}' for {self.call_sid}")
                logger.debug(f"Interim transcription: '{frame.text}' for {self.call_sid}")
            return  # Don't pass through InterimTranscriptionFrame
        
        # Handle connection end frames
        elif isinstance(frame, EndFrame):
            print(f"🛑 EndFrame received for {self.call_sid} - cleaning up")
            logger.info(f"EndFrame received for {self.call_sid}, cleaning up")
            
            # Cancel silence monitoring
            if self._silence_check_task:
                self._silence_check_task.cancel()
                self._silence_check_task = None
                print(f"🔇 Silence monitoring cancelled for {self.call_sid}")
                logger.info(f"Silence monitoring cancelled for {self.call_sid}")
            else:
                print(f"⚠️ No silence task to cancel for {self.call_sid}")
            
            # Call parent method
            await super().process_frame(frame, direction)
        

        
        # For all other frames, call parent method first, then pass through
        else:
            await super().process_frame(frame, direction)
    
    async def _handle_user_input(self, text: str) -> AsyncGenerator[Frame, None]:
        """Process user input and generate response."""
        logger.info(f"User input in {self.call_sid}: {text}")
        
        # Track user input time for silence detection
        import time
        self._last_user_input_time = time.time()
        self._start_silence_monitoring()
        
        # Get current state
        state = await state_manager.get_state(self.call_sid)
        if not state:
            logger.error(f"No state found for {self.call_sid}")
            return
        
        # Add to transcript
        state.add_transcript_entry("user", text)
        
        # Route to appropriate handler based on phase
        response_text = await self._route_to_handler(state, text)
        
        # Send response as TextFrame with robust error handling
        if response_text and response_text.strip():
            # CHECK FOR REPETITION - Prevent asking same question multiple times
            if self._last_response == response_text:
                self._response_count += 1
                print(f"🚨 REPETITION WARNING: Same response #{self._response_count} - '{response_text[:50]}...'")
                
                if self._response_count >= self._max_same_response:
                    # Escalate or provide alternative response
                    escalated_response = self._handle_repetition_escalation(response_text, state)
                    if escalated_response:
                        response_text = escalated_response
                        print(f"🔄 ESCALATED RESPONSE: '{response_text[:50]}...'")
                        # Reset counter for new response
                        self._response_count = 0
                        self._last_response = response_text
                    else:
                        print(f"🛑 BLOCKING REPETITION: Skipping identical response #{self._response_count}")
                        return  # Skip sending the response
            else:
                # New response, reset counter
                self._response_count = 1
                self._last_response = response_text
                print(f"✅ NEW RESPONSE: '{response_text[:50]}...'")
            
            print(f"\n🤖 ===== AGENT RESPONDING: '{response_text}' =====")
            logger.info(f"Sending response: '{response_text[:50]}...' for {self.call_sid}")
            
            try:
                print(f"🔥 Creating TextFrame with response for TTS processing...")
                text_frame = TextFrame(text=response_text)
                print(f"🚀 Yielding TextFrame to pipeline: {text_frame}")
                yield text_frame
                # Add assistant response to transcript
                state.add_transcript_entry("assistant", response_text)
                print(f"✅ Successfully yielded TextFrame for TTS conversion")
                logger.info(f"Successfully sent response for {self.call_sid}")
                
            except Exception as e:
                print(f"❌ FAILED to yield TextFrame: {e}")
                logger.error(f"Failed to send response for {self.call_sid}: {e}")
                # Note: Don't yield fallback frames as they might cause the same error
    
    async def _route_to_handler(self, state: ConversationState, user_input: str) -> str:
        """Route input to appropriate phase handler."""
        phase = state.phase
        
        # Handle initial phases directly
        if phase == ConversationPhase.GREETING:
            await state_manager.transition_phase(
                self.call_sid, 
                ConversationPhase.EMERGENCY_CHECK
            )
            # NO additional message - greeting already included emergency question
            # Return None to avoid sending another TTS frame
            return None
        
        elif phase == ConversationPhase.EMERGENCY_CHECK:
            # Smart emergency detection - look for positive vs negative responses
            input_lower = user_input.lower()
            
            # Positive emergency indicators
            emergency_yes = any(phrase in input_lower for phrase in [
                "yes", "experiencing emergency", "need emergency", "911", "urgent", 
                "having emergency", "this is emergency"
            ])
            
            # Negative emergency indicators  
            emergency_no = any(phrase in input_lower for phrase in [
                "no", "not experiencing", "no emergency", "not emergency", 
                "not urgent", "i'm not", "not having"
            ])
            
            print(f"🚨 EMERGENCY CHECK: Input='{user_input}', Yes={emergency_yes}, No={emergency_no}")
            
            if emergency_yes and not emergency_no:
                return "Please hang up and dial 911 immediately for emergency assistance."
            else:
                # Assume no emergency and proceed to insurance
                print(f"✅ NO EMERGENCY detected, proceeding to insurance phase")
                await state_manager.transition_phase(
                    self.call_sid,
                    ConversationPhase.INSURANCE
                )
                return PHASE_PROMPTS["insurance"]
        
        # Use specific handlers for data collection phases
        elif phase in self.phase_handlers:
            handler = self.phase_handlers[phase]
            handler_name = type(handler).__name__
            print(f"🎯 ROUTING: Phase={phase}, Handler={handler_name}, Input='{user_input[:50]}...'")
            logger.info(f"Routing to {handler_name} for phase {phase}: '{user_input[:50]}...'")
            response = await handler.process_input(user_input, state)
            print(f"🤖 HANDLER RESPONSE: {handler_name} -> '{response[:100]}...'")
            return response
        
        # Handle confirmation phase
        elif phase == ConversationPhase.CONFIRMATION:
            return await self._handle_confirmation(state, user_input)
        
        return ERROR_PROMPTS["not_understood"]
    
    async def _handle_confirmation(self, state: ConversationState, user_input: str) -> str:
        """Handle final confirmation phase.

        Offload email sending to a background task so we don't block the
        real-time media pipeline.
        """
        try:
            import asyncio
            from src.services.email_service import EmailService

            async def _send_email_with_retry():
                email_service = EmailService()
                # simple retry: 3 attempts with backoff
                for attempt in range(3):
                    ok = await email_service.send_appointment_confirmation(state)
                    if ok:
                        return
                    await asyncio.sleep(2 * (attempt + 1))

            asyncio.create_task(_send_email_with_retry())
        except Exception as e:
            logger.error(f"Failed to spawn email task: {e}")

        # Mark as completed immediately
        await state_manager.transition_phase(
            self.call_sid,
            ConversationPhase.COMPLETED
        )
        
        return "Your appointment has been scheduled. You'll receive a confirmation email shortly. Thank you for calling. Goodbye!"
    

    
    def _start_silence_monitoring(self):
        """Start monitoring for user silence."""
        # Cancel existing silence check if any
        if self._silence_check_task:
            self._silence_check_task.cancel()
        
        import asyncio
        self._silence_check_task = asyncio.create_task(self._monitor_silence())
    
    async def _monitor_silence(self):
        """Monitor for silence and check in with user after 30 seconds."""
        import asyncio
        import time
        
        try:
            while True:
                await asyncio.sleep(30)  # Wait 30 seconds - much more patient
                
                if self._last_user_input_time:
                    time_since_input = time.time() - self._last_user_input_time
                    
                    if time_since_input >= 30:
                        logger.info(f"Silence detected for {self.call_sid}, checking in with user")
                        
                        # Send check-in message
                        checkin = "Are you still there? I'm here to help you schedule your appointment."
                        await self.push_frame(TextFrame(text=checkin), FrameDirection.DOWNSTREAM)
                        
                        # Reset timer
                        self._last_user_input_time = time.time()
                        
        except asyncio.CancelledError:
            logger.info(f"Silence monitoring cancelled for {self.call_sid}")
        except Exception as e:
            logger.error(f"Error in silence monitoring for {self.call_sid}: {e}")
    
    def _handle_repetition_escalation(self, repeated_response: str, state: ConversationState) -> Optional[str]:
        """Handle cases where the same response would be repeated multiple times."""
        
        # If asking for insurance info repeatedly, provide more guidance
        if "insurance provider name" in repeated_response.lower():
            return ("I understand you may be having trouble. Let me explain what I need. "
                   "I need the name of your insurance company - like Kaiser Permanente, "
                   "Blue Cross Blue Shield, Aetna, Cigna, UnitedHealthcare, or another provider. "
                   "Can you tell me which insurance company you have?")
        
        # If asking for emergency info repeatedly, move forward
        elif "medical emergency" in repeated_response.lower():
            logger.info(f"Emergency question repeated, assuming no emergency and moving forward for {self.call_sid}")
            # Directly transition to insurance
            import asyncio
            asyncio.create_task(state_manager.transition_phase(self.call_sid, ConversationPhase.INSURANCE))
            return "I'll assume you're not experiencing an emergency. Let me collect your insurance information to help schedule your appointment. What's your insurance provider name?"
        
        # If asking for other info repeatedly, provide help
        else:
            return ("I understand this might be confusing. Let me know if you need any clarification, "
                   "or say 'help' if you'd like me to explain what information I need.")
