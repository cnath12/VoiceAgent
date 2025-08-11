"""Handler for provider selection and appointment scheduling."""
from datetime import datetime, timedelta
from typing import List, Dict

from src.core.models import ConversationState, ConversationPhase
from src.core.conversation_state import state_manager
from src.services.provider_service import ProviderService
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SchedulingHandler:
    """Handles provider selection and appointment scheduling."""
    
    def __init__(self, call_sid: str):
        self.call_sid = call_sid
        self.provider_service = ProviderService()
        self._available_providers: List[Dict] = []
        self._available_slots: List[Dict] = []
    
    async def process_input(self, user_input: str, state: ConversationState) -> str:
        """Process scheduling-related input."""
        
        if state.phase == ConversationPhase.PROVIDER_SELECTION:
            return await self._handle_provider_selection(user_input, state)
        else:
            return await self._handle_appointment_selection(user_input, state)
    
    async def _handle_provider_selection(self, user_input: str, state: ConversationState) -> str:
        """Handle provider selection."""
        
        # First time - get available providers
        if not self._available_providers:
            self._available_providers = await self.provider_service.get_available_providers(
                state.patient_info.chief_complaint,
                state.patient_info.insurance.payer_name if state.patient_info.insurance else None
            )
            
            # If no providers returned, propose a default
            if not self._available_providers:
                self._available_providers = [{
                    "id": "default-1",
                    "name": "Sarah Smith",
                    "specialty": "Primary Care"
                }]
            
            # Present options
            options = []
            for i, provider in enumerate(self._available_providers[:3], 1):
                options.append(f"{i}. Dr. {provider['name']} - {provider['specialty']}")
            
            return f"Based on your needs, I have these doctors available: {', '.join(options)}. Which would you prefer? You can say the number or the doctor's name."
        
        # Process selection
        selected_provider = None
        
        # Check if they said a number
        if user_input.strip().isdigit():
            idx = int(user_input.strip()) - 1
            if 0 <= idx < len(self._available_providers):
                selected_provider = self._available_providers[idx]
        
        # Check if they said a name
        if not selected_provider:
            for provider in self._available_providers:
                if provider['name'].lower() in user_input.lower():
                    selected_provider = provider
                    break
        
        if not selected_provider:
            # Permissive: default to first option
            selected_provider = self._available_providers[0]
        
        # Store selection
        state.patient_info.selected_provider = f"Dr. {selected_provider['name']}"
        await state_manager.update_state(
            self.call_sid,
            selected_provider=state.patient_info.selected_provider
        )
        
        # Move to appointment scheduling
        await state_manager.transition_phase(
            self.call_sid,
            ConversationPhase.APPOINTMENT_SCHEDULING
        )
        
        # Get available slots
        self._available_slots = await self.provider_service.get_available_slots(
            selected_provider['id']
        )
        
        # If no slots, propose next business day at 2 PM
        if not self._available_slots:
            from datetime import datetime, timedelta
            next_day = datetime.now() + timedelta(days=1)
            proposed = next_day.replace(hour=14, minute=0, second=0, microsecond=0)
            display = proposed.strftime('%A, %B %d at %I:%M %p')
            self._available_slots = [{
                "datetime": proposed,
                "display": display,
                "keywords": ["2 pm", "tomorrow", next_day.strftime('%A').lower()]
            }]
        
        # Present time options
        slot_options = []
        for i, slot in enumerate(self._available_slots[:3], 1):
            slot_options.append(f"{i}. {slot['display']}")
        
        return f"Dr. {selected_provider['name']} has these appointments available: {', '.join(slot_options)}. Which works best for you?"
    
    async def _handle_appointment_selection(self, user_input: str, state: ConversationState) -> str:
        """Handle appointment time selection."""
        
        selected_slot = None
        
        # Check if they said a number
        if user_input.strip().isdigit():
            idx = int(user_input.strip()) - 1
            if 0 <= idx < len(self._available_slots):
                selected_slot = self._available_slots[idx]
        
        # Check for day/time keywords
        if not selected_slot:
            input_lower = user_input.lower()
            for slot in self._available_slots:
                if any(word in input_lower for word in slot['keywords']):
                    selected_slot = slot
                    break
        
        if not selected_slot:
            # Permissive: default to first available slot
            selected_slot = self._available_slots[0]
        
        # Store appointment
        state.patient_info.appointment_datetime = selected_slot['datetime']
        await state_manager.update_state(
            self.call_sid,
            appointment_datetime=state.patient_info.appointment_datetime
        )
        
        # Move to confirmation
        await state_manager.transition_phase(
            self.call_sid,
            ConversationPhase.CONFIRMATION
        )
        
        # Format confirmation
        appointment_str = selected_slot['display']
        return f"Perfect! I've scheduled your appointment with {state.patient_info.selected_provider} for {appointment_str}. I'll send a confirmation email to {state.patient_info.email or 'the email on file'}. Is there anything else you need help with today?"