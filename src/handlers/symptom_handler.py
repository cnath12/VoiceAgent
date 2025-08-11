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
        self._asked_for_scale = False
        self._captured_duration: Optional[str] = None
    
    async def process_input(self, user_input: str, state: ConversationState) -> str:
        """Process symptom-related input."""
        
        # If we haven't collected the complaint yet
        if not state.patient_info.chief_complaint:
            return await self._handle_initial_complaint(user_input, state)
        
        # If we need duration then pain scale in two steps
        if not self._asked_for_duration:
            return await self._handle_duration(user_input, state)
        if not self._asked_for_scale:
            return await self._handle_pain_scale(user_input, state)
        
        # Move to next phase
        await state_manager.transition_phase(
            self.call_sid,
            ConversationPhase.DEMOGRAPHICS
        )
        return "Thank you for that information. Now I need to collect your address for our records. Could you please provide your complete street address?"
    
    async def _handle_initial_complaint(self, user_input: str, state: ConversationState) -> str:
        """Process the initial complaint."""
        
        # Store the complaint (permissive: accept any 2+ words; otherwise accept as-is)
        cleaned = user_input.strip()
        if len(cleaned.split()) >= 2:
            state.patient_info.chief_complaint = cleaned
        else:
            state.patient_info.chief_complaint = cleaned
        
        # Update state
        await state_manager.update_state(
            self.call_sid,
            chief_complaint=state.patient_info.chief_complaint
        )
        
        # Keep gentle guidance but do not block
        urgent_keywords = ["emergency", "chest pain", "can't breathe", "bleeding", "unconscious"]
        if any(keyword in user_input.lower() for keyword in urgent_keywords):
            self._asked_for_duration = True
            return "If this is an emergency, please hang up and dial 911. Otherwise, how long have you been experiencing these symptoms?"
        
        # Ask only duration first
        self._asked_for_duration = False
        self._asked_for_scale = False
        return "How long have you been experiencing these symptoms?"
    
    async def _handle_duration(self, user_input: str, state: ConversationState) -> str:
        """Capture duration and then ask for pain scale."""
        self._captured_duration = user_input.strip()
        # Store duration appended to complaint for now
        if state.patient_info.chief_complaint:
            state.patient_info.chief_complaint += f" (Duration: {self._captured_duration})"
            await state_manager.update_state(self.call_sid, chief_complaint=state.patient_info.chief_complaint)
        self._asked_for_duration = True
        # Next, ask for the pain scale only
        return "On a scale of 1 to 10, how would you rate your discomfort?"

    async def _handle_pain_scale(self, user_input: str, state: ConversationState) -> str:
        """Capture pain scale and proceed."""
        import re
        pain_match = re.search(r'\b([1-9]|10)\b', user_input)
        if pain_match:
            state.patient_info.urgency_level = int(pain_match.group(1))
            await state_manager.update_state(self.call_sid, urgency_level=state.patient_info.urgency_level)
        self._asked_for_scale = True
        # Proceed to demographics
        await state_manager.transition_phase(self.call_sid, ConversationPhase.DEMOGRAPHICS)
        return "Thank you for that information. Now I need to collect your address for our records. Could you please provide your complete street address?"