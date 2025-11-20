"""Unit tests for configuration settings."""
import pytest
from unittest.mock import patch
import os


@pytest.mark.unit
class TestSettings:
    """Test configuration settings."""

    def test_settings_loaded_from_env(self):
        """Test that settings are loaded from environment variables."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token',
            'TWILIO_PHONE_NUMBER': '+15555555555',
            'OPENAI_API_KEY': 'test_openai',
            'DEEPGRAM_API_KEY': 'test_deepgram'
        }):
            from src.config.settings import Settings

            settings = Settings()

            assert settings.twilio_account_sid == 'test_sid'
            assert settings.twilio_auth_token == 'test_token'
            assert settings.twilio_phone_number == '+15555555555'
            assert settings.openai_api_key == 'test_openai'
            assert settings.deepgram_api_key == 'test_deepgram'

    def test_default_values(self):
        """Test default configuration values."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token',
            'TWILIO_PHONE_NUMBER': '+15555555555',
            'OPENAI_API_KEY': 'test_openai',
            'DEEPGRAM_API_KEY': 'test_deepgram'
        }):
            from src.config.settings import Settings

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
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token',
            'TWILIO_PHONE_NUMBER': '+15555555555',
            'OPENAI_API_KEY': 'test_openai',
            'DEEPGRAM_API_KEY': 'test_deepgram'
        }):
            from src.config.settings import Settings

            settings = Settings()

            # Default should parse the hardcoded list
            assert len(settings.notification_emails) > 0
            assert all('@' in email for email in settings.notification_emails)

    def test_phone_numbers_list(self):
        """Test parsing multiple phone numbers."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token',
            'TWILIO_PHONE_NUMBER': '+15555555555',
            'TWILIO_PHONE_NUMBERS': '+15551111111,+15552222222',
            'OPENAI_API_KEY': 'test_openai',
            'DEEPGRAM_API_KEY': 'test_deepgram'
        }):
            from src.config.settings import Settings

            settings = Settings()

            phone_list = settings.phone_numbers_list

            # Should have primary + additional numbers
            assert '+15555555555' in phone_list
            assert '+15551111111' in phone_list
            assert '+15552222222' in phone_list

            # Should not have duplicates
            assert len(phone_list) == len(set(phone_list))

    def test_phone_numbers_deduplication(self):
        """Test that duplicate phone numbers are removed."""
        with patch.dict(os.environ, {
            'TWILIO_ACCOUNT_SID': 'test_sid',
            'TWILIO_AUTH_TOKEN': 'test_token',
            'TWILIO_PHONE_NUMBER': '+15555555555',
            'TWILIO_PHONE_NUMBERS': '+15555555555,+15551111111',  # Duplicate primary
            'OPENAI_API_KEY': 'test_openai',
            'DEEPGRAM_API_KEY': 'test_deepgram'
        }):
            from src.config.settings import Settings

            settings = Settings()

            phone_list = settings.phone_numbers_list

            # Should deduplicate
            assert phone_list.count('+15555555555') == 1
            assert len(phone_list) == 2

    def test_app_env_variations(self):
        """Test different app environment values."""
        envs = ['development', 'staging', 'production', 'testing']

        for env in envs:
            with patch.dict(os.environ, {
                'TWILIO_ACCOUNT_SID': 'test_sid',
                'TWILIO_AUTH_TOKEN': 'test_token',
                'TWILIO_PHONE_NUMBER': '+15555555555',
                'OPENAI_API_KEY': 'test_openai',
                'DEEPGRAM_API_KEY': 'test_deepgram',
                'APP_ENV': env
            }):
                from src.config.settings import Settings

                settings = Settings()
                assert settings.app_env == env
