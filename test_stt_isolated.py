#!/usr/bin/env python3
"""Isolated STT test to verify Deepgram works independently."""

import asyncio
import base64
import logging
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.frames.frames import InputAudioRawFrame, StartFrame
from deepgram import LiveOptions
from src.config.settings import get_settings

async def test_deepgram_stt_isolated():
    """Test Deepgram STT in complete isolation with sample audio."""
    print("🧪 ISOLATED DEEPGRAM STT TEST")
    print("=" * 50)
    
    settings = get_settings()
    
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)
    deepgram_logger = logging.getLogger("pipecat.services.deepgram")
    deepgram_logger.setLevel(logging.DEBUG)
    
    try:
        print(f"🔑 API Key: {settings.deepgram_api_key[:8]}...{settings.deepgram_api_key[-4:]}")
        
        # Create STT service with same config as main app
        live_options = LiveOptions(
            language="en-US",
            model=settings.deepgram_model,
            punctuate=True,
            interim_results=True,
            endpointing=settings.deepgram_endpointing_ms,
            smart_format=True,
            profanity_filter=False,
            redact=False,
            channels=1,
        )
        
        stt_service = DeepgramSTTService(
            api_key=settings.deepgram_api_key,
            sample_rate=8000,
            live_options=live_options,
        )
        
        print("✅ DeepgramSTTService created successfully")
        
        # Create a simple frame processor to capture transcriptions
        transcriptions_received = []
        
        class TestProcessor:
            async def process_frame(self, frame, direction):
                frame_type = type(frame).__name__
                if frame_type in ["TranscriptionFrame", "InterimTranscriptionFrame"]:
                    text = getattr(frame, 'text', '')
                    confidence = getattr(frame, 'confidence', 'N/A')
                    print(f"🎯 {frame_type}: '{text}' (confidence: {confidence})")
                    if frame_type == "TranscriptionFrame":
                        transcriptions_received.append(text)
                return frame
        
        # Link test processor
        test_processor = TestProcessor()
        stt_service._next = test_processor
        
        # Send StartFrame
        print("🚀 Sending StartFrame to STT...")
        await stt_service.process_frame(StartFrame(), None)
        
        # Wait a moment for initialization
        await asyncio.sleep(2)
        
        # Generate simple test audio (8kHz, mulaw like Twilio)
        print("🎤 Generating test audio data...")
        
        # Create a simple audio pattern that should be recognizable
        # This is a very basic sine wave pattern encoded as mulaw
        import math
        sample_rate = 8000
        duration = 2.0  # 2 seconds
        frequency = 440  # A4 note
        
        # Generate raw PCM samples first
        samples = []
        for i in range(int(sample_rate * duration)):
            t = i / sample_rate
            sample = int(32767 * 0.3 * math.sin(2 * math.pi * frequency * t))
            samples.extend([sample & 0xFF, (sample >> 8) & 0xFF])  # 16-bit PCM
        
        audio_data = bytes(samples)
        
        # Send audio in chunks like Twilio would
        chunk_size = 320  # 20ms worth of data at 8kHz, 16-bit = 320 bytes
        print(f"📡 Sending {len(audio_data)} bytes of audio data in chunks...")
        
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            if len(chunk) > 0:
                audio_frame = InputAudioRawFrame(chunk, sample_rate, 1)
                await stt_service.process_frame(audio_frame, None)
                await asyncio.sleep(0.02)  # 20ms delay between chunks
        
        # Wait for processing
        print("⏳ Waiting for STT processing...")
        await asyncio.sleep(3)
        
        # Results
        print("\n" + "=" * 50)
        if transcriptions_received:
            print(f"✅ SUCCESS: Received {len(transcriptions_received)} transcriptions")
            for i, text in enumerate(transcriptions_received):
                print(f"   {i+1}: '{text}'")
            print("🎯 STT IS WORKING - May need different audio format!")
        else:
            print("❌ FAILURE: No final transcriptions received")
            print("🎯 STT MAY BE WORKING but audio format is wrong!")
            
        return len(transcriptions_received) > 0
        
    except Exception as e:
        print(f"❌ STT Test failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_deepgram_stt_isolated())
    print(f"\n🏁 STT Test Result: {'✅ PASS' if success else '❌ FAIL'}")

