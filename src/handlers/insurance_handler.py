"""Handler for collecting insurance information."""
import re
from typing import Optional

from src.core.models import ConversationState, Insurance, ConversationPhase
from src.core.conversation_state import state_manager
from src.config.prompts import ERROR_PROMPTS
from src.core.validators import InputValidator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class InsuranceHandler:
    """Handles insurance information collection."""
    
    def __init__(self, call_sid: str):
        self.call_sid = call_sid
        self._collection_step = "payer_name"  # Track what we're collecting
    
    async def process_input(self, user_input: str, state: ConversationState) -> str:
        """Process insurance-related input."""
        
        print(f"🏥 INSURANCE HANDLER: Step={self._collection_step}, Input='{user_input}'")
        
        # Check if we already have complete insurance info
        if state.patient_info.insurance and state.patient_info.insurance.member_id:
            # Move to next phase
            await state_manager.transition_phase(
                self.call_sid,
                ConversationPhase.CHIEF_COMPLAINT
            )
            return "Thank you for the insurance information. Now, what's the main reason you'd like to see a doctor today?"
        
        # Try to parse complete insurance response first (like "My insurance is Kaiser and my member ID is 12345")
        complete_response = await self._try_parse_complete_insurance(user_input, state)
        if complete_response:
            return complete_response
        
        # Fall back to step-by-step collection
        if self._collection_step == "payer_name":
            return await self._handle_payer_name(user_input, state)
        else:
            return await self._handle_member_id(user_input, state)
    
    async def _handle_payer_name(self, user_input: str, state: ConversationState) -> str:
        """Extract and validate insurance payer name."""
        
        # Common insurance providers for validation
        common_payers = [
            "aetna", "blue cross", "cigna", "humana", "kaiser", 
            "united", "anthem", "medicare", "medicaid", "tricare"
        ]
        
        # Check if input contains a recognizable payer
        input_lower = user_input.lower()
        payer_found = None
        
        for payer in common_payers:
            if payer in input_lower:
                payer_found = payer.title()
                break
        
        if not payer_found:
            # Check if user is actually trying to provide insurance info
            # Reject common non-answers, conversational responses, and scheduling language
            non_answers = [
                "yes", "no", "hello", "hi", "okay", "ok", "sure", "can you hear me",
                "i can hear you", "what", "huh", "sorry", "excuse me", "pardon",
                "good", "fine", "great", "perfect", "alright"
            ]
            
            # Reject scheduling/appointment related language - clearly not insurance
            non_insurance_phrases = [
                "schedule", "appointment", "can you help", "doctor", "clinic", 
                "tuesday", "monday", "wednesday", "thursday", "friday", 
                "saturday", "sunday", "today", "tomorrow", "next week",
                "medical emergency", "emergency", "pain", "hurt", "sick"
            ]
            
            # If input contains scheduling language or is too generic, ask again
            if (len(user_input.split()) < 2 or 
                any(phrase in input_lower for phrase in non_answers + non_insurance_phrases) or
                len(user_input.strip()) < 3):
                print(f"🚫 REJECTING INVALID INSURANCE INPUT: '{user_input}'")
                return "I need your insurance provider name. Common providers include Kaiser, Blue Cross, Aetna, Cigna, or United Healthcare. What's your insurance?"
            
            # STILL reject if it doesn't look like an insurance name
            # Only accept if it contains insurance-like words or is a proper noun
            insurance_indicators = ["insurance", "health", "care", "plan", "coverage", "medical"]
            looks_like_company = user_input.strip().replace(" ", "").replace(".", "").isalpha() and len(user_input.strip()) <= 25
            
            if not (any(word in input_lower for word in insurance_indicators) or looks_like_company):
                print(f"🚫 REJECTING NON-INSURANCE INPUT: '{user_input}'")
                return "I need your insurance provider name. Common providers include Kaiser, Blue Cross, Aetna, Cigna, or United Healthcare. What's your insurance?"
            
            # Accept as potential insurance name but flag for review
            payer_found = user_input.strip()
            logger.warning(f"Accepting unrecognized but plausible insurance payer: {payer_found}")
        
        # Store payer name temporarily
        if not state.patient_info.insurance:
            state.patient_info.insurance = Insurance(
                payer_name=payer_found,
                member_id=""  # Temporary
            )
        else:
            state.patient_info.insurance.payer_name = payer_found
        
        self._collection_step = "member_id"
        return f"Thank you. I have {payer_found} as your insurance provider. Now, could you please provide your member ID number? Please speak slowly and clearly."
    
    async def _handle_member_id(self, user_input: str, state: ConversationState) -> str:
        """Extract and validate member ID."""
        
        # Check for non-answers first
        non_answers = ["yes", "no", "okay", "ok", "sure", "what", "huh", "hello", "hi"]
        if any(phrase in user_input.lower() for phrase in non_answers):
            return "I need your insurance member ID number. This is usually found on your insurance card. Could you please provide the ID number?"
        
        # Check if user is just repeating insurance provider name
        insurance_providers = ["aetna", "blue cross", "cigna", "humana", "kaiser", "united", "anthem", "medicare", "medicaid", "tricare"]
        if any(provider in user_input.lower() for provider in insurance_providers):
            return "I already have your insurance provider. I need your member ID number - the unique number on your insurance card, not the company name. Could you please provide that number?"
        
        valid, cleaned = InputValidator.validate_insurance_member_id(user_input)
        if not valid or not cleaned:
            return "I didn't catch the full member ID. Could you please repeat it slowly, including any letters and numbers?"
        
        # Store member ID
        state.patient_info.insurance.member_id = cleaned
        
        # Update state in manager
        await state_manager.update_state(
            self.call_sid,
            insurance=state.patient_info.insurance
        )
        
        # Transition to next phase
        await state_manager.transition_phase(
            self.call_sid,
            ConversationPhase.CHIEF_COMPLAINT
        )
        
        return f"Perfect! I have your insurance information: {state.patient_info.insurance.payer_name} with member ID {cleaned}. Now, what brings you in today? Please describe your main health concern."
    
    async def _try_parse_complete_insurance(self, user_input: str, state: ConversationState) -> Optional[str]:
        """Try to parse complete insurance info from a single response."""
        
        input_lower = user_input.lower()
        
        # Look for patterns like "my insurance is X and my member ID is Y"
        # or "I have X insurance, member ID Y"
        if any(phrase in input_lower for phrase in ["member id", "id number", "insurance"]):
            
            # Common insurance providers
            common_payers = [
                "aetna", "blue cross", "cigna", "humana", "kaiser", 
                "united", "anthem", "medicare", "medicaid", "tricare",
                "geico", "geizo"  # Common variations
            ]
            
            # Try to extract insurance provider
            payer_found = None
            for payer in common_payers:
                if payer in input_lower:
                    payer_found = payer.title()
                    break
            
            # Try to extract member ID (numbers, letters, or combinations)
            import re
            member_id_patterns = [
                r'(?:member\s*id|id\s*number|member\s*number)[\s:]*([A-Z0-9]+)',
                r'(\d{4,})',  # 4+ digit numbers
                r'([A-Z0-9]{5,})'  # 5+ alphanumeric strings
            ]
            
            member_id = None
            for pattern in member_id_patterns:
                match = re.search(pattern, user_input.upper())
                if match:
                    member_id = match.group(1)
                    break
            
            # If we found both, store them
            if payer_found and member_id:
                print(f"🎯 COMPLETE INSURANCE: Provider={payer_found}, ID={member_id}")
                
                # Store insurance information
                state.patient_info.insurance = Insurance(
                    payer_name=payer_found,
                    member_id=member_id
                )
                
                # Update state and transition to next phase
                await state_manager.update_state(self.call_sid, insurance=state.patient_info.insurance)
                await state_manager.transition_phase(self.call_sid, ConversationPhase.CHIEF_COMPLAINT)
                
                return f"Perfect! I have your insurance information: {payer_found} with member ID {member_id}. Now, what brings you in today? Please describe your main health concern."
            
            # If we found just provider, ask for member ID
            elif payer_found:
                print(f"🏥 PARTIAL INSURANCE: Found provider={payer_found}, asking for member ID")
                
                # Store payer name temporarily
                if not state.patient_info.insurance:
                    state.patient_info.insurance = Insurance(payer_name=payer_found, member_id="")
                else:
                    state.patient_info.insurance.payer_name = payer_found
                
                self._collection_step = "member_id"
                return f"Thank you. I have {payer_found} as your insurance provider. Now, could you please provide your member ID number?"
        
        return None  # Could not parse complete insurance