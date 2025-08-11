"""State machine for managing conversation flow."""
from typing import Dict, Optional
import asyncio
from datetime import datetime

from src.core.models import ConversationState, ConversationPhase, PatientInfo
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ConversationStateManager:
    """Manages conversation state across calls."""
    
    def __init__(self):
        self._states: Dict[str, ConversationState] = {}
        self._lock = asyncio.Lock()
    
    async def create_state(self, call_sid: str) -> ConversationState:
        """Create new conversation state."""
        async with self._lock:
            state = ConversationState(call_sid=call_sid)
            self._states[call_sid] = state
            logger.info(f"Created conversation state for {call_sid}")
            return state
    
    async def get_state(self, call_sid: str) -> Optional[ConversationState]:
        """Get conversation state by call SID."""
        async with self._lock:
            return self._states.get(call_sid)
    
    async def update_state(self, call_sid: str, **kwargs) -> Optional[ConversationState]:
        """Update conversation state."""
        async with self._lock:
            state = self._states.get(call_sid)
            if state:
                for key, value in kwargs.items():
                    if hasattr(state, key):
                        setattr(state, key, value)
                    elif hasattr(state.patient_info, key):
                        setattr(state.patient_info, key, value)
                logger.info(f"Updated state for {call_sid}: {kwargs}")
            return state
    
    async def transition_phase(self, call_sid: str, new_phase: ConversationPhase) -> Optional[ConversationState]:
        """Transition to new conversation phase."""
        async with self._lock:
            state = self._states.get(call_sid)
            if state:
                old_phase = state.phase
                state.phase = new_phase
                logger.info(f"Transitioned {call_sid} from {old_phase} to {new_phase}")
            return state
    
    async def cleanup_state(self, call_sid: str):
        """Remove conversation state after completion."""
        async with self._lock:
            if call_sid in self._states:
                del self._states[call_sid]
                logger.info(f"Cleaned up state for {call_sid}")
    
    def get_next_phase(self, current_phase: ConversationPhase) -> ConversationPhase:
        """Determine next phase in conversation flow."""
        transitions = {
            ConversationPhase.GREETING: ConversationPhase.EMERGENCY_CHECK,
            ConversationPhase.EMERGENCY_CHECK: ConversationPhase.INSURANCE,
            ConversationPhase.INSURANCE: ConversationPhase.CHIEF_COMPLAINT,
            ConversationPhase.CHIEF_COMPLAINT: ConversationPhase.DEMOGRAPHICS,
            ConversationPhase.DEMOGRAPHICS: ConversationPhase.CONTACT_INFO,
            ConversationPhase.CONTACT_INFO: ConversationPhase.PROVIDER_SELECTION,
            ConversationPhase.PROVIDER_SELECTION: ConversationPhase.APPOINTMENT_SCHEDULING,
            ConversationPhase.APPOINTMENT_SCHEDULING: ConversationPhase.CONFIRMATION,
            ConversationPhase.CONFIRMATION: ConversationPhase.COMPLETED,
        }
        return transitions.get(current_phase, ConversationPhase.COMPLETED)


# Global state manager instance
state_manager = ConversationStateManager()