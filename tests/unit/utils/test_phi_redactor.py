"""Unit tests for PHI redaction."""
import pytest
from src.utils.phi_redactor import PHIRedactor, redact_phi, redact_phi_dict


@pytest.mark.unit
class TestPHIRedactor:
    """Test PHI redaction for HIPAA compliance."""

    @pytest.fixture
    def redactor(self):
        """Create a PHI redactor instance."""
        return PHIRedactor()

    def test_redact_ssn(self, redactor):
        """Test SSN redaction."""
        text = "My SSN is 123-45-6789"
        redacted = redactor.redact(text)

        assert "123-45-6789" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_ssn_no_dashes(self, redactor):
        """Test SSN without dashes."""
        text = "SSN: 123456789"
        redacted = redactor.redact(text)

        assert "123456789" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_phone(self, redactor):
        """Test phone number redaction."""
        text = "Call me at 555-123-4567"
        redacted = redactor.redact(text)

        # Should show last 4 digits
        assert "XXX-XXX-4567" in redacted
        assert "555-123-4567" not in redacted

    def test_redact_phone_formats(self, redactor):
        """Test various phone number formats."""
        formats = [
            "(555) 123-4567",
            "555.123.4567",
            "5551234567",
            "+1-555-123-4567"
        ]

        for phone in formats:
            text = f"Phone: {phone}"
            redacted = redactor.redact(text)
            # Original phone should not appear
            assert phone not in redacted

    def test_redact_email(self, redactor):
        """Test email redaction."""
        text = "Email: patient@example.com"
        redacted = redactor.redact(text)

        # Should keep domain
        assert "***@example.com" in redacted
        assert "patient@example.com" not in redacted

    def test_redact_member_id(self, redactor):
        """Test insurance member ID redaction."""
        text = "Member ID: ABC123456789"
        redacted = redactor.redact(text)

        assert "ABC123456789" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_zip_code(self, redactor):
        """Test ZIP code redaction."""
        text = "ZIP: 12345"
        redacted = redactor.redact(text, redact_level="full")

        # Should keep first 3 digits
        assert "123XX" in redacted
        assert "12345" not in redacted

    def test_redact_zip_plus_four(self, redactor):
        """Test ZIP+4 redaction."""
        text = "ZIP: 12345-6789"
        redacted = redactor.redact(text, redact_level="full")

        assert "123XX" in redacted
        assert "12345-6789" not in redacted

    def test_redact_street_address(self, redactor):
        """Test street address redaction."""
        text = "I live at 123 Main Street"
        redacted = redactor.redact(text, redact_level="full")

        assert "123 Main Street" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_date(self, redactor):
        """Test date redaction."""
        text = "DOB: 01/15/1990"
        redacted = redactor.redact(text, redact_level="full")

        # Should keep year, redact month/day
        assert "MM/DD/1990" in redacted
        assert "01/15/1990" not in redacted

    def test_redact_credit_card(self, redactor):
        """Test credit card redaction."""
        text = "Card: 4532-1234-5678-9010"
        redacted = redactor.redact(text)

        assert "4532-1234-5678-9010" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_mrn(self, redactor):
        """Test medical record number redaction."""
        text = "MRN: ABC123456"
        redacted = redactor.redact(text)

        assert "ABC123456" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_level_minimal(self, redactor):
        """Test minimal redaction level."""
        text = "SSN: 123-45-6789, Phone: 555-123-4567, Email: test@example.com"
        redacted = redactor.redact(text, redact_level="minimal")

        # Should redact SSN but not phone/email
        assert "123-45-6789" not in redacted
        assert "555-123-4567" in redacted or "XXX-XXX-4567" not in redacted

    def test_redact_level_partial(self, redactor):
        """Test partial redaction level."""
        text = "SSN: 123-45-6789, Phone: 555-123-4567"
        redacted = redactor.redact(text, redact_level="partial")

        # Should redact SSN and partially redact phone
        assert "123-45-6789" not in redacted
        assert "XXX-XXX-4567" in redacted

    def test_redact_level_full(self, redactor):
        """Test full redaction level."""
        text = "SSN: 123-45-6789, Address: 123 Main St, ZIP: 12345"
        redacted = redactor.redact(text, redact_level="full")

        # Should redact everything
        assert "123-45-6789" not in redacted
        assert "123 Main St" not in redacted
        assert "12345" not in redacted

    def test_redact_empty_string(self, redactor):
        """Test redacting empty string."""
        assert redactor.redact("") == ""
        assert redactor.redact(None) == None

    def test_redact_no_phi(self, redactor):
        """Test text with no PHI."""
        text = "This is a normal sentence with no sensitive information."
        redacted = redactor.redact(text)

        # Should be unchanged
        assert redacted == text

    def test_redact_dict(self, redactor):
        """Test dictionary redaction."""
        data = {
            "name": "John Doe",
            "phone": "555-123-4567",
            "email": "john@example.com",
            "complaint": "headache"
        }

        redacted = redactor.redact_dict(data)

        # Sensitive keys should be redacted
        assert redacted["phone"] == "[REDACTED]"
        assert redacted["email"] == "[REDACTED]"
        # Non-sensitive should remain
        assert redacted["complaint"] == "headache"

    def test_redact_nested_dict(self, redactor):
        """Test nested dictionary redaction."""
        data = {
            "patient": {
                "name": "John Doe",
                "contact": {
                    "phone": "555-123-4567",
                    "email": "john@example.com"
                }
            }
        }

        redacted = redactor.redact_dict(data)

        assert redacted["patient"]["contact"]["phone"] == "[REDACTED]"
        assert redacted["patient"]["contact"]["email"] == "[REDACTED]"

    def test_redact_list_in_dict(self, redactor):
        """Test dictionary with list values."""
        data = {
            "phones": ["555-123-4567", "555-987-6543"]
        }

        redacted = redactor.redact_dict(data)

        # Phones in list should be redacted
        assert "555-123-4567" not in str(redacted)

    def test_is_phi_present_true(self, redactor):
        """Test PHI detection when present."""
        text = "Call me at 555-123-4567"

        assert redactor.is_phi_present(text) is True

    def test_is_phi_present_false(self, redactor):
        """Test PHI detection when absent."""
        text = "This is a normal sentence."

        assert redactor.is_phi_present(text) is False

    def test_is_phi_present_empty(self, redactor):
        """Test PHI detection on empty string."""
        assert redactor.is_phi_present("") is False
        assert redactor.is_phi_present(None) is False

    def test_custom_placeholder(self):
        """Test using custom placeholder."""
        redactor = PHIRedactor(placeholder="***")
        text = "SSN: 123-45-6789"
        redacted = redactor.redact(text)

        assert "***" in redacted
        assert "[REDACTED]" not in redacted

    def test_redact_phi_convenience_function(self):
        """Test convenience function."""
        text = "SSN: 123-45-6789"
        redacted = redact_phi(text)

        assert "123-45-6789" not in redacted
        assert "[REDACTED]" in redacted

    def test_redact_phi_dict_convenience_function(self):
        """Test dictionary convenience function."""
        data = {"phone": "555-123-4567"}
        redacted = redact_phi_dict(data)

        assert redacted["phone"] == "[REDACTED]"

    def test_real_world_conversation(self, redactor):
        """Test redacting real conversation text."""
        text = """
        User: My insurance is Blue Cross and my member ID is ABC123456.
        My phone number is 555-123-4567.
        Agent: Thank you! I've scheduled your appointment for 01/15/2024.
        """

        redacted = redactor.redact(text, redact_level="full")

        # Verify all PHI is redacted
        assert "ABC123456" not in redacted
        assert "XXX-XXX-4567" in redacted
        assert "01/15/2024" not in redacted
        assert "MM/DD/2024" in redacted  # Year preserved

    def test_multiple_phi_same_text(self, redactor):
        """Test redacting multiple PHI items in same text."""
        text = "Patient: John Doe, SSN: 123-45-6789, Phone: 555-123-4567, Email: john@example.com"
        redacted = redactor.redact(text)

        # All PHI should be redacted
        assert "123-45-6789" not in redacted
        assert "555-123-4567" not in redacted
        assert "john@example.com" not in redacted
