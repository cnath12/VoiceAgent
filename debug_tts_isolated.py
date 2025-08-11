#!/usr/bin/env python3
"""
Isolated TTS debugging to find root cause of caching issue.
Tests multiple scenarios to isolate where the problem occurs.
"""

import asyncio
import aiohttp
import logging
import time
import uuid
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TTSCacheTestRunner:
    def __init__(self, deepgram_api_key: str):
        self.api_key = deepgram_api_key
        self.test_results: Dict[str, List[str]] = {}
        
    async def test_scenario(self, name: str, session_factory, texts: List[str]):
        """Test a specific scenario with different session configurations."""
        print(f"\n🧪 Testing: {name}")
        print("=" * 60)
        
        results = []
        session = session_factory()
        
        try:
            for i, text in enumerate(texts, 1):
                print(f"\n📝 Request {i}: '{text[:50]}...'")
                
                # Make TTS request
                url = "https://api.deepgram.com/v1/speak"
                headers = {
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "text/plain"
                }
                
                # Create payload with proper query parameters
                params = {
                    "model": "aura-asteria-en",
                    "encoding": "linear16", 
                    "container": "none",
                    "sample_rate": 8000
                }
                
                # Send text as raw body content
                start_time = time.time()
                async with session.post(url, params=params, data=text, headers=headers) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        duration = time.time() - start_time
                        audio_size = len(audio_data)
                        
                        print(f"✅ Success: {audio_size} bytes, {duration:.2f}s")
                        results.append(f"Text: '{text[:30]}...', Size: {audio_size}, Duration: {duration:.2f}s")
                        
                        # Check if audio data looks unique (basic heuristic)
                        if i > 1 and audio_size == prev_size:
                            print(f"⚠️  WARNING: Same audio size as previous request - possible caching!")
                        
                        prev_size = audio_size
                    else:
                        error_text = await response.text()
                        print(f"❌ Failed: {response.status} - {error_text}")
                        results.append(f"FAILED: {response.status}")
                
                # Small delay between requests
                await asyncio.sleep(0.5)
                
        except Exception as e:
            print(f"❌ Test failed: {e}")
            results.append(f"ERROR: {e}")
        finally:
            await session.close()
            
        self.test_results[name] = results
        print(f"\n✅ {name} completed: {len(results)} requests")

    async def run_all_tests(self):
        """Run all TTS caching isolation tests."""
        
        test_texts = [
            "Hello! This is Assort Health, your AI appointment scheduler.",
            "I'll need to collect your insurance information.",
            "Could you please tell me your insurance provider name?",
            "Thank you. I have Cigna as your insurance provider.",
            "Perfect! I have your insurance information."
        ]
        
        print("🔍 TTS CACHING ISOLATION TESTS")
        print("=" * 60)
        
        # Test 1: Fresh session for each request (maximum isolation)
        await self.test_scenario(
            "Fresh Session Per Request",
            lambda: aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=aiohttp.TCPConnector(limit=1, force_close=True)
            ),
            test_texts
        )
        
        # Test 2: Single persistent session (normal usage)
        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10)
        )
        
        print(f"\n🧪 Testing: Persistent Session")
        print("=" * 60)
        
        results = []
        try:
            for i, text in enumerate(test_texts, 1):
                print(f"\n📝 Request {i}: '{text[:50]}...'")
                
                url = "https://api.deepgram.com/v1/speak"
                headers = {
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "text/plain"
                }
                
                params = {
                    "model": "aura-asteria-en",
                    "encoding": "linear16",
                    "container": "none",
                    "sample_rate": 8000
                }
                
                start_time = time.time()
                async with session.post(url, params=params, data=text, headers=headers) as response:
                    if response.status == 200:
                        audio_data = await response.read()
                        duration = time.time() - start_time
                        audio_size = len(audio_data)
                        
                        print(f"✅ Success: {audio_size} bytes, {duration:.2f}s")
                        results.append(f"Text: '{text[:30]}...', Size: {audio_size}, Duration: {duration:.2f}s")
                        
                    else:
                        error_text = await response.text()
                        print(f"❌ Failed: {response.status} - {error_text}")
                        results.append(f"FAILED: {response.status}")
                
                await asyncio.sleep(0.5)
                
        except Exception as e:
            print(f"❌ Test failed: {e}")
            results.append(f"ERROR: {e}")
        finally:
            await session.close()
            
        self.test_results["Persistent Session"] = results
        
        # Test 3: Session with anti-cache headers
        await self.test_scenario(
            "Anti-Cache Headers",
            lambda: aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                connector=aiohttp.TCPConnector(limit=1),
                headers={
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            ),
            test_texts
        )

    def print_summary(self):
        """Print summary of all test results."""
        print(f"\n🎯 TTS CACHING TEST SUMMARY")
        print("=" * 60)
        
        for test_name, results in self.test_results.items():
            print(f"\n📊 {test_name}:")
            for result in results:
                print(f"  • {result}")
                
        print(f"\n🔍 ANALYSIS:")
        print("- If all tests show similar audio sizes: No caching detected")
        print("- If persistent session shows identical sizes: Session-level caching")
        print("- If fresh sessions also cache: Server-side caching")
        print("- Look for patterns in audio sizes and durations")

async def main():
    """Main test runner."""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        print("❌ DEEPGRAM_API_KEY environment variable not set!")
        return
        
    if len(api_key) < 20:
        print("⚠️  WARNING: API key looks too short, please verify it's correct")
        
    print(f"🔑 Using API key: {api_key[:8]}...{api_key[-4:]}")
    
    runner = TTSCacheTestRunner(api_key)
    await runner.run_all_tests()
    runner.print_summary()
    
    print(f"\n✅ TTS caching isolation tests completed!")
    print("Review the results above to identify where caching occurs.")

if __name__ == "__main__":
    asyncio.run(main())
