#!/usr/bin/env python3
"""Quick debugging script to verify API keys and basic service connectivity."""

import os
import asyncio
from src.config.settings import get_settings

async def check_credentials():
    """Check all API credentials and basic connectivity."""
    print("🔍 DEBUGGING AUDIO FLOW - Checking API Credentials")
    print("=" * 60)
    
    settings = get_settings()
    
    # Check Deepgram API Key
    print(f"🔑 Deepgram API Key:")
    if not settings.deepgram_api_key:
        print(f"  ❌ MISSING: No Deepgram API key found!")
        return False
    elif len(settings.deepgram_api_key) < 20:
        print(f"  ⚠️  WARNING: Deepgram API key seems too short ({len(settings.deepgram_api_key)} chars)")
        print(f"  Key preview: {settings.deepgram_api_key[:8]}...")
        return False
    else:
        print(f"  ✅ Found: {settings.deepgram_api_key[:8]}...{settings.deepgram_api_key[-4:]} ({len(settings.deepgram_api_key)} chars)")
    
    # Check Cartesia API Key
    print(f"🔑 Cartesia API Key:")
    if not settings.cartesia_api_key:
        print(f"  ❌ MISSING: No Cartesia API key found!")
        return False
    elif len(settings.cartesia_api_key) < 20:
        print(f"  ⚠️  WARNING: Cartesia API key seems too short ({len(settings.cartesia_api_key)} chars)")
        print(f"  Key preview: {settings.cartesia_api_key[:8]}...")
        return False
    else:
        print(f"  ✅ Found: {settings.cartesia_api_key[:8]}...{settings.cartesia_api_key[-4:]} ({len(settings.cartesia_api_key)} chars)")
    
    # Check Twilio credentials
    print(f"🔑 Twilio Credentials:")
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        print(f"  ❌ MISSING: Twilio credentials not found!")
        return False
    else:
        print(f"  ✅ Account SID: {settings.twilio_account_sid[:8]}...{settings.twilio_account_sid[-4:]}")
        print(f"  ✅ Auth Token: {settings.twilio_auth_token[:8]}...{settings.twilio_auth_token[-4:]}")
    
    print("\n🔧 Configuration:")
    print(f"  Model: {settings.deepgram_model}")
    print(f"  Sample Rate: 8000 Hz (Twilio)")
    print(f"  Encoding: {settings.deepgram_encoding}")
    print(f"  Endpointing: {settings.deepgram_endpointing_ms}ms")
    
    return True

async def test_deepgram_connection():
    """Test basic Deepgram connectivity."""
    print("\n🧪 TESTING DEEPGRAM CONNECTION")
    print("=" * 40)
    
    try:
        import httpx
        from src.config.settings import get_settings
        
        settings = get_settings()
        
        # Test basic API connectivity
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.deepgram.com/v1/projects",
                headers={"Authorization": f"Token {settings.deepgram_api_key}"}
            )
            
            if response.status_code == 200:
                print("  ✅ Deepgram API connection successful!")
                projects = response.json()
                print(f"  📊 Found {len(projects.get('projects', []))} project(s)")
                return True
            else:
                print(f"  ❌ Deepgram API error: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return False
                
    except ImportError:
        print("  ⚠️  httpx not available, skipping connection test")
        return True
    except Exception as e:
        print(f"  ❌ Deepgram connection test failed: {e}")
        return False

async def main():
    """Run all debugging checks."""
    print("🚀 VOICE AGENT AUDIO FLOW DEBUGGER")
    print("=" * 50)
    
    # Check credentials
    creds_ok = await check_credentials()
    if not creds_ok:
        print("\n❌ CREDENTIAL ISSUES FOUND!")
        print("   Please check your .env file and ensure all API keys are valid.")
        return
    
    # Test Deepgram connection
    connection_ok = await test_deepgram_connection()
    if not connection_ok:
        print("\n❌ DEEPGRAM CONNECTION ISSUES!")
        print("   Your API key may be invalid or expired.")
        return
    
    print("\n" + "=" * 60)
    print("✅ ALL BASIC CHECKS PASSED!")
    print("\n🔍 NEXT DEBUGGING STEPS:")
    print("   1. Restart your voice agent with the updated logging")
    print("   2. Make a test call and look for these log messages:")
    print("      📡 MEDIA FRAME #X: payload_len=Y bytes")
    print("      🔌 Deepgram connecting...")
    print("      ✅ Deepgram connection successful!")
    print("      🎯 RECEIVED TRANSCRIPTION FRAME: text='...'")
    print("      🔊 TTS STARTED FRAME received")
    print("\n   3. If you see media frames but no transcriptions:")
    print("      - Check Deepgram model compatibility")
    print("      - Verify audio encoding (mulaw vs linear16)")
    print("      - Look for Deepgram error messages")
    print("\n   4. If no media frames appear:")
    print("      - Check Twilio webhook configuration")
    print("      - Verify ngrok/public host setup")
    print("      - Check WebSocket connection logs")

if __name__ == "__main__":
    asyncio.run(main())
