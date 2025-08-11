#!/usr/bin/env python3
"""Test pipeline frame flow to identify where frames get lost."""

import asyncio
from pipecat.frames.frames import TextFrame, StartFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

class DebugFrameProcessor(FrameProcessor):
    """A debug processor that logs all frames passing through."""
    
    def __init__(self, name: str):
        super().__init__()
        self.name = name
        self.frames_seen = []
    
    async def process_frame(self, frame, direction):
        frame_type = type(frame).__name__
        
        # Log the frame
        if frame_type == "TextFrame":
            text_content = getattr(frame, 'text', '')[:50]
            print(f"🔍 {self.name}: {frame_type} - '{text_content}...' direction={direction}")
        else:
            print(f"🔍 {self.name}: {frame_type} direction={direction}")
        
        # Track frames
        self.frames_seen.append((frame_type, direction))
        
        # Pass frame downstream
        await super().process_frame(frame, direction)

async def test_pipeline_flow():
    """Test a simple pipeline to see where TextFrames get lost."""
    print("🧪 PIPELINE FLOW TEST")
    print("=" * 50)
    
    # Create a chain of debug processors
    processor1 = DebugFrameProcessor("PROC1")
    processor2 = DebugFrameProcessor("PROC2") 
    processor3 = DebugFrameProcessor("PROC3")
    
    # Link them together
    processor1.set_next(processor2)
    processor2.set_next(processor3)
    
    print("🔧 Pipeline: PROC1 -> PROC2 -> PROC3")
    
    # Send StartFrame
    print("\n🚀 Sending StartFrame...")
    await processor1.process_frame(StartFrame(), FrameDirection.DOWNSTREAM)
    
    await asyncio.sleep(0.1)
    
    # Send TextFrame
    test_text = "Hello! This is a pipeline test."
    print(f"\n🔤 Sending TextFrame: '{test_text}'")
    text_frame = TextFrame(text=test_text)
    await processor1.process_frame(text_frame, FrameDirection.DOWNSTREAM)
    
    await asyncio.sleep(0.1)
    
    # Results
    print("\n" + "=" * 50)
    print("📊 FRAME FLOW ANALYSIS:")
    
    for i, proc in enumerate([processor1, processor2, processor3], 1):
        print(f"\n{proc.name} saw {len(proc.frames_seen)} frames:")
        for frame_type, direction in proc.frames_seen:
            print(f"  - {frame_type} ({direction})")
    
    # Check if TextFrame made it through
    text_frames_at_end = len([f for f, d in processor3.frames_seen if f == "TextFrame"])
    
    if text_frames_at_end > 0:
        print(f"\n✅ SUCCESS: TextFrame made it through pipeline!")
        print("🎯 Pipeline flow is working - issue is likely in TTS service")
    else:
        print(f"\n❌ FAILURE: TextFrame got lost in pipeline!")
        print("🎯 Pipeline has issues - frames not flowing correctly")
        
    return text_frames_at_end > 0

if __name__ == "__main__":
    success = asyncio.run(test_pipeline_flow())
    print(f"\n🏁 Pipeline Test Result: {'✅ PASS' if success else '❌ FAIL'}")

