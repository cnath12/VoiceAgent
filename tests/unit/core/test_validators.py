"""Unit tests for input validators."""
import pytest
from src.core.validators import InputValidator


@pytest.mark.unit
class TestInputValidator:
    """Test input validation functions."""

    def test_validate_phone_number_valid(self):
        """Test validating a valid phone number."""
        valid, cleaned = InputValidator.validate_phone_number("555-123-4567")
        assert valid is True
        assert cleaned == "5551234567"

    def test_validate_phone_number_with_country_code(self):
        """Test phone number with country code."""
        valid, cleaned = InputValidator.validate_phone_number("+1 (555) 123-4567")
        assert valid is True
        assert cleaned == "5551234567"

    def test_validate_phone_number_digits_only(self):
        """Test phone number with only digits."""
        valid, cleaned = InputValidator.validate_phone_number("5551234567")
        assert valid is True
        assert cleaned == "5551234567"

    def test_validate_phone_number_too_short(self):
        """Test invalid phone number (too short)."""
        valid, cleaned = InputValidator.validate_phone_number("555123")
        assert valid is False

    def test_validate_phone_number_invalid_characters(self):
        """Test phone number with invalid characters."""
        valid, cleaned = InputValidator.validate_phone_number("abc-defg-hijk")
        assert valid is False

    def test_validate_email_valid(self):
        """Test validating a valid email."""
        valid, cleaned = InputValidator.validate_email("test@example.com")
        assert valid is True
        assert cleaned == "test@example.com"

    def test_validate_email_invalid(self):
        """Test invalid email formats."""
        assert InputValidator.validate_email("invalid")[0] is False
        assert InputValidator.validate_email("@example.com")[0] is False
        assert InputValidator.validate_email("test@")[0] is False

    def test_validate_zip_code_valid_5_digit(self):
        """Test valid 5-digit ZIP code."""
        valid, cleaned = InputValidator.validate_zip_code("12345")
        assert valid is True
        assert cleaned == "12345"

    def test_validate_zip_code_valid_9_digit(self):
        """Test valid 9-digit ZIP code."""
        valid, cleaned = InputValidator.validate_zip_code("12345-6789")
        assert valid is True
        assert cleaned == "12345-6789"

    def test_validate_zip_code_invalid(self):
        """Test invalid ZIP codes."""
        assert InputValidator.validate_zip_code("1234")[0] is False
        assert InputValidator.validate_zip_code("abcde")[0] is False

    def test_validate_insurance_member_id_valid(self):
        """Test valid insurance member ID."""
        valid, cleaned = InputValidator.validate_insurance_member_id("ABC123456")
        assert valid is True
        assert cleaned == "ABC123456"

    def test_validate_insurance_member_id_with_spaces(self):
        """Test member ID with spaces."""
        valid, cleaned = InputValidator.validate_insurance_member_id("ABC 123 456")
        assert valid is True
        assert cleaned == "ABC123456"

    def test_validate_insurance_member_id_too_short(self):
        """Test member ID that's too short."""
        valid, cleaned = InputValidator.validate_insurance_member_id("ABC")
        assert valid is False

    def test_extract_number_from_speech(self):
        """Test extracting numbers from speech."""
        # Test digit extraction
        assert InputValidator.extract_number_from_speech("five") == 5
        assert InputValidator.extract_number_from_speech("ten") == 10

        # Test numeric extraction
        assert InputValidator.extract_number_from_speech("7") == 7
        assert InputValidator.extract_number_from_speech("the number is 3") == 3

    def test_extract_number_from_speech_no_number(self):
        """Test when no number is found in speech."""
        result = InputValidator.extract_number_from_speech("no numbers here")
        assert result is None
