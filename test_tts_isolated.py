#!/usr/bin/env python3
"""Isolated TTS test to verify Cartesia works independently."""

import asyncio
import logging
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.frames.frames import TextFrame, StartFrame
from src.config.settings import get_settings

async def test_cartesia_tts_isolated():
    """Test Cartesia TTS in complete isolation."""
    print("🧪 ISOLATED CARTESIA TTS TEST")
    print("=" * 50)
    
    settings = get_settings()
    
    # Enable debug logging
    logging.basicConfig(level=logging.DEBUG)
    cartesia_logger = logging.getLogger("pipecat.services.cartesia")
    cartesia_logger.setLevel(logging.DEBUG)
    
    try:
        print(f"🔑 API Key: {settings.cartesia_api_key[:8]}...{settings.cartesia_api_key[-4:]}")
        
        # Create TTS service
        tts_service = CartesiaTTSService(
            api_key=settings.cartesia_api_key,
            voice_id="professional-female-1",
            model="sonic-turbo",
            sample_rate=8000,
            encoding="pcm_s16le",
            container="raw"
        )
        
        print("✅ CartesiaTTSService created successfully")
        
        # Create a simple frame processor to capture output
        audio_frames_received = []
        
        class TestProcessor:
            async def process_frame(self, frame, direction):
                frame_type = type(frame).__name__
                print(f"📦 Received frame: {frame_type}")
                if hasattr(frame, 'audio'):
                    audio_data = getattr(frame, 'audio', b'')
                    audio_frames_received.append(len(audio_data))
                    print(f"🔊 Audio frame: {len(audio_data)} bytes")
                return frame
        
        # Link test processor
        test_processor = TestProcessor()
        tts_service._next = test_processor
        
        # Send StartFrame
        print("🚀 Sending StartFrame to TTS...")
        await tts_service.process_frame(StartFrame(), None)
        
        # Wait a moment for initialization
        await asyncio.sleep(1)
        
        # Send TextFrame
        test_text = "Hello! This is a TTS test."
        print(f"🔤 Sending TextFrame: '{test_text}'")
        text_frame = TextFrame(text=test_text)
        await tts_service.process_frame(text_frame, None)
        
        # Wait for processing
        print("⏳ Waiting for TTS processing...")
        await asyncio.sleep(5)
        
        # Results
        print("\n" + "=" * 50)
        if audio_frames_received:
            total_audio = sum(audio_frames_received)
            print(f"✅ SUCCESS: Received {len(audio_frames_received)} audio frames")
            print(f"📊 Total audio data: {total_audio} bytes")
            print("🎯 TTS IS WORKING - Problem is in pipeline!")
        else:
            print("❌ FAILURE: No audio frames received")
            print("🎯 TTS IS BROKEN - API key or service issue!")
            
        return len(audio_frames_received) > 0
        
    except Exception as e:
        print(f"❌ TTS Test failed: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_cartesia_tts_isolated())
    print(f"\n🏁 TTS Test Result: {'✅ PASS' if success else '❌ FAIL'}")
