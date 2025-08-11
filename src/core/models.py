"""Data models for the healthcare voice agent."""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr
from enum import Enum


class ConversationPhase(str, Enum):
    """Phases of the appointment scheduling conversation."""
    GREETING = "greeting"
    EMERGENCY_CHECK = "emergency_check"
    INSURANCE = "insurance"
    CHIEF_COMPLAINT = "chief_complaint"
    DEMOGRAPHICS = "demographics"
    CONTACT_INFO = "contact_info"
    PROVIDER_SELECTION = "provider_selection"
    APPOINTMENT_SCHEDULING = "appointment_scheduling"
    CONFIRMATION = "confirmation"
    COMPLETED = "completed"


class Address(BaseModel):
    """Patient address model."""
    street: str
    city: str
    state: str
    zip_code: str
    validated: bool = False
    validation_message: Optional[str] = None


class Insurance(BaseModel):
    """Insurance information model."""
    payer_name: str
    member_id: str
    group_number: Optional[str] = None


class PatientInfo(BaseModel):
    """Complete patient information."""
    # Insurance
    insurance: Optional[Insurance] = None
    
    # Medical
    chief_complaint: Optional[str] = None
    urgency_level: Optional[int] = Field(None, ge=1, le=10)
    
    # Demographics
    address: Optional[Address] = None
    
    # Contact
    phone_number: Optional[str] = None
    email: Optional[EmailStr] = None
    
    # Appointment
    selected_provider: Optional[str] = None
    appointment_datetime: Optional[datetime] = None


class ConversationState(BaseModel):
    """Current state of the conversation."""
    call_sid: str
    phase: ConversationPhase = ConversationPhase.GREETING
    patient_info: PatientInfo = Field(default_factory=PatientInfo)
    error_count: int = 0
    start_time: datetime = Field(default_factory=datetime.utcnow)
    transcript: List[dict] = Field(default_factory=list)
    
    def add_transcript_entry(self, speaker: str, text: str):
        """Add entry to conversation transcript."""
        self.transcript.append({
            "timestamp": datetime.utcnow().isoformat(),
            "speaker": speaker,
            "text": text
        })
