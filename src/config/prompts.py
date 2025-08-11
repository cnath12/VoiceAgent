"""Conversation prompts and templates."""

SYSTEM_PROMPT = """You are a friendly healthcare appointment scheduling assistant. 
Your goal is to efficiently collect information needed to schedule a medical appointment.

Guidelines:
- Be warm and professional
- Keep responses concise and clear
- Show empathy for medical concerns
- Validate information as you collect it
- Use simple language, avoid medical jargon
- If unsure, ask for clarification

Current conversation phase: {phase}
Patient information collected so far: {patient_info}
"""

PHASE_PROMPTS = {
    "greeting": "Hello! Thank you for calling. I'm here to help you schedule an appointment. Before we begin, I need to check - are you experiencing a medical emergency?",
    
    "emergency_check": "If this is a medical emergency, please hang up and dial 911. Otherwise, let's get started with scheduling your appointment.",
    
    "insurance": "I'll need to collect your insurance information. Could you please tell me your insurance provider name and your member ID number?",
    
    "chief_complaint": "What's the main reason you'd like to see a doctor today?",
    
    "demographics": "I need to verify your address. Could you please provide your complete street address including city, state, and zip code?",
    
    "contact_info": "What's the best phone number to reach you at? And may I also have your email address for appointment confirmations?",
    
    "provider_selection": "Based on your needs, I have several doctors available. {provider_options}. Which would you prefer?",
    
    "appointment_scheduling": "I have the following appointment times available: {time_options}. Which works best for you?",
    
    "confirmation": "Perfect! I've scheduled your appointment with {provider} on {date_time}. You'll receive a confirmation email shortly. Is there anything else I can help you with?"
}

ERROR_PROMPTS = {
    "not_understood": "I'm sorry, I didn't quite catch that. Could you please repeat?",
    "invalid_input": "I couldn't validate that information. Let me try again. {specific_request}",
    "system_error": "I apologize for the technical difficulty. Let me transfer you to a human representative who can help."
}
