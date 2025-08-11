"""Handler for collecting chief medical complaint."""
from typing import Optional

from src.core.models import ConversationState, ConversationPhase
from src.core.conversation_state import state_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SymptomHandler:
    """Handles chief complaint and symptom collection."""
    
    def __init__(self, call_sid: str):
        self.call_sid = call_sid
        self._asked_for_duration = False
    
    async def process_input(self, user_input: str, state: ConversationState) -> str:
        """Process symptom-related input."""
        
        # If we haven't collected the complaint yet
        if not state.patient_info.chief_complaint:
            return await self._handle_initial_complaint(user_input, state)
        
        # If we need duration/severity info
        if not self._asked_for_duration:
            return await self._handle_symptom_details(user_input, state)
        
        # Move to next phase
        await state_manager.transition_phase(
            self.call_sid,
            ConversationPhase.DEMOGRAPHICS
        )
        return "Thank you for that information. Now I need to collect your address for our records. Could you please provide your complete street address?"
    
    async def _handle_initial_complaint(self, user_input: str, state: ConversationState) -> str:
        """Process the initial complaint."""
        
        # Store the complaint
        state.patient_info.chief_complaint = user_input.strip()
        
        # Update state
        await state_manager.update_state(
            self.call_sid,
            chief_complaint=state.patient_info.chief_complaint
        )
        
        # Check for urgent keywords
        urgent_keywords = ["emergency", "chest pain", "can't breathe", "bleeding", "unconscious"]
        if any(keyword in user_input.lower() for keyword in urgent_keywords):
            return "This sounds like it may need immediate attention. If this is an emergency, please hang up and dial 911. Otherwise, how long have you been experiencing these symptoms?"
        
        self._asked_for_duration = True
        return "I understand. How long have you been experiencing these symptoms? And on a scale of 1 to 10, how would you rate your discomfort?"
    
    async def _handle_symptom_details(self, user_input: str, state: ConversationState) -> str:
        """Handle additional symptom details."""
        
        # Extract pain scale if mentioned
        import re
        pain_match = re.search(r'\b([1-9]|10)\b', user_input)
        if pain_match:
            state.patient_info.urgency_level = int(pain_match.group(1))
            await state_manager.update_state(
                self.call_sid,
                urgency_level=state.patient_info.urgency_level
            )
        
        # Append duration info to complaint
        state.patient_info.chief_complaint += f" (Duration: {user_input})"
        
        # Transition to demographics
        await state_manager.transition_phase(
            self.call_sid,
            ConversationPhase.DEMOGRAPHICS
        )
        
        return "Thank you for that information. Now I need to verify your address. Could you please provide your complete street address including city, state, and zip code?"