"""Unit tests for configuration settings."""
import pytest
from unittest.mock import patch
import os


# Valid test values that pass validators
VALID_TWILIO_SID = "AC" + "a" * 32  # Must start with AC, 30+ chars
VALID_AUTH_TOKEN = "a" * 32  # 30+ chars
VALID_PHONE = "+15555555555"
VALID_OPENAI_KEY = "sk-" + "a" * 48  # 20+ chars
VALID_DEEPGRAM_KEY = "a" * 40  # 20+ chars


@pytest.mark.unit
class TestSettings:
    """Test configuration settings."""

    def test_settings_loaded_from_env(self):
        """Test that settings are loaded from environment variables."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': VALID_TWILIO_SID,
            'TWILIO_AUTH_TOKEN': VALID_AUTH_TOKEN,
            'TWILIO_PHONE_NUMBER': VALID_PHONE,
            'OPENAI_API_KEY': VALID_OPENAI_KEY,
            'DEEPGRAM_API_KEY': VALID_DEEPGRAM_KEY
        }):
            from src.config.settings import Settings

            settings = Settings()

            assert settings.twilio_account_sid == VALID_TWILIO_SID
            # SecretStr values need getter methods
            assert settings.get_twilio_auth_token() == VALID_AUTH_TOKEN
            assert settings.twilio_phone_number == VALID_PHONE
            assert settings.get_openai_api_key() == VALID_OPENAI_KEY
            assert settings.get_deepgram_api_key() == VALID_DEEPGRAM_KEY

    def test_default_values(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': VALID_TWILIO_SID,
            'TWILIO_AUTH_TOKEN': VALID_AUTH_TOKEN,
            'TWILIO_PHONE_NUMBER': VALID_PHONE,
            'OPENAI_API_KEY': VALID_OPENAI_KEY,
            'DEEPGRAM_API_KEY': VALID_DEEPGRAM_KEY
        }, clear=True):
            from src.config.settings import Settings
            # Clear cache to get fresh settings
            from src.config.settings import get_settings
            get_settings.cache_clear()

            settings = Settings()

            # Check defaults
            assert settings.app_env == "development"
            assert settings.log_level == "INFO"
            assert settings.smtp_host == "smtp.gmail.com"
            assert settings.smtp_port == 587
            assert settings.deepgram_model == "nova-2-phonecall"
            assert settings.deepgram_endpointing_ms == 800

    def test_notification_emails_parsing(self):
        """Test parsing comma-separated notification emails."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': VALID_TWILIO_SID,
            'TWILIO_AUTH_TOKEN': VALID_AUTH_TOKEN,
            'TWILIO_PHONE_NUMBER': VALID_PHONE,
            'OPENAI_API_KEY': VALID_OPENAI_KEY,
            'DEEPGRAM_API_KEY': VALID_DEEPGRAM_KEY,
            'NOTIFICATION_EMAILS_STR': 'test1@example.com,test2@example.com'
        }):
            from src.config.settings import Settings

            settings = Settings()

            # Should parse the comma-separated list
            assert len(settings.notification_emails) == 2
            assert all('@' in email for email in settings.notification_emails)

    def test_empty_notification_emails(self):
        """Test empty notification emails list."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': VALID_TWILIO_SID,
            'TWILIO_AUTH_TOKEN': VALID_AUTH_TOKEN,
            'TWILIO_PHONE_NUMBER': VALID_PHONE,
            'OPENAI_API_KEY': VALID_OPENAI_KEY,
            'DEEPGRAM_API_KEY': VALID_DEEPGRAM_KEY,
            'NOTIFICATION_EMAILS_STR': ''
        }):
            from src.config.settings import Settings

            settings = Settings()

            # Should return empty list
            assert settings.notification_emails == []

    def test_phone_numbers_list(self):
        """Test parsing multiple phone numbers."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': VALID_TWILIO_SID,
            'TWILIO_AUTH_TOKEN': VALID_AUTH_TOKEN,
            'TWILIO_PHONE_NUMBER': VALID_PHONE,
            'TWILIO_PHONE_NUMBERS': '+15551111111,+15552222222',
            'OPENAI_API_KEY': VALID_OPENAI_KEY,
            'DEEPGRAM_API_KEY': VALID_DEEPGRAM_KEY
        }):
            from src.config.settings import Settings

            settings = Settings()

            phone_list = settings.phone_numbers_list

            # Should have primary + additional numbers
            assert VALID_PHONE in phone_list
            assert '+15551111111' in phone_list
            assert '+15552222222' in phone_list

            # Should not have duplicates
            assert len(phone_list) == len(set(phone_list))

    def test_phone_numbers_deduplication(self):
        """Test that duplicate phone numbers are removed."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': VALID_TWILIO_SID,
            'TWILIO_AUTH_TOKEN': VALID_AUTH_TOKEN,
            'TWILIO_PHONE_NUMBER': VALID_PHONE,
            'TWILIO_PHONE_NUMBERS': f'{VALID_PHONE},+15551111111',  # Duplicate primary
            'OPENAI_API_KEY': VALID_OPENAI_KEY,
            'DEEPGRAM_API_KEY': VALID_DEEPGRAM_KEY
        }):
            from src.config.settings import Settings

            settings = Settings()

            phone_list = settings.phone_numbers_list

            # Should deduplicate
            assert phone_list.count(VALID_PHONE) == 1
            assert len(phone_list) == 2

    def test_app_env_variations(self):
        """Test different app environment values."""
        envs = ['development', 'staging', 'production', 'testing', 'test']

        for env in envs:
            with patch.dict(os.environ, {
                'TWILIO_ACCOUNT_SID': VALID_TWILIO_SID,
                'TWILIO_AUTH_TOKEN': VALID_AUTH_TOKEN,
                'TWILIO_PHONE_NUMBER': VALID_PHONE,
                'OPENAI_API_KEY': VALID_OPENAI_KEY,
                'DEEPGRAM_API_KEY': VALID_DEEPGRAM_KEY,
                'APP_ENV': env
            }):
                from src.config.settings import Settings

                settings = Settings()
                assert settings.app_env == env

    def test_invalid_twilio_sid_format(self):
        """Test that invalid Twilio SID is rejected."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'invalid_sid',  # Doesn't start with AC
            'TWILIO_AUTH_TOKEN': VALID_AUTH_TOKEN,
            'TWILIO_PHONE_NUMBER': VALID_PHONE,
            'OPENAI_API_KEY': VALID_OPENAI_KEY,
            'DEEPGRAM_API_KEY': VALID_DEEPGRAM_KEY
        }):
            from src.config.settings import Settings
            import pydantic

            with pytest.raises(pydantic.ValidationError):
                Settings()

    def test_is_production_property(self):
        """Test is_production property."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': VALID_TWILIO_SID,
            'TWILIO_AUTH_TOKEN': VALID_AUTH_TOKEN,
            'TWILIO_PHONE_NUMBER': VALID_PHONE,
            'OPENAI_API_KEY': VALID_OPENAI_KEY,
            'DEEPGRAM_API_KEY': VALID_DEEPGRAM_KEY,
            'APP_ENV': 'production'
        }):
            from src.config.settings import Settings

            settings = Settings()
            assert settings.is_production is True
            assert settings.is_testing is False

    def test_is_testing_property(self):
        """Test is_testing property."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': VALID_TWILIO_SID,
            'TWILIO_AUTH_TOKEN': VALID_AUTH_TOKEN,
            'TWILIO_PHONE_NUMBER': VALID_PHONE,
            'OPENAI_API_KEY': VALID_OPENAI_KEY,
            'DEEPGRAM_API_KEY': VALID_DEEPGRAM_KEY,
            'APP_ENV': 'testing'
        }):
            from src.config.settings import Settings

            settings = Settings()
            assert settings.is_testing is True
            assert settings.is_production is False

    def test_secret_str_values_not_exposed(self):
        """Test that SecretStr values are not exposed in repr."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': VALID_TWILIO_SID,
            'TWILIO_AUTH_TOKEN': VALID_AUTH_TOKEN,
            'TWILIO_PHONE_NUMBER': VALID_PHONE,
            'OPENAI_API_KEY': VALID_OPENAI_KEY,
            'DEEPGRAM_API_KEY': VALID_DEEPGRAM_KEY
        }):
            from src.config.settings import Settings

            settings = Settings()
            settings_repr = repr(settings)

            # Secret values should be masked
            assert VALID_AUTH_TOKEN not in settings_repr
            assert VALID_OPENAI_KEY not in settings_repr
            assert VALID_DEEPGRAM_KEY not in settings_repr
