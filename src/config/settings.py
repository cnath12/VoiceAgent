"""Configuration management for the voice agent."""
import re
from typing import Optional
from pydantic import Field, field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with validation."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # Twilio - Required with validation
    twilio_account_sid: str = Field(min_length=30, description="Twilio Account SID (starts with AC)")
    twilio_auth_token: SecretStr = Field(min_length=30, description="Twilio Auth Token")
    twilio_phone_number: str = Field(min_length=10, description="Primary Twilio phone number")
    twilio_phone_numbers: str = ""  # Comma-separated list of additional numbers

    # AI Services - Required with validation
    openai_api_key: SecretStr = Field(min_length=20, description="OpenAI API key")
    deepgram_api_key: SecretStr = Field(min_length=20, description="Deepgram API key")
    cartesia_api_key: str = ""  # Optional

    # Deepgram tuning
    deepgram_model: str = "nova-2-phonecall"  # Optimized for phone calls
    deepgram_encoding: str = "mulaw"  # default to mu-law for Twilio telephony
    deepgram_endpointing_ms: int = Field(default=800, ge=100, le=5000)

    # Hybrid STT Architecture
    # When enabled, creates a DIRECT Deepgram WebSocket connection in parallel
    # with Pipecat's built-in STT. This was added as a workaround for reliability
    # issues with Pipecat's STT. Set to False once Pipecat STT is reliable.
    # Monitor metrics (voiceagent_transcriptions_total{source="direct|pipecat"})
    # to see which path provides transcriptions.
    enable_direct_stt: bool = True  # Enable parallel direct Deepgram connection

    # Email - Optional in dev, required in production
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_email: str = ""
    smtp_password: SecretStr = Field(default="")

    # USPS API - Optional
    usps_user_id: str = ""

    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_db: int = Field(default=0, ge=0, le=15)
    redis_password: SecretStr = Field(default="")
    redis_ssl: bool = False
    redis_url: str = ""  # Optional: full Redis URL (overrides individual settings)
    use_redis: bool = False  # Enable Redis-backed state management

    # Application
    app_env: str = Field(default="development", pattern=r"^(development|staging|production|testing|test)$")
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    public_host: str = ""  # Optional explicit public host for Twilio callbacks
    admin_api_key: str = ""  # Admin API key to protect debug endpoints
    echo_test: bool = False  # Diagnostics

    # Notification Recipients (comma-separated in env)
    notification_emails_str: str = ""  # Configure via NOTIFICATION_EMAILS_STR env variable
    test_notification_email: str = "chirag12084@gmail.com"  # Test environment recipient override

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------

    @field_validator("twilio_account_sid")
    @classmethod
    def validate_twilio_account_sid(cls, v: str) -> str:
        """Validate Twilio Account SID format."""
        if not v.startswith("AC"):
            raise ValueError("Twilio Account SID must start with 'AC'")
        return v

    @field_validator("twilio_phone_number")
    @classmethod
    def validate_phone_number(cls, v: str) -> str:
        """Validate phone number format."""
        # Remove common formatting
        cleaned = re.sub(r"[\s\-\(\)]+", "", v)
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        if not re.match(r"^\+\d{10,15}$", cleaned):
            raise ValueError("Phone number must be E.164 format (e.g., +15551234567)")
        return cleaned

    @field_validator("smtp_email")
    @classmethod
    def validate_smtp_email(cls, v: str, info) -> str:
        """Validate SMTP email format and require in production."""
        if not v:
            # Check if we're in production (info.data may not have app_env yet during validation)
            return v
        # Basic email validation
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        """Normalize app_env to lowercase."""
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Normalize log_level to uppercase."""
        return v.upper()

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

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
        if self.twilio_phone_number:
            numbers.append(self.twilio_phone_number)
        # Add additional numbers
        if self.twilio_phone_numbers:
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

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"

    @property
    def is_testing(self) -> bool:
        """Check if running in test environment."""
        return self.app_env in ("testing", "test")

    # -------------------------------------------------------------------------
    # Secret Accessors (for services that need the raw value)
    # -------------------------------------------------------------------------

    def get_twilio_auth_token(self) -> str:
        """Get Twilio auth token as string."""
        return self.twilio_auth_token.get_secret_value()

    def get_openai_api_key(self) -> str:
        """Get OpenAI API key as string."""
        return self.openai_api_key.get_secret_value()

    def get_deepgram_api_key(self) -> str:
        """Get Deepgram API key as string."""
        return self.deepgram_api_key.get_secret_value()

    def get_smtp_password(self) -> str:
        """Get SMTP password as string."""
        return self.smtp_password.get_secret_value() if self.smtp_password else ""

    def get_redis_password(self) -> str:
        """Get Redis password as string."""
        return self.redis_password.get_secret_value() if self.redis_password else ""


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
