"""Configuration management for the voice agent."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""
    
    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str  # Keep for backward compatibility
    twilio_phone_numbers: str = ""  # Comma-separated list of additional numbers
    
    # AI Services
    openai_api_key: str
    deepgram_api_key: str
    cartesia_api_key: str = ""  # Optional
    # Deepgram tuning
    deepgram_model: str = "nova-2-phonecall"  # Optimized for phone calls
    deepgram_encoding: str = "mulaw"  # default to mu-law for Twilio telephony
    deepgram_endpointing_ms: int = 800  # Reduced for more responsive recognition
    
    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_email: str = ""  # Optional for testing
    smtp_password: str = ""  # Optional for testing
    
    # USPS API
    usps_user_id: str = ""
    
    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    # Optional explicit public host for Twilio callbacks and WS stream
    public_host: str = ""
    # Admin API key to protect debug endpoints
    admin_api_key: str = ""
    # Diagnostics
    echo_test: bool = False
    
    # Notification Recipients (comma-separated in env)
    notification_emails_str: str = "jeff@assorthealth.com,connor@assorthealth.com,cole@assorthealth.com,jciminelli@assorthealth.com,akumar@assorthealth.com,riley@assorthealth.com"
    # Test environment recipient override
    test_notification_email: str = "chirag12084@gmail.com"
    @property
    def notification_emails(self) -> list[str]:
        """Parse comma-separated email string into list."""
        if not self.notification_emails_str:
            return []
        return [email.strip() for email in self.notification_emails_str.split(",") if email.strip()]

    @property
    def phone_numbers_list(self) -> list[str]:
        """Return all configured Twilio phone numbers without duplicates (preserve order)."""
        numbers: list[str] = []
        # Add primary number first
        if getattr(self, "twilio_phone_number", None):
            numbers.append(self.twilio_phone_number)
        # Add additional numbers
        if getattr(self, "twilio_phone_numbers", None):
            additional = [n.strip() for n in self.twilio_phone_numbers.split(",") if n.strip()]
            numbers.extend(additional)
        # Deduplicate while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for n in numbers:
            if n not in seen:
                deduped.append(n)
                seen.add(n)
        return deduped
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()