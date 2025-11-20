"""Abstract base class for conversation state managers."""
from abc import ABC, abstractmethod
from typing import Optional
from src.core.models import ConversationState, ConversationPhase


class StateManagerBase(ABC):
    """Abstract base class for managing conversation state.

    Implementations can use different backends (in-memory, Redis, etc.)
    while maintaining a consistent interface.
    """

    @abstractmethod
    async def create_state(self, call_sid: str) -> ConversationState:
        """Create new conversation state.

        Args:
            call_sid: Twilio call SID

        Returns:
            Newly created conversation state
        """
        pass

    @abstractmethod
    async def get_state(self, call_sid: str) -> Optional[ConversationState]:
        """Get conversation state by call SID.

        Args:
            call_sid: Twilio call SID

        Returns:
            Conversation state if found, None otherwise
        """
        pass

    @abstractmethod
    async def update_state(
        self,
        call_sid: str,
        **kwargs
    ) -> Optional[ConversationState]:
        """Update conversation state.

        Args:
            call_sid: Twilio call SID
            **kwargs: Fields to update

        Returns:
            Updated conversation state if found, None otherwise
        """
        pass

    @abstractmethod
    async def transition_phase(
        self,
        call_sid: str,
        new_phase: ConversationPhase
    ) -> Optional[ConversationState]:
        """Transition to new conversation phase.

        Args:
            call_sid: Twilio call SID
            new_phase: New conversation phase

        Returns:
            Updated conversation state if found, None otherwise
        """
        pass

    @abstractmethod
    async def cleanup_state(self, call_sid: str) -> None:
        """Remove conversation state after completion.

        Args:
            call_sid: Twilio call SID
        """
        pass

    def get_next_phase(self, current_phase: ConversationPhase) -> ConversationPhase:
        """Determine next phase in conversation flow.

        This logic is the same for all implementations.

        Args:
            current_phase: Current conversation phase

        Returns:
            Next conversation phase
        """
        transitions = {
            ConversationPhase.GREETING: ConversationPhase.INSURANCE,
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
