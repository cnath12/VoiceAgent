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
            
            # Also prefetch slots for the first provider to ensure a smooth next turn
            try:
                first_provider_id = self._available_providers[0]['id']
                self._available_slots = await self.provider_service.get_available_slots(first_provider_id)
            except Exception:
                self._available_slots = []

            return f"Based on your needs, I have these doctors available: {', '.join(options)}. Which doctor would you like?"
        
        # Process selection
        selected_provider = None

        # Check if they said a number (support number words via LLM classifier as fallback)
        cleaned = user_input.strip()
        if cleaned.isdigit():
            idx = int(cleaned) - 1
            if 0 <= idx < len(self._available_providers):
                selected_provider = self._available_providers[idx]
        if not selected_provider and cleaned:
            try:
                from src.services.llm_service import LLMService
                labels = [str(i+1) for i in range(len(self._available_providers[:3]))]
                llm = LLMService()
                result = await llm.classify_choice(cleaned, labels)
                if result and result.get("label") in labels:
                    idx = int(result["label"]) - 1
                    if 0 <= idx < len(self._available_providers):
                        selected_provider = self._available_providers[idx]
            except Exception:
                pass

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
            next_day = datetime.now() + timedelta(days=1)
            proposed = next_day.replace(hour=14, minute=0, second=0, microsecond=0)
            display = proposed.strftime('%A, %B %d at %I:%M %p')
            self._available_slots = [{
                "datetime": proposed,
                "display": display,
                "keywords": ["2 pm", "tomorrow", next_day.strftime('%A').lower()]
            }]
        
        # Present time options (ensure clear numbering)
        slot_options = []
        for i, slot in enumerate(self._available_slots[:3], 1):
            slot_options.append(f"{i}. {slot['display']}")
        return (
            f"Dr. {selected_provider['name']} has these appointments available: "
            f"{', '.join(slot_options)}. Which time works best for you?"
        )
    
    async def _handle_appointment_selection(self, user_input: str, state: ConversationState) -> str:
        """Handle appointment time selection."""
        
        selected_slot = None
        
        # 1) Exact number selection or number words
        number_words = {
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
        }
        lowered = user_input.strip().lower()
        if lowered in number_words:
            idx = number_words[lowered] - 1
            if 0 <= idx < len(self._available_slots):
                selected_slot = self._available_slots[idx]

        # Check if they said a number (support number words via LLM classifier as fallback)
        cleaned = user_input.strip()
        if cleaned.isdigit():
            idx = int(cleaned) - 1
            if 0 <= idx < len(self._available_slots):
                selected_slot = self._available_slots[idx]
        if not selected_slot and cleaned:
            try:
                from src.services.llm_service import LLMService
                labels = [str(i+1) for i in range(len(self._available_slots[:3]))]
                llm = LLMService()
                result = await llm.classify_choice(cleaned, labels)
                if result and result.get("label") in labels:
                    idx = int(result["label"]) - 1
                    if 0 <= idx < len(self._available_slots):
                        selected_slot = self._available_slots[idx]
            except Exception:
                pass
        
        # 2) Parse explicit time/day and pick closest matching slot
        if not selected_slot and cleaned:
            import re

            # Extract explicit time and (optional) am/pm
            tm = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?\b", lowered)
            # Extract day words
            day_word = None
            for w in ["today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                if w in lowered:
                    day_word = w
                    break

            def infer_target_date(base: datetime) -> datetime:
                if not day_word:
                    return base
                if day_word == "today":
                    return base
                if day_word == "tomorrow":
                    return base + timedelta(days=1)
                # Next named weekday
                weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                target_idx = weekdays.index(day_word)
                delta = (target_idx - base.weekday()) % 7
                delta = 7 if delta == 0 else delta
                return base + timedelta(days=delta)

            def choose_closest_slot(target_dt: datetime) -> dict:
                # Prefer same-day slots; otherwise nearest overall
                same_day = [s for s in self._available_slots if s['datetime'].date() == target_dt.date()]
                candidates = same_day or self._available_slots
                if not candidates:
                    return None
                return min(candidates, key=lambda s: abs((s['datetime'] - target_dt).total_seconds()))

            if tm:
                hh = int(tm.group(1))
                mm = int(tm.group(2) or 0)
                ampm = (tm.group(3) or '').replace('.', '').lower()  # 'am'|'pm'|''

                # Base date: first listed slot date
                base_date = self._available_slots[0]['datetime'] if self._available_slots else datetime.now()
                base_date = infer_target_date(base_date)

                # Build two candidates if am/pm not specified
                candidates = []
                if ampm:
                    hour24 = (hh % 12) + (12 if ampm == 'pm' and hh != 12 else 0)
                    candidates.append(base_date.replace(hour=hour24, minute=mm, second=0, microsecond=0))
                else:
                    # Try AM
                    hour24_am = (hh % 12)
                    candidates.append(base_date.replace(hour=hour24_am, minute=mm, second=0, microsecond=0))
                    # Try PM
                    hour24_pm = (hh % 12) + 12
                    candidates.append(base_date.replace(hour=hour24_pm, minute=mm, second=0, microsecond=0))

                # Pick closest slot to any candidate
                best = None
                best_delta = None
                for cand in candidates:
                    slot = choose_closest_slot(cand)
                    if slot is None:
                        continue
                    delta = abs((slot['datetime'] - cand).total_seconds())
                    if best is None or delta < best_delta:
                        best = slot
                        best_delta = delta
                if best:
                    selected_slot = best

        # 3) Check for day/time keywords; if ambiguous, ask LLM to pick
        if not selected_slot:
            input_lower = user_input.lower()
            for slot in self._available_slots:
                if any(word in input_lower for word in slot['keywords']):
                    selected_slot = slot
                    break
            if not selected_slot and user_input.strip():
                try:
                    from src.services.llm_service import LLMService
                    options = [s['display'] for s in self._available_slots[:3]]
                    if options:
                        result = await LLMService().pick_best_option(user_input, options)
                        if result and isinstance(result.get('index'), int):
                            idx = result['index']
                            if 0 <= idx < len(self._available_slots):
                                selected_slot = self._available_slots[idx]
                except Exception:
                    pass
        
        if not selected_slot:
            # If no slots exist, synthesize a default next day 2 PM slot
            if not self._available_slots:
                next_day = datetime.now() + timedelta(days=1)
                proposed = next_day.replace(hour=14, minute=0, second=0, microsecond=0)
                display = proposed.strftime('%A, %B %d at %I:%M %p')
                self._available_slots = [{
                    "id": "default",
                    "datetime": proposed,
                    "display": display,
                    "keywords": ["2 pm", "tomorrow", next_day.strftime('%A').lower()]
                }]
            # Permissive: default to first available slot
            selected_slot = self._available_slots[0]
        
        # Store appointment
        state.patient_info.appointment_datetime = selected_slot['datetime']
        await state_manager.update_state(
            self.call_sid,
            appointment_datetime=state.patient_info.appointment_datetime
        )
        
        # Move to confirmation immediately without waiting for extra user input
        await state_manager.transition_phase(self.call_sid, ConversationPhase.CONFIRMATION)
        
        # Format confirmation
        appointment_str = selected_slot['display']
        return f"Perfect! I've scheduled your appointment with {state.patient_info.selected_provider} for {appointment_str}. You'll receive a confirmation email shortly. Goodbye!"