"""PHI (Protected Health Information) redaction utilities for HIPAA compliance.

This module provides utilities to redact sensitive health information from logs,
transcripts, and other outputs to ensure HIPAA compliance.

PHI includes:
- Names (first, last, full names)
- Phone numbers
- Email addresses
- Social Security Numbers (SSN)
- Medical record numbers
- Insurance member IDs
- Street addresses
- Dates (except year)
- Any unique identifying numbers

References:
- HIPAA Privacy Rule: 45 CFR § 164.514(b)
- Safe Harbor Method: 18 identifiers that must be removed
"""
import re
from typing import Dict, List, Optional, Pattern
from datetime import datetime


class PHIRedactor:
    """Redacts Protected Health Information (PHI) from text."""

    def __init__(self, placeholder: str = "[REDACTED]"):
        """Initialize PHI redactor.

        Args:
            placeholder: String to replace PHI with (default: "[REDACTED]")
        """
        self.placeholder = placeholder
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for PHI detection."""

        # Social Security Numbers: ###-##-#### or #########
        self.ssn_pattern = re.compile(
            r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b'
        )

        # Phone numbers: Various formats
        self.phone_pattern = re.compile(
            r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
        )

        # Email addresses
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )

        # Insurance member IDs: Alphanumeric sequences (5-20 chars)
        # Conservative pattern to avoid false positives
        self.member_id_pattern = re.compile(
            r'\b[A-Z]{2,4}\d{6,12}\b'  # e.g., ABC123456789
        )

        # ZIP codes (specific to 5 or 9 digits)
        self.zip_pattern = re.compile(
            r'\b\d{5}(?:-\d{4})?\b'
        )

        # Credit card numbers (13-19 digits with optional spaces/dashes)
        self.credit_card_pattern = re.compile(
            r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4,7}\b'
        )

        # Dates: MM/DD/YYYY, MM-DD-YYYY, etc.
        # Keep year-only references
        self.date_pattern = re.compile(
            r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b'
        )

        # Street addresses: Pattern for common US address formats
        # E.g., "123 Main St", "456 Oak Avenue"
        self.street_address_pattern = re.compile(
            r'\b\d+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Way|Court|Ct|Circle|Cir|Place|Pl)\b',
            re.IGNORECASE
        )

        # Medical record numbers: Often start with MRN, MR#, or similar
        self.mrn_pattern = re.compile(
            r'\b(?:MRN|MR#|Medical\s+Record)[:\s#]*[A-Z0-9]{6,12}\b',
            re.IGNORECASE
        )

    def redact(self, text: str, redact_level: str = "full") -> str:
        """Redact PHI from text.

        Args:
            text: Text to redact
            redact_level: Level of redaction
                - "full": Redact all PHI (production)
                - "partial": Keep some context (debugging)
                - "minimal": Only redact highly sensitive (SSN, credit cards)

        Returns:
            Redacted text
        """
        if not text:
            return text

        redacted = text

        if redact_level in ["minimal", "partial", "full"]:
            # Always redact highly sensitive information
            redacted = self.ssn_pattern.sub(self.placeholder, redacted)
            redacted = self.credit_card_pattern.sub(self.placeholder, redacted)

        if redact_level in ["partial", "full"]:
            # Redact contact information
            redacted = self.phone_pattern.sub(self._redact_phone, redacted)
            redacted = self.email_pattern.sub(self._redact_email, redacted)
            redacted = self.member_id_pattern.sub(self.placeholder, redacted)
            redacted = self.mrn_pattern.sub(self.placeholder, redacted)

        if redact_level == "full":
            # Redact all identifiers
            redacted = self.date_pattern.sub(self._redact_date, redacted)
            redacted = self.zip_pattern.sub(self._redact_zip, redacted)
            redacted = self.street_address_pattern.sub(self.placeholder, redacted)

        return redacted

    def _redact_phone(self, match) -> str:
        """Redact phone number, keeping format.

        Args:
            match: Regex match object

        Returns:
            Redacted phone (e.g., "XXX-XXX-1234" shows last 4)
        """
        phone = match.group(0)
        # Keep last 4 digits for partial redaction
        if len(phone) >= 4:
            return "XXX-XXX-" + phone[-4:]
        return self.placeholder

    def _redact_email(self, match) -> str:
        """Redact email, keeping domain for context.

        Args:
            match: Regex match object

        Returns:
            Redacted email (e.g., "***@example.com")
        """
        email = match.group(0)
        if '@' in email:
            parts = email.split('@')
            return f"***@{parts[1]}"
        return self.placeholder

    def _redact_date(self, match) -> str:
        """Redact date, keeping year for medical context.

        Args:
            match: Regex match object

        Returns:
            Redacted date (e.g., "MM/DD/2024")
        """
        date_str = match.group(0)
        # Keep year, redact month/day
        if '/' in date_str:
            parts = date_str.split('/')
            if len(parts) == 3:
                return f"MM/DD/{parts[2]}"
        elif '-' in date_str:
            parts = date_str.split('-')
            if len(parts) == 3:
                return f"MM-DD-{parts[2]}"
        return self.placeholder

    def _redact_zip(self, match) -> str:
        """Redact ZIP code, keeping first 3 digits for geographic context.

        Args:
            match: Regex match object

        Returns:
            Redacted ZIP (e.g., "123XX")
        """
        zip_code = match.group(0)
        if len(zip_code) >= 3:
            return zip_code[:3] + "XX"
        return self.placeholder

    def redact_dict(
        self,
        data: Dict,
        sensitive_keys: Optional[List[str]] = None,
        redact_level: str = "full"
    ) -> Dict:
        """Redact PHI from dictionary values.

        Args:
            data: Dictionary to redact
            sensitive_keys: List of keys that contain PHI (if None, redact all string values)
            redact_level: Redaction level

        Returns:
            Dictionary with redacted values
        """
        if sensitive_keys is None:
            # Default sensitive keys
            sensitive_keys = [
                "phone", "phone_number", "email", "address", "street",
                "ssn", "social_security", "member_id", "medical_record",
                "patient_name", "first_name", "last_name", "full_name",
                "date_of_birth", "dob", "zip", "zip_code"
            ]

        redacted = {}
        for key, value in data.items():
            if isinstance(value, str):
                # Check if key is sensitive
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    redacted[key] = self.placeholder
                else:
                    # Apply pattern-based redaction
                    redacted[key] = self.redact(value, redact_level)
            elif isinstance(value, dict):
                # Recursively redact nested dicts
                redacted[key] = self.redact_dict(value, sensitive_keys, redact_level)
            elif isinstance(value, list):
                # Redact list items
                redacted[key] = [
                    self.redact(item, redact_level) if isinstance(item, str)
                    else item
                    for item in value
                ]
            else:
                redacted[key] = value

        return redacted

    def is_phi_present(self, text: str) -> bool:
        """Check if text contains potential PHI.

        Args:
            text: Text to check

        Returns:
            True if PHI patterns detected, False otherwise
        """
        if not text:
            return False

        patterns = [
            self.ssn_pattern,
            self.phone_pattern,
            self.email_pattern,
            self.member_id_pattern,
            self.mrn_pattern,
            self.credit_card_pattern
        ]

        for pattern in patterns:
            if pattern.search(text):
                return True

        return False


# Global singleton instance
_redactor = None


def get_phi_redactor(placeholder: str = "[REDACTED]") -> PHIRedactor:
    """Get global PHI redactor instance.

    Args:
        placeholder: Placeholder string for redacted content

    Returns:
        PHIRedactor instance
    """
    global _redactor
    if _redactor is None:
        _redactor = PHIRedactor(placeholder)
    return _redactor


def redact_phi(text: str, level: str = "full") -> str:
    """Convenience function to redact PHI from text.

    Args:
        text: Text to redact
        level: Redaction level ("full", "partial", "minimal")

    Returns:
        Redacted text
    """
    redactor = get_phi_redactor()
    return redactor.redact(text, level)


def redact_phi_dict(data: Dict, level: str = "full") -> Dict:
    """Convenience function to redact PHI from dictionary.

    Args:
        data: Dictionary to redact
        level: Redaction level

    Returns:
        Redacted dictionary
    """
    redactor = get_phi_redactor()
    return redactor.redact_dict(data, redact_level=level)
