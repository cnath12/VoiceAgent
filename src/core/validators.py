"""Input validation utilities for the voice agent."""
import re
from typing import Optional, Tuple

from src.utils.logger import get_logger

logger = get_logger(__name__)


class InputValidator:
    """Validates various types of user input."""
    
    @staticmethod
    def validate_phone_number(phone_input: str) -> Tuple[bool, Optional[str]]:
        """Validate and format phone number."""
        
        # Remove all non-digits
        digits = re.sub(r'[^0-9]', '', phone_input)
        
        # Check if it's 10 digits (US phone)
        if len(digits) == 10:
            formatted = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
            return True, formatted
        
        # Check if it's 11 digits starting with 1
        elif len(digits) == 11 and digits[0] == '1':
            digits = digits[1:]
            formatted = f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
            return True, formatted
        
        return False, None
    
    @staticmethod
    def validate_email(email_input: str) -> Tuple[bool, Optional[str]]:
        """Validate email address."""
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        cleaned = email_input.strip().lower()
        
        if re.match(email_pattern, cleaned):
            return True, cleaned
        
        return False, None
    
    @staticmethod
    def validate_zip_code(zip_input: str) -> Tuple[bool, Optional[str]]:
        """Validate US zip code."""
        
        # Remove all non-digits
        digits = re.sub(r'[^0-9]', '', zip_input)
        
        # Check for 5-digit zip
        if len(digits) == 5:
            return True, digits
        
        # Check for 9-digit zip (ZIP+4)
        elif len(digits) == 9:
            return True, f"{digits[:5]}-{digits[5:]}"
        
        return False, None
    
    @staticmethod
    def validate_insurance_member_id(member_id_input: str) -> Tuple[bool, Optional[str]]:
        """Validate and clean insurance member ID."""
        
        # Remove common words
        cleaned = member_id_input.upper()
        remove_words = ['MEMBER', 'ID', 'NUMBER', 'IS', "IT'S", 'IT IS', 'MY']
        
        for word in remove_words:
            cleaned = cleaned.replace(word, '')
        
        # Remove extra spaces and special characters (keep alphanumeric and hyphens)
        cleaned = re.sub(r'[^A-Z0-9\-]', '', cleaned).strip()
        
        # Check if we have something meaningful left
        if len(cleaned) >= 5:  # Most member IDs are at least 5 characters
            return True, cleaned
        
        return False, None
    
    @staticmethod
    def extract_number_from_speech(speech_input: str) -> Optional[int]:
        """Extract number from speech (e.g., 'number three' -> 3)."""
        
        # Direct digit
        if speech_input.strip().isdigit():
            return int(speech_input.strip())
        
        # Word to number mapping
        word_to_num = {
            'one': 1, 'first': 1,
            'two': 2, 'second': 2,
            'three': 3, 'third': 3,
            'four': 4, 'fourth': 4,
            'five': 5, 'fifth': 5,
            'six': 6, 'sixth': 6,
            'seven': 7, 'seventh': 7,
            'eight': 8, 'eighth': 8,
            'nine': 9, 'ninth': 9,
            'ten': 10, 'tenth': 10
        }
        
        speech_lower = speech_input.lower().strip()
        
        # Check for word numbers
        for word, num in word_to_num.items():
            if word in speech_lower:
                return num
        
        # Try to find any digit in the string
        digits = re.findall(r'\d+', speech_input)
        if digits:
            return int(digits[0])
        
        return None
    
    @staticmethod
    def validate_date_time(date_input: str) -> Tuple[bool, Optional[str]]:
        """Validate and parse date/time expressions."""
        
        # Common patterns
        patterns = {
            'today': 0,
            'tomorrow': 1,
            'monday': 'Monday',
            'tuesday': 'Tuesday',
            'wednesday': 'Wednesday',
            'thursday': 'Thursday',
            'friday': 'Friday',
            'morning': 'AM',
            'afternoon': 'PM',
            'evening': 'PM'
        }
        
        date_lower = date_input.lower()
        
        # Look for pattern matches
        found_patterns = []
        for pattern, value in patterns.items():
            if pattern in date_lower:
                found_patterns.append((pattern, value))
        
        if found_patterns:
            return True, found_patterns
        
        return False, None