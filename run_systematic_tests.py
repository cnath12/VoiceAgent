#!/usr/bin/env python3
"""Systematic test runner to isolate voice agent issues."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

async def run_systematic_tests():
    """Run all isolated tests systematically to identify root cause."""
    print("🎯 SYSTEMATIC VOICE AGENT DEBUGGING")
    print("=" * 60)
    print("This will test each component in isolation to identify the root cause.")
    print("=" * 60)
    
    results = {}
    
    # Test 1: TTS Isolation
    print("\n" + "🔴" * 20 + " TEST 1: TTS ISOLATION " + "🔴" * 20)
    try:
        from test_tts_isolated import test_cartesia_tts_isolated
        results['tts'] = await test_cartesia_tts_isolated()
    except Exception as e:
        print(f"❌ TTS test failed to run: {e}")
        results['tts'] = False
    
    await asyncio.sleep(1)
    
    # Test 2: STT Isolation  
    print("\n" + "🔵" * 20 + " TEST 2: STT ISOLATION " + "🔵" * 20)
    try:
        from test_stt_isolated import test_deepgram_stt_isolated
        results['stt'] = await test_deepgram_stt_isolated()
    except Exception as e:
        print(f"❌ STT test failed to run: {e}")
        results['stt'] = False
        
    await asyncio.sleep(1)
    
    # Test 3: Pipeline Flow
    print("\n" + "🟡" * 20 + " TEST 3: PIPELINE FLOW " + "🟡" * 20)
    try:
        from test_pipeline_flow import test_pipeline_flow
        results['pipeline'] = await test_pipeline_flow()
    except Exception as e:
        print(f"❌ Pipeline test failed to run: {e}")
        results['pipeline'] = False
    
    # Comprehensive Analysis
    print("\n" + "🟢" * 20 + " COMPREHENSIVE ANALYSIS " + "🟢" * 20)
    
    print(f"\n📊 TEST RESULTS:")
    print(f"   🔤 TTS (Cartesia):     {'✅ PASS' if results.get('tts') else '❌ FAIL'}")
    print(f"   🎤 STT (Deepgram):     {'✅ PASS' if results.get('stt') else '❌ FAIL'}")  
    print(f"   🔗 Pipeline Flow:      {'✅ PASS' if results.get('pipeline') else '❌ FAIL'}")
    
    # Diagnosis
    print(f"\n🔍 DIAGNOSIS:")
    
    if not results.get('tts'):
        print("❌ TTS ISSUE: Cartesia API key invalid, service down, or configuration wrong")
        print("   → Check API key, try different voice/model, verify account status")
        
    if not results.get('stt'):
        print("❌ STT ISSUE: Audio format incompatible or Deepgram configuration wrong")  
        print("   → Try different audio encoding, check mulaw vs linear16")
        
    if not results.get('pipeline'):
        print("❌ PIPELINE ISSUE: Frames not flowing correctly through processors")
        print("   → Check frame processor linking, async handling")
        
    # Root Cause Analysis
    print(f"\n🎯 ROOT CAUSE ANALYSIS:")
    
    if results.get('tts') and results.get('pipeline'):
        print("✅ TTS and Pipeline work individually")
        print("🔍 LIKELY CAUSE: Integration issue - TTS not receiving frames in main app")
        print("💡 SOLUTION: Check VoiceHandler -> TTS connection, StartFrame timing")
        
    elif results.get('tts') and not results.get('pipeline'):
        print("✅ TTS works but Pipeline broken")  
        print("🔍 LIKELY CAUSE: Frame routing issue in main pipeline")
        print("💡 SOLUTION: Fix pipeline assembly, check processor linking")
        
    elif not results.get('tts'):
        print("❌ TTS fundamentally broken")
        print("🔍 LIKELY CAUSE: Cartesia API issue")
        print("💡 SOLUTION: Fix API key, try different TTS service for testing")
        
    else:
        print("📊 Complex issue - multiple components failing")
        print("💡 SOLUTION: Start with TTS fix first, then tackle pipeline")
    
    # Next Steps
    print(f"\n📋 RECOMMENDED NEXT STEPS:")
    
    if not results.get('tts'):
        print("1. 🔧 Fix Cartesia API key or try alternative TTS service")
        print("2. ⚡ Test with simpler TTS configuration")  
        print("3. 🔍 Check Cartesia account status and quotas")
        
    elif results.get('tts') and not results.get('pipeline'):
        print("1. 🔧 Debug pipeline frame routing in main app")
        print("2. ⚡ Add more logging to VoiceHandler TextFrame generation")
        print("3. 🔍 Check StartFrame timing and TTS initialization")
        
    else:
        print("1. 🔧 Run main app with enhanced logging")
        print("2. ⚡ Compare working isolated tests vs main app")
        print("3. 🔍 Check integration points between components")
    
    print("\n" + "=" * 60)
    total_passes = sum(results.values())
    print(f"🏁 OVERALL RESULT: {total_passes}/3 tests passed")
    
    if total_passes == 3:
        print("🎉 All components work individually - issue is in integration!")
    elif total_passes >= 1:
        print("⚠️ Partial success - can fix remaining issues systematically")
    else:
        print("🚨 Multiple fundamental issues - start with TTS first")

if __name__ == "__main__":
    asyncio.run(run_systematic_tests())

