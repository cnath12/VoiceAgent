"""Handler for collecting and validating demographics."""
import re
from typing import Optional, Dict

from src.core.models import ConversationState, Address, ConversationPhase
from src.core.conversation_state import state_manager
from src.services.address_service import AddressService
from src.core.validators import InputValidator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DemographicsHandler:
    """Handles demographic information collection, primarily address."""
    
    def __init__(self, call_sid: str):
        self.call_sid = call_sid
        self.address_service = AddressService()
        self._collection_step = "full_address"
        self._address_parts: Dict[str, str] = {}
    
    async def process_input(self, user_input: str, state: ConversationState) -> str:
        """Process demographics-related input."""
        
        if self._collection_step == "full_address":
            return await self._handle_full_address(user_input, state)
        elif self._collection_step == "clarification":
            return await self._handle_address_clarification(user_input, state)
        else:
            return await self._handle_contact_info(user_input, state)
    
    async def _handle_full_address(self, user_input: str, state: ConversationState) -> str:
        """Parse and validate full address."""
        
        # Permissive acceptance: allow typical address patterns
        input_lower = user_input.lower().strip()
        has_numbers = any(char.isdigit() for char in user_input)
        street_keywords = [
            "street", "st", "avenue", "ave", "road", "rd", "drive", "dr", "lane", "ln",
            "boulevard", "blvd", "way", "court", "ct", "place", "pl", "parkway", "pkwy"
        ]
        has_street_keyword = any(f" {kw} " in f" {input_lower} " for kw in street_keywords)
        
        # Try to parse address components
        address_parts = self._parse_address(user_input)
        
        # Attempt validation, but don't block on failure
        validated_address = None
        try:
            validated_address = await self.address_service.validate_address(
                street=address_parts.get("street", ""),
                city=address_parts.get("city", ""),
                state=address_parts.get("state", ""),
                zip_code=address_parts.get("zip", "")
            )
        except Exception:
            validated_address = None
        
        if validated_address and validated_address.validated:
            # Store validated address
            state.patient_info.address = validated_address
            await state_manager.update_state(
                self.call_sid,
                address=validated_address
            )
            # Move to contact info
            self._collection_step = "phone"
            await state_manager.transition_phase(
                self.call_sid,
                ConversationPhase.CONTACT_INFO
            )
            return "Great! I've verified your address. Now, what's the best phone number to reach you at?"
        
        # If it looks like an address (numbers or street keyword or sufficiently descriptive), accept and proceed
        looks_like_address = (has_numbers and has_street_keyword) or len(user_input.split()) >= 4
        if looks_like_address:
            # Fill missing parts permissively
            street = address_parts.get("street") or user_input.strip()
            # If the input is clearly not an address sentence, do not accept
            if street.lower() in {"yes", "no", "ok", "okay", "sure"}:
                return "I need your complete street address, starting with the house number and street name. For example: '150 Van Ness Ave, San Francisco, CA 94102'."
            city = address_parts.get("city") or ""
            state_code = address_parts.get("state") or ""
            zip_code = address_parts.get("zip") or ""
            
            addr = Address(
                street=street,
                city=city,
                state=state_code,
                zip_code=zip_code,
                validated=False,
                validation_message="Captured without verification"
            )
            state.patient_info.address = addr
            await state_manager.update_state(self.call_sid, address=addr)
            
            # Move to contact info
            self._collection_step = "phone"
            await state_manager.transition_phase(self.call_sid, ConversationPhase.CONTACT_INFO)
            return "Thanks! What's the best phone number to reach you at?"
        
        # Otherwise, ask again with guidance
        return "I need your complete street address for our records. Please provide your house number and street name, like '150 Van Ness Ave, San Francisco, CA 94102'."
    
    async def _handle_address_clarification(self, user_input: str, state: ConversationState) -> str:
        """Handle address clarification."""
        # Update missing parts
        if not self._address_parts.get("street"):
            self._address_parts["street"] = user_input.strip()
            return "Thank you. Now, what city is that in?"
        elif not self._address_parts.get("city"):
            self._address_parts["city"] = user_input.strip()
            return "And the state?"
        elif not self._address_parts.get("state"):
            self._address_parts["state"] = self._normalize_state(user_input.strip())
            return "And finally, the zip code?"
        elif not self._address_parts.get("zip"):
            self._address_parts["zip"] = re.sub(r'[^0-9]', '', user_input)
            
        # Try validation again
        return await self._handle_full_address(
            f"{self._address_parts['street']} {self._address_parts['city']} {self._address_parts['state']} {self._address_parts['zip']}", 
            state
        )
    
    async def _handle_contact_info(self, user_input: str, state: ConversationState) -> str:
        """Handle phone and email collection."""
        
        if not state.patient_info.phone_number:
            # Permissive phone acceptance: require at least 7 digits to accept
            import re
            digits = re.sub(r"\D", "", user_input)
            if len(digits) >= 10:
                formatted = f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
            elif len(digits) >= 7:
                formatted = digits
            else:
                return "I didn't catch a phone number. Please say the digits clearly, for example '765 771 0488'. What's the best phone number to reach you at?"

            state.patient_info.phone_number = formatted
            await state_manager.update_state(
                self.call_sid,
                phone_number=state.patient_info.phone_number
            )

            # In non-production, do not ask for email; use test email and proceed immediately
            from src.config.settings import get_settings
            settings = get_settings()
            if settings.app_env.lower() in {"development", "test", "testing", "staging"}:
                state.patient_info.email = settings.test_notification_email
                await state_manager.update_state(self.call_sid, email=state.patient_info.email)
                await state_manager.transition_phase(self.call_sid, ConversationPhase.PROVIDER_SELECTION)
                return "Thank you! Now let me find available doctors for you based on your needs."

            # In production, ask for email next
            return "Perfect! And may I have your email address for appointment confirmations?"
        
        # Handle email (production only; non-prod already advanced above)
        from src.config.settings import get_settings
        settings = get_settings()
        if settings.app_env.lower() not in {"development", "test", "testing", "staging"}:
            valid_email, cleaned = InputValidator.validate_email(user_input)
            if valid_email and cleaned:
                state.patient_info.email = cleaned
                await state_manager.update_state(self.call_sid, email=state.patient_info.email)
        
        # Move to provider selection
        await state_manager.transition_phase(
            self.call_sid,
            ConversationPhase.PROVIDER_SELECTION
        )
        return "Thank you! Now let me find available doctors for you based on your needs."
    
    def _parse_address(self, address_text: str) -> Dict[str, str]:
        """Parse address components from text."""
        parts = {"street": "", "city": "", "state": "", "zip": ""}
        
        # Extract zip code
        zip_match = re.search(r'\b(\d{5})(-\d{4})?\b', address_text)
        if zip_match:
            parts["zip"] = zip_match.group(1)
            address_text = address_text.replace(zip_match.group(0), "").strip()
        
        # Extract state
        states = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
                 "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
                 "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
                 "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
                 "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]
        
        for state in states:
            if f" {state} " in address_text.upper() or address_text.upper().endswith(f" {state}"):
                parts["state"] = state
                address_text = re.sub(rf'\b{state}\b', '', address_text, flags=re.IGNORECASE).strip()
                break
        
        # Try to separate street and city
        # This is simplified - in production you'd use a more sophisticated parser
        words = address_text.split()
        if len(words) >= 3:
            # Assume last 1-2 words before state were city
            city_words = 1 if len(words) < 5 else 2
            parts["city"] = " ".join(words[-city_words:])
            parts["street"] = " ".join(words[:-city_words])
        else:
            parts["street"] = address_text
        
        return parts
    
    def _normalize_state(self, state_input: str) -> str:
        """Normalize state input to 2-letter code."""
        state_map = {
            "california": "CA", "texas": "TX", "new york": "NY",
            "florida": "FL", "illinois": "IL", "pennsylvania": "PA",
            # Add more as needed
        }
        
        state_lower = state_input.lower().strip()
        if len(state_input) == 2:
            return state_input.upper()
        return state_map.get(state_lower, state_input.upper()[:2])