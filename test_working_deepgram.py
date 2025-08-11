#!/usr/bin/env python3
"""
Working Deepgram Voice Agent - Direct Client Approach
This was the version that worked with transcription and responses!
"""

import os
import asyncio
import json
import base64
import time
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import PlainTextResponse
from openai import OpenAI
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

# Initialize clients
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
deepgram_client = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))

@app.post("/voice/answer")
async def voice_answer(request: Request):
    """Handle incoming Twilio voice call"""
    form = await request.form()
    call_sid = form.get("CallSid")
    from_number = form.get("From")
    
    print(f"📞 Incoming call: {call_sid} from {from_number}")
    
    # Get host for WebSocket URL
    host = request.headers.get('x-forwarded-host', request.url.hostname)
    
    # TwiML response
    twiml = f'''<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Connect>
            <Stream url="wss://{host}/voice/stream/{call_sid}" />
        </Connect>
        <Say>Sorry, we couldn't connect your call. Please try again.</Say>
    </Response>'''
    
    return PlainTextResponse(content=twiml, media_type="application/xml")

@app.websocket("/voice/stream/{call_sid}")
async def handle_media_stream(websocket: WebSocket, call_sid: str):
    """Handle Twilio MediaStream - WORKING VERSION"""
    print(f"🔗 WebSocket connection for: {call_sid}")
    await websocket.accept()
    print(f"✅ WebSocket connected")
    
    try:
        # Configure Deepgram with working settings
        live_options = LiveOptions(
            language="en-US",
            model="nova-2-medical",  # This was working!
            punctuate=True,
            interim_results=True,
            endpointing=300,  # 300ms silence before finalizing
            smart_format=True,
            encoding="mulaw",  # Twilio uses μ-law encoding  
            sample_rate=8000,  # Twilio uses 8kHz
            channels=1,        # Mono
        )

        print(f"🔧 Starting Deepgram connection...")
        dg_connection = deepgram_client.listen.asyncwebsocket.v("1")
        
        # Track variables
        last_audio_time = time.time()

        # Deepgram event handlers - THIS WAS WORKING!
        async def on_message(self, result, **kwargs):
            nonlocal last_audio_time
            last_audio_time = time.time()
            
            if result.channel.alternatives[0].transcript:
                sentence = result.channel.alternatives[0].transcript.strip()
                
                # Check if this is final result
                if result.is_final:
                    if sentence:
                        print(f"🗣️ FINAL: User said: '{sentence}'")
                        
                        # Generate AI response using OpenAI
                        await generate_ai_response(sentence)
                else:
                    # Partial result
                    print(f"🎤 Partial: '{sentence}'")

        async def on_error(self, error, **kwargs):
            print(f"❌ Deepgram error: {error}")

        async def generate_ai_response(user_text: str):
            """Generate AI response - THIS WAS WORKING!"""
            try:
                print(f"🤖 Generating response for: '{user_text}'")
                
                # Simple prompt for testing
                prompt = f"""You are a helpful healthcare assistant. 
                The user said: "{user_text}"
                
                Respond naturally and helpfully. Keep it brief (1-2 sentences)."""
                
                response = openai_client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=100,
                    temperature=0.7
                )
                
                ai_response = response.choices[0].message.content.strip()
                print(f"🤖 AI Response: '{ai_response}'")
                
                # NOTE: In the working version, this was logged but not spoken
                # The TTS part would need to be added separately
                print(f"📢 Would speak: '{ai_response}'")
                
            except Exception as e:
                print(f"❌ AI response error: {e}")

        # Register event handlers
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        await dg_connection.start(live_options)
        print(f"✅ Deepgram connection started!")

        # Keepalive task for Deepgram
        async def send_keepalive():
            while True:
                try:
                    await asyncio.sleep(2)  # Send keepalive every 2 seconds
                    if time.time() - last_audio_time > 30:  # No audio for 30 seconds
                        print(f"⏱️ No audio for 30s, sending keepalive...")
                    await dg_connection.send(b'')  # Empty keepalive
                except Exception as e:
                    print(f"❌ Keepalive error: {e}")
                    break

        # Start the keepalive task
        keepalive_task = asyncio.create_task(send_keepalive())
        print(f"📡 MediaStream started - Working Deepgram agent ready!")

        # Send initial greeting message
        print(f"🤖 Starting with greeting...")
        
        # Main WebSocket message loop - THIS WAS THE WORKING PART!
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            if data["event"] == "media":
                # Forward audio directly to Deepgram - THIS WORKED!
                audio_chunk = data["media"]["payload"]
                if audio_chunk:
                    last_audio_time = time.time()
                    # Decode base64 and send to Deepgram
                    await dg_connection.send(base64.b64decode(audio_chunk))
                    
            elif data["event"] == "stop":
                print(f"📡 MediaStream stopped")
                break

    except Exception as e:
        print(f"❌ Working agent error for {call_sid}: {e}")
        import traceback
        print(f"🔍 Error details: {traceback.format_exc()}")
    finally:
        # Cleanup
        if 'keepalive_task' in locals():
            keepalive_task.cancel()
        if 'dg_connection' in locals():
            await dg_connection.finish()
        
        print(f"🔗 WebSocket disconnected for: {call_sid}")
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting WORKING Deepgram Voice Agent...")
    print("🎯 This version uses direct Deepgram client - was transcribing correctly!")
    uvicorn.run(app, host="0.0.0.0", port=8001)  # Different port to avoid conflicts
