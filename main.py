#!/usr/bin/env python3
"""
Voice AI Agent - Main FastAPI Application
"""
import os
import asyncio
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn
from loguru import logger

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Voice AI Agent",
    description="A voice AI agent using Pipecat and Twilio",
    version="1.0.0"
)

# Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class TwilioWebhookRequest(BaseModel):
    """Twilio webhook request model"""
    CallSid: str
    From: str
    To: str
    CallStatus: str


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Voice AI Agent is running!", "status": "healthy"}


@app.get("/health")
async def health_check():
    """Detailed health check"""
    config_status = {
        "twilio_configured": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN),
        "openai_configured": bool(OPENAI_API_KEY),
        "phone_number_set": bool(TWILIO_PHONE_NUMBER)
    }
    
    return {
        "status": "healthy",
        "service": "Voice AI Agent",
        "configuration": config_status
    }


@app.post("/voice-webhook")
async def voice_webhook(request: Request):
    """
    Twilio voice webhook endpoint
    This is where Twilio will send call events
    """
    try:
        # Get form data from Twilio
        form_data = await request.form()
        call_data = dict(form_data)
        
        logger.info(f"Received call: {call_data}")
        
        # For now, return a simple TwiML response
        twiml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello! Welcome to your AI voice agent. This is a test response. The agent is not yet fully configured, but your Twilio integration is working!</Say>
    <Pause length="1"/>
    <Say voice="alice">Please check your server logs and configure your AI services.</Say>
</Response>"""
        
        return PlainTextResponse(
            content=twiml_response,
            media_type="application/xml"
        )
        
    except Exception as e:
        logger.error(f"Error in voice webhook: {e}")
        # Return error TwiML
        error_twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Sorry, there was an error processing your call. Please try again later.</Say>
</Response>"""
        return PlainTextResponse(
            content=error_twiml,
            media_type="application/xml"
        )


@app.post("/status-webhook")
async def status_webhook(request: Request):
    """
    Twilio status webhook endpoint
    Receives call status updates
    """
    try:
        form_data = await request.form()
        status_data = dict(form_data)
        
        logger.info(f"Call status update: {status_data}")
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Error in status webhook: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    # Check configuration
    missing_config = []
    if not TWILIO_ACCOUNT_SID:
        missing_config.append("TWILIO_ACCOUNT_SID")
    if not TWILIO_AUTH_TOKEN:
        missing_config.append("TWILIO_AUTH_TOKEN")
    if not TWILIO_PHONE_NUMBER:
        missing_config.append("TWILIO_PHONE_NUMBER")
    if not OPENAI_API_KEY:
        missing_config.append("OPENAI_API_KEY")
    
    if missing_config:
        logger.warning(f"Missing configuration: {', '.join(missing_config)}")
        logger.warning("Please check your .env file")
    
    logger.info("Starting Voice AI Agent server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
