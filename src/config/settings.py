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
    twilio_phone_number: str
    
    # AI Services
    openai_api_key: str
    deepgram_api_key: str
    cartesia_api_key: str
    # Deepgram tuning
    deepgram_model: str = "nova-2-phonecall"  # Optimized for phone calls
    deepgram_encoding: str = "mulaw"  # default to mu-law for Twilio telephony
    deepgram_endpointing_ms: int = 800  # Reduced for more responsive recognition
    
    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_email: str
    smtp_password: str
    
    # USPS API
    usps_user_id: str = ""
    
    # Application
    app_env: str = "development"
    log_level: str = "INFO"
    # Optional explicit public host for Twilio callbacks and WS stream
    public_host: str = ""
    # Diagnostics
    echo_test: bool = False
    
    # Notification Recipients (comma-separated in env)
    notification_emails_str: str = "jeff@assorthealth.com,connor@assorthealth.com,cole@assorthealth.com,jciminelli@assorthealth.com,akumar@assorthealth.com,riley@assorthealth.com"
    @property
    def notification_emails(self) -> list[str]:
        """Parse comma-separated email string into list."""
        return [email.strip() for email in self.notification_emails_str.split(",") if email.strip()]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()