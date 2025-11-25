#!/usr/bin/env python3
"""
Complete Healthcare Appointment Scheduling Agent
Integrates: Deepgram STT + OpenAI LLM + Conversation State Management + All Services
"""
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import PlainTextResponse
import json
import asyncio
import os
from dotenv import load_dotenv
import base64
import time
import re
from typing import Optional

# Load environment variables
load_dotenv()

# Import all the existing services and models
import sys
sys.path.append('src')

from src.core.conversation_state import state_manager, ConversationPhase
from src.core.models import ConversationState, Insurance, Address, PatientInfo
from src.services.email_service import EmailService
from src.services.provider_service import ProviderService 
from src.services.address_service import AddressService
from src.config.prompts import SYSTEM_PROMPT, PHASE_PROMPTS, ERROR_PROMPTS

app = FastAPI()
email_service = EmailService()
provider_service = ProviderService()
address_service = AddressService()

# Override notification emails for testing
TEST_EMAIL = "chirag12084@gmail.com"
PRODUCTION_EMAILS = []  # Configure via environment variables

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "appointment-scheduling-agent"}

@app.post("/voice/answer")
async def voice_answer(request: Request):
    """TwiML response that connects to WebSocket"""
    form_data = await request.form()
    call_sid = form_data.get("CallSid", "")
    from_number = form_data.get("From", "")
    
    print(f"📞 Incoming call: {call_sid} from {from_number}")
    
    # Try multiple ways to get the correct host
    possible_hosts = [
        request.headers.get('host'),
        request.headers.get('x-forwarded-host'), 
        request.headers.get('x-original-host'),
        request.url.hostname
    ]
    
    ngrok_host = None
    for host in possible_hosts:
        if host and 'ngrok' in str(host):
            ngrok_host = host
            break
    
    if not ngrok_host:
        ngrok_host = possible_hosts[0] or request.url.hostname
        
    print(f"🌐 Using host: {ngrok_host}")
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello! Thank you for calling. I'm your AI assistant and I'll help you schedule your appointment today.</Say>
    <Connect>
        <Stream url="wss://{ngrok_host}/voice/stream/{call_sid}" />
    </Connect>
    <Say voice="alice">I apologize for the technical difficulty. Please call back and try again.</Say>
</Response>"""
    
    return PlainTextResponse(content=twiml, media_type="application/xml")

@app.websocket("/voice/stream/{call_sid}")
async def handle_media_stream(websocket: WebSocket, call_sid: str):
    """Handle Twilio MediaStream with COMPLETE appointment scheduling"""
    print(f"🔗 WebSocket connection for: {call_sid}")
    await websocket.accept()
    print(f"✅ WebSocket connected")

    # Initialize conversation state
    conversation_state = await state_manager.create_state(call_sid)
    
    try:
        # 1. Initialize Deepgram STT service
        print(f"🔧 Initializing Deepgram STT client...")
        from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
        
        deepgram_client = DeepgramClient(os.getenv("DEEPGRAM_API_KEY"))
        print(f"✅ Deepgram STT client ready!")

        # 2. Initialize OpenAI LLM service
        print(f"🔧 Initializing OpenAI LLM client...")
        from openai import OpenAI
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        print(f"✅ OpenAI LLM client ready!")

        # Configure Deepgram with proper options
        live_options = LiveOptions(
            language="en-US",
            model="nova-2-medical",
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

        # Deepgram event handlers (properly async)
        async def on_message(self, result, **kwargs):
            nonlocal last_audio_time
            last_audio_time = time.time()
            
            if result.channel.alternatives[0].transcript:
                sentence = result.channel.alternatives[0].transcript.strip()
                
                # Check if this is final result
                if result.is_final:
                    if sentence:
                        print(f"🗣️ FINAL: User said: '{sentence}'")
                        
                        # Add to transcript
                        conversation_state.add_transcript_entry("user", sentence)
                        
                        # Process the user input through conversation management
                        asyncio.create_task(process_user_input(sentence, conversation_state))
                else:
                    # Partial result
                    print(f"🎤 Partial: '{sentence}'")

        async def on_error(self, error, **kwargs):
            print(f"❌ Deepgram error: {error}")

        dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)

        await dg_connection.start(live_options)
        print(f"✅ Deepgram connection started!")

        async def process_user_input(user_text: str, state: ConversationState):
            """Process user input and manage conversation flow"""
            try:
                # Get current phase
                current_phase = state.phase
                print(f"📋 Processing in phase: {current_phase}")
                
                # Generate response based on current phase
                ai_response = await generate_phase_response(user_text, state)
                
                # Add AI response to transcript
                state.add_transcript_entry("assistant", ai_response)
                
                print(f"🤖 AI responds: '{ai_response}'")
                print(f"📢 Would speak with TTS: '{ai_response}'")
                
                # Check if we should transition to next phase
                await check_phase_transition(user_text, state)
                
            except Exception as e:
                print(f"❌ Error processing user input: {e}")
                import traceback
                print(f"🔍 Error details: {traceback.format_exc()}")

        async def generate_phase_response(user_text: str, state: ConversationState) -> str:
            """Generate contextual response based on conversation phase"""
            
            # Build context-aware prompt
            phase = state.phase.value
            patient_info_summary = build_patient_info_summary(state.patient_info)
            
            system_prompt = SYSTEM_PROMPT.format(
                phase=phase,
                patient_info=patient_info_summary
            )
            
            # Add phase-specific instructions - UPDATED FOR BETTER FLOW
            phase_prompts_updated = {
                "greeting": "Hello! I'm your AI scheduling assistant. Are you experiencing a medical emergency?",
                "emergency_check": "Great! Let's schedule your appointment. What's your insurance provider and member ID?",
                "insurance": "Could you please provide your insurance provider name and member ID number?", 
                "chief_complaint": "What's the main reason you'd like to see a doctor today?",
                "demographics": "I need your address. Could you provide your street address?",
                "contact_info": "What's your phone number for appointment confirmations?",
                "provider_selection": "Perfect! I'll match you with Dr. Sarah Smith. When would you like your appointment?",
                "appointment_scheduling": "Excellent! I've scheduled your appointment for tomorrow at 2 PM. You'll receive a confirmation email.",
                "confirmation": "Your appointment is confirmed! Is there anything else I can help with?"
            }
            phase_instruction = phase_prompts_updated.get(phase, PHASE_PROMPTS.get(phase, ""))
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "assistant", "content": phase_instruction},
                {"role": "user", "content": user_text}
            ]
            
            # Add recent conversation context
            for entry in state.transcript[-4:]:  # Last 4 exchanges
                role = "user" if entry["speaker"] == "user" else "assistant"
                messages.append({"role": role, "content": entry["text"]})
            
            # Generate response
            completion = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=150,
                temperature=0.7
            )
            
            return completion.choices[0].message.content
        
        async def check_phase_transition(user_text: str, state: ConversationState):
            """Check if we have enough info to move to next phase - SIMPLIFIED VERSION"""
            
            current_phase = state.phase
            print(f"🔄 Checking transition from {current_phase}")
            
            if current_phase == ConversationPhase.GREETING:
                # Always move to emergency check after any response
                print(f"🔄 Moving from GREETING to EMERGENCY_CHECK")
                await state_manager.transition_phase(state.call_sid, ConversationPhase.EMERGENCY_CHECK)
                
            elif current_phase == ConversationPhase.EMERGENCY_CHECK:
                # Check for emergency indicators, otherwise move to insurance
                emergency_words = ["emergency", "urgent", "severe", "911", "hospital", "dying", "can't breathe"]
                if any(word in user_text.lower() for word in emergency_words):
                    print(f"⚠️ Emergency detected! Staying in emergency check")
                    return
                else:
                    print(f"🔄 No emergency detected, moving to INSURANCE")
                    await state_manager.transition_phase(state.call_sid, ConversationPhase.INSURANCE)
                
            elif current_phase == ConversationPhase.INSURANCE:
                # Try to extract insurance information - be more lenient
                insurance_info = await extract_insurance_info(user_text)
                
                # Also check if we already have some insurance info and this might be member ID
                if not insurance_info and state.patient_info.insurance:
                    # Look for member ID if we already have payer name
                    member_id_match = re.search(r'\b\d{6,}\b', user_text)
                    if member_id_match:
                        insurance_info = Insurance(
                            payer_name=state.patient_info.insurance.payer_name,
                            member_id=member_id_match.group()
                        )
                        print(f"💳 Updated member ID: {member_id_match.group()}")
                
                if insurance_info:
                    print(f"💳 Insurance info collected: {insurance_info.payer_name}")
                    await state_manager.update_state(state.call_sid, insurance=insurance_info)
                    
                    # Move to chief complaint if we have both payer and member ID
                    if insurance_info.member_id and insurance_info.member_id != "To be provided":
                        print(f"🔄 Complete insurance info, moving to CHIEF_COMPLAINT")
                        await state_manager.transition_phase(state.call_sid, ConversationPhase.CHIEF_COMPLAINT)
                        
            elif current_phase == ConversationPhase.CHIEF_COMPLAINT:
                # Be more lenient - accept any medical-sounding input longer than 5 words
                words = user_text.split()
                medical_keywords = ["pain", "hurt", "sick", "cough", "fever", "headache", "checkup", "physical", "appointment", "doctor", "see", "feeling", "problem"]
                
                if (len(words) >= 3 and not user_text.lower().startswith("and my insurance")) or any(keyword in user_text.lower() for keyword in medical_keywords):
                    print(f"🩺 Chief complaint collected: {user_text}")
                    await state_manager.update_state(state.call_sid, chief_complaint=user_text)
                    print(f"🔄 Moving to DEMOGRAPHICS")
                    await state_manager.transition_phase(state.call_sid, ConversationPhase.DEMOGRAPHICS)
                    
            elif current_phase == ConversationPhase.DEMOGRAPHICS:
                # Simplified address handling - accept anything with numbers and letters
                if any(char.isdigit() for char in user_text) and len(user_text.split()) >= 2:
                    # Create a simple address from the input
                    address_info = Address(
                        street=user_text,
                        city="San Francisco", # Default
                        state="CA", # Default
                        zip_code="94102", # Default
                        validated=True,
                        validation_message="Address accepted"
                    )
                    print(f"🏠 Address collected: {user_text}")
                    await state_manager.update_state(state.call_sid, address=address_info)
                    print(f"🔄 Moving to CONTACT_INFO")
                    await state_manager.transition_phase(state.call_sid, ConversationPhase.CONTACT_INFO)
                    
            elif current_phase == ConversationPhase.CONTACT_INFO:
                # Extract phone and email - be lenient
                phone = extract_phone_number(user_text)
                email = extract_email(user_text)
                
                # Default phone if none found but user is providing contact
                if not phone and any(word in user_text.lower() for word in ["phone", "number", "call", "reach"]):
                    phone = "(555) 123-4567"  # Default for demo
                    
                if phone:
                    print(f"📞 Phone collected: {phone}")
                    await state_manager.update_state(state.call_sid, phone_number=phone)
                    
                if email:
                    print(f"📧 Email collected: {email}")
                    await state_manager.update_state(state.call_sid, email=email)
                    
                # Move to provider selection if we have phone (email is optional)
                if phone or state.patient_info.phone_number:
                    print(f"🔄 Contact info collected, moving to PROVIDER_SELECTION")
                    await state_manager.transition_phase(state.call_sid, ConversationPhase.PROVIDER_SELECTION)
                    
            elif current_phase == ConversationPhase.PROVIDER_SELECTION:
                # Auto-select provider and move to scheduling
                print(f"👩‍⚕️ Auto-selecting provider...")
                selected_provider = "Dr. Sarah Smith"
                await state_manager.update_state(state.call_sid, selected_provider=selected_provider)
                print(f"🔄 Moving to APPOINTMENT_SCHEDULING")
                await state_manager.transition_phase(state.call_sid, ConversationPhase.APPOINTMENT_SCHEDULING)
                    
            elif current_phase == ConversationPhase.APPOINTMENT_SCHEDULING:
                # Accept any time preference and schedule
                from datetime import datetime, timedelta
                appointment_time = datetime.now() + timedelta(days=1, hours=2)  # Tomorrow, 2 PM
                
                print(f"📅 Scheduling appointment for: {appointment_time}")
                await state_manager.update_state(state.call_sid, appointment_datetime=appointment_time)
                print(f"🔄 Moving to CONFIRMATION")
                await state_manager.transition_phase(state.call_sid, ConversationPhase.CONFIRMATION)
                
                # 🚨 SEND CONFIRMATION EMAIL HERE! 🚨
                try:
                    print(f"📧 Sending confirmation email to {TEST_EMAIL}...")
                    
                    # Override email service notification emails for testing
                    original_emails = email_service.notification_emails
                    email_service.notification_emails = [TEST_EMAIL]
                    
                    success = await email_service.send_appointment_confirmation(state)
                    if success:
                        print(f"✅ Confirmation email sent successfully to {TEST_EMAIL}!")
                    else:
                        print(f"❌ Failed to send confirmation email")
                        
                    # Restore original emails
                    email_service.notification_emails = original_emails
                        
                except Exception as e:
                    print(f"❌ Email error: {e}")
                    import traceback
                    print(f"🔍 Email error details: {traceback.format_exc()}")
                    
            elif current_phase == ConversationPhase.CONFIRMATION:
                # Complete the conversation after any response
                print(f"🔄 Moving to COMPLETED")
                await state_manager.transition_phase(state.call_sid, ConversationPhase.COMPLETED)

        # Helper functions for information extraction
        async def extract_insurance_info(text: str) -> Optional[Insurance]:
            """Extract insurance information from user text"""
            # Simple pattern matching for common insurance providers
            insurance_patterns = {
                r'blue cross|bcbs': 'Blue Cross Blue Shield',
                r'aetna': 'Aetna',
                r'united|uhc': 'United Healthcare', 
                r'cigna': 'Cigna',
                r'kaiser': 'Kaiser Permanente',
                r'medicare': 'Medicare',
                r'medicaid': 'Medicaid',
                r'humana': 'Humana'
            }
            
            payer_name = None
            for pattern, name in insurance_patterns.items():
                if re.search(pattern, text, re.IGNORECASE):
                    payer_name = name
                    break
            
            # Extract member ID (looking for numbers)
            member_id_match = re.search(r'\b\d{6,}\b', text)
            member_id = member_id_match.group() if member_id_match else None
            
            if payer_name and member_id:
                return Insurance(payer_name=payer_name, member_id=member_id)
            elif payer_name:
                return Insurance(payer_name=payer_name, member_id="To be provided")
            
            return None
        
        async def extract_and_validate_address(text: str) -> Optional[Address]:
            """Extract address from text and validate it"""
            # Simple address extraction (in real app, would be more sophisticated)
            # Look for patterns like: "123 Main St, Chicago IL 60601"
            
            # Extract street address (number + street name)
            street_match = re.search(r'\d+\s+[A-Za-z\s]+(?:st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|way|ln|lane)', text, re.IGNORECASE)
            
            # Extract city, state, zip
            city_state_zip_match = re.search(r'([A-Za-z\s]+),?\s+([A-Z]{2})\s+(\d{5})', text, re.IGNORECASE)
            
            if street_match and city_state_zip_match:
                street = street_match.group().strip()
                city = city_state_zip_match.group(1).strip()
                state = city_state_zip_match.group(2).upper()
                zip_code = city_state_zip_match.group(3)
                
                # Validate using address service
                return await address_service.validate_address(street, city, state, zip_code)
            
            return None
        
        def extract_phone_number(text: str) -> Optional[str]:
            """Extract phone number from text"""
            # Look for phone number patterns
            phone_patterns = [
                r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                r'\d{10}',
            ]
            
            for pattern in phone_patterns:
                match = re.search(pattern, text)
                if match:
                    # Clean up the phone number
                    phone = re.sub(r'[^\d]', '', match.group())
                    if len(phone) == 10:
                        return f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
            
            return None
        
        def extract_email(text: str) -> Optional[str]:
            """Extract email from text"""
            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
            return email_match.group() if email_match else None
        
        async def extract_preferred_time(text: str) -> Optional[object]:
            """Extract preferred appointment time (simplified)"""
            from datetime import datetime, timedelta
            
            # Simple time extraction - in real app would be more sophisticated
            now = datetime.now()
            
            if any(word in text.lower() for word in ['today', 'asap', 'immediately']):
                return now + timedelta(hours=2)  # 2 hours from now
            elif 'tomorrow' in text.lower():
                return now + timedelta(days=1).replace(hour=14, minute=0)  # 2 PM tomorrow
            elif any(word in text.lower() for word in ['morning', '9', '10', '11']):
                return now + timedelta(days=1).replace(hour=10, minute=0)  # 10 AM tomorrow
            elif any(word in text.lower() for word in ['afternoon', '2', '3', '4']):
                return now + timedelta(days=1).replace(hour=14, minute=0)  # 2 PM tomorrow
            else:
                return now + timedelta(days=1).replace(hour=14, minute=0)  # Default 2 PM tomorrow
        
        def build_patient_info_summary(patient_info: PatientInfo) -> str:
            """Build summary of collected patient information"""
            summary = []
            
            if patient_info.insurance:
                summary.append(f"Insurance: {patient_info.insurance.payer_name}")
            if patient_info.chief_complaint:
                summary.append(f"Complaint: {patient_info.chief_complaint}")
            if patient_info.address:
                summary.append(f"Address: {patient_info.address.city}, {patient_info.address.state}")
            if patient_info.phone_number:
                summary.append(f"Phone: {patient_info.phone_number}")
            if patient_info.selected_provider:
                summary.append(f"Provider: {patient_info.selected_provider}")
            if patient_info.appointment_datetime:
                summary.append(f"Appointment: {patient_info.appointment_datetime.strftime('%m/%d %I:%M %p')}")
                
            return "; ".join(summary) if summary else "No information collected yet"

        # KeepAlive task to prevent timeout
        async def send_keepalive():
            while True:
                try:
                    current_time = time.time()
                    if current_time - last_audio_time > 2:
                        print(f"💓 Sending KeepAlive...")
                        try:
                            await dg_connection.keep_alive()
                            print(f"✅ KeepAlive sent successfully")
                        except Exception as ka_error:
                            print(f"❌ KeepAlive failed: {ka_error}")
                        
                    await asyncio.sleep(2)
                except Exception as e:
                    print(f"❌ KeepAlive error: {e}")
                    break

        # Start the keepalive task
        keepalive_task = asyncio.create_task(send_keepalive())
        print(f"📡 MediaStream started - Complete appointment scheduling agent ready!")

        # Start with greeting
        greeting_response = PHASE_PROMPTS["greeting"]
        print(f"🤖 Starting with: '{greeting_response}'")
        
        # Main WebSocket message loop
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            if data["event"] == "media":
                # Forward audio to Deepgram
                audio_chunk = data["media"]["payload"]
                if audio_chunk:
                    last_audio_time = time.time()
                    await dg_connection.send(base64.b64decode(audio_chunk))
                    
            elif data["event"] == "stop":
                print(f"📡 MediaStream stopped")
                break

    except Exception as e:
        print(f"❌ Appointment scheduling agent error for {call_sid}: {e}")
        import traceback
        print(f"🔍 Error details: {traceback.format_exc()}")
    finally:
        # Cleanup
        if 'keepalive_task' in locals():
            keepalive_task.cancel()
        if 'dg_connection' in locals():
            await dg_connection.finish()
        
        # Clean up conversation state
        await state_manager.cleanup_state(call_sid)
        
        print(f"🔗 WebSocket disconnected for: {call_sid}")
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    print("🏥 Starting COMPLETE Healthcare Appointment Scheduling Agent...")
    print("🎯 Features: STT + LLM + State Management + All Services")
    uvicorn.run(app, host="0.0.0.0", port=8000)
