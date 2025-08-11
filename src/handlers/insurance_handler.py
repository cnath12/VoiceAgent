"""Handler for collecting insurance information - FIXED VERSION."""
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
        self._retry_count = 0  # Track retries to prevent infinite loops
        self._last_input = ""  # Track last input to detect duplicates
    
    async def process_input(self, user_input: str, state: ConversationState) -> str:
        """Process insurance-related input."""
        
        print(f"🏥 INSURANCE HANDLER: Step={self._collection_step}, Input='{user_input}'")
        
        # Check for duplicate input (user might be repeating themselves)
        if user_input.strip().lower() == self._last_input.strip().lower():
            print(f"⚠️ Duplicate input detected, processing anyway")
        self._last_input = user_input
        
        # Check if we already have complete insurance info
        if state.patient_info.insurance and state.patient_info.insurance.member_id and state.patient_info.insurance.member_id != "":
            print(f"✅ Insurance complete, moving to chief complaint")
            # Move to next phase
            await state_manager.transition_phase(
                self.call_sid,
                ConversationPhase.CHIEF_COMPLAINT
            )
            return "Thank you for the insurance information. Now, what's the main reason you'd like to see a doctor today?"
        
        # Try to parse complete insurance response first
        complete_response = await self._try_parse_complete_insurance(user_input, state)
        if complete_response:
            return complete_response
        
        # Fall back to step-by-step collection
        if self._collection_step == "payer_name":
            return await self._handle_payer_name(user_input, state)
        else:
            return await self._handle_member_id(user_input, state)
    
    async def _handle_payer_name(self, user_input: str, state: ConversationState) -> str:
        """Extract and validate insurance payer name - MORE LENIENT VERSION."""
        
        # Increment retry count
        self._retry_count += 1
        
        # If we've asked too many times, just accept whatever they say
        if self._retry_count > 2:
            print(f"⚠️ Max retries reached, accepting input as-is: '{user_input}'")
            payer_found = user_input.strip()
            
            # Store and move on
            if not state.patient_info.insurance:
                state.patient_info.insurance = Insurance(
                    payer_name=payer_found,
                    member_id=""
                )
            else:
                state.patient_info.insurance.payer_name = payer_found
            
            self._collection_step = "member_id"
            self._retry_count = 0  # Reset for next step
            return f"Thank you. I have {payer_found} as your insurance provider. Now, could you please provide your member ID number?"
        
        # Common insurance providers - expanded list
        common_payers = {
            "aetna": "Aetna",
            "blue cross": "Blue Cross Blue Shield",
            "bcbs": "Blue Cross Blue Shield",
            "blue shield": "Blue Cross Blue Shield",
            "cigna": "Cigna",
            "humana": "Humana",
            "kaiser": "Kaiser Permanente",
            "united": "United Healthcare",
            "uhc": "United Healthcare",
            "anthem": "Anthem",
            "medicare": "Medicare",
            "medicaid": "Medicaid",
            "tricare": "Tricare",
            "wellpoint": "WellPoint",
            "centene": "Centene",
            "molina": "Molina Healthcare",
            "healthnet": "Health Net",
            "carefirst": "CareFirst",
            "highmark": "Highmark",
            "oxford": "Oxford Health"
        }
        
        # Check if input contains a recognizable payer (avoid using meta complaints as payer)
        input_lower = user_input.lower()
        # If the input looks like a meta-comment about the bot, do not accept as payer
        meta_phrases = [
            "you were supposed", "why did you", "stop speaking", "can you hear",
            "hello?", "are you there", "did you stop"
        ]
        if any(p in input_lower for p in meta_phrases):
            return "I need your insurance provider name, like Kaiser, Blue Cross, Aetna, Cigna, or UnitedHealthcare. What insurance do you have?"
        payer_found = None
        
        # First, check for exact matches
        for pattern, name in common_payers.items():
            if pattern in input_lower:
                payer_found = name
                print(f"✅ Recognized insurance: {payer_found}")
                break
        
        # If not found, be more lenient
        if not payer_found:
            # Remove common filler words
            cleaned_input = user_input.strip()
            for word in ["my", "insurance", "is", "i have", "it's", "its", "the", "provider"]:
                cleaned_input = cleaned_input.lower().replace(word, "").strip()
            
            # Check if what's left looks like it could be an insurance name
            # (at least 3 characters, not just numbers)
            if len(cleaned_input) >= 3 and not cleaned_input.isdigit():
                # Check for very short responses that are clearly not insurance
                non_answers = ["yes", "no", "ok", "okay", "sure", "what", "huh", "um", "uh"]
                if cleaned_input not in non_answers and len(cleaned_input) >= 3:
                    payer_found = user_input.strip()  # Use original input
                    print(f"⚠️ Accepting unrecognized but plausible insurance: {payer_found}")
                    logger.warning(f"Unrecognized insurance payer: {payer_found}")
        
        if not payer_found:
            # Don't be too picky - guide them
            return "I need your insurance provider name. For example, you might say 'Kaiser' or 'Blue Cross' or the name on your insurance card. What insurance do you have?"
        
        # Store payer name
        if not state.patient_info.insurance:
            state.patient_info.insurance = Insurance(
                payer_name=payer_found,
                member_id=""
            )
        else:
            state.patient_info.insurance.payer_name = payer_found
        
        # Update state immediately
        await state_manager.update_state(
            self.call_sid,
            insurance=state.patient_info.insurance
        )
        
        self._collection_step = "member_id"
        self._retry_count = 0  # Reset for next step
        return f"Thank you. I have {payer_found} as your insurance provider. Now, could you please provide your member ID number?"
    
    async def _handle_member_id(self, user_input: str, state: ConversationState) -> str:
        """Extract and validate member ID - MORE LENIENT VERSION."""
        
        # Increment retry count
        self._retry_count += 1
        
        # If we've asked too many times, accept whatever looks like an ID
        if self._retry_count > 2:
            # Extract any alphanumeric sequence as member ID
            cleaned = re.sub(r'[^A-Z0-9]', '', user_input.upper())
            if len(cleaned) >= 4:  # At least 4 characters
                print(f"⚠️ Max retries reached, accepting as member ID: {cleaned}")
                state.patient_info.insurance.member_id = cleaned
                
                # Update and transition
                await state_manager.update_state(
                    self.call_sid,
                    insurance=state.patient_info.insurance
                )
                await state_manager.transition_phase(
                    self.call_sid,
                    ConversationPhase.CHIEF_COMPLAINT
                )
                self._retry_count = 0
                return f"Perfect! I have your insurance information. Now, what brings you in today? Please describe your main health concern."
        
        # Check if they're just repeating the insurance provider name
        if state.patient_info.insurance and state.patient_info.insurance.payer_name:
            if state.patient_info.insurance.payer_name.lower() in user_input.lower():
                return "I already have your insurance provider. I need your member ID number - the unique number on your insurance card. Could you please provide that?"
        
        # More lenient validation
        valid, cleaned = InputValidator.validate_insurance_member_id(user_input)
        
        # If validation fails, try a simpler approach
        if not valid or not cleaned:
            # Look for any sequence of numbers/letters that could be an ID
            # Remove common words first
            temp = user_input.upper()
            for word in ["MY", "MEMBER", "ID", "NUMBER", "IS", "IT'S", "IT IS", "THE"]:
                temp = temp.replace(word, " ")
            
            # Find alphanumeric sequences
            matches = re.findall(r'\b[A-Z0-9]{4,}\b', temp)
            if matches:
                cleaned = matches[0]  # Take the first match
                valid = True
                print(f"✅ Extracted member ID from input: {cleaned}")
        
        if not valid or not cleaned:
            return "I need your member ID number from your insurance card. It's usually a combination of letters and numbers. Could you please say it slowly?"
        
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
        
        self._retry_count = 0
        return f"Perfect! I have your insurance information: {state.patient_info.insurance.payer_name} with member ID {cleaned}. Now, what brings you in today?"
    
    async def _try_parse_complete_insurance(self, user_input: str, state: ConversationState) -> Optional[str]:
        """Try to parse complete insurance info from a single response."""
        
        input_lower = user_input.lower()
        
        # Look for patterns that indicate both insurance and member ID
        has_both = any(phrase in input_lower for phrase in ["member id", "id is", "number is"]) and \
                   any(phrase in input_lower for phrase in ["insurance", "have", "my"])
        
        if not has_both:
            return None
        
        # Expanded insurance providers
        common_payers = {
            "aetna": "Aetna",
            "blue cross": "Blue Cross Blue Shield",
            "bcbs": "Blue Cross Blue Shield",
            "cigna": "Cigna",
            "humana": "Humana",
            "kaiser": "Kaiser Permanente",
            "united": "United Healthcare",
            "anthem": "Anthem",
            "medicare": "Medicare",
            "medicaid": "Medicaid",
            "tricare": "Tricare"
        }
        
        # Try to extract insurance provider
        payer_found = None
        for pattern, name in common_payers.items():
            if pattern in input_lower:
                payer_found = name
                break
        
        # Try to extract member ID
        # Look for patterns after "id" or "number"
        member_id = None
        patterns = [
            r'(?:member\s*id|id\s*number|id\s*is|number\s*is)[\s:]*([A-Z0-9]+)',
            r'([A-Z0-9]{6,})',  # Any 6+ character alphanumeric
        ]
        
        for pattern in patterns:
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
            
            self._retry_count = 0
            return f"Perfect! I have your insurance information: {payer_found} with member ID {member_id}. Now, what brings you in today? Please describe your main health concern."
        
        return None  # Could not parse complete insurance