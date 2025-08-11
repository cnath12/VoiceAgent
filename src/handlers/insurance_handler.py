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
        
        # Check if we already have insurance info
        if state.patient_info.insurance and state.patient_info.insurance.member_id:
            # Move to next phase
            await state_manager.transition_phase(
                self.call_sid,
                ConversationPhase.CHIEF_COMPLAINT
            )
            return "Thank you for the insurance information. Now, what's the main reason you'd like to see a doctor today?"
        
        # Parse insurance information
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
            # Accept whatever they said but flag for human review
            payer_found = user_input.strip()
            logger.warning(f"Unrecognized insurance payer: {payer_found}")
        
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