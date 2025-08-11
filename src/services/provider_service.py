"""Mock provider and appointment scheduling service."""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import random

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProviderService:
    """Service for managing providers and appointment slots."""
    
    def __init__(self):
        # Mock provider data
        self.providers = [
            {
                "id": "dr_smith_001",
                "name": "Sarah Smith",
                "specialty": "Family Medicine",
                "accepting_new": True,
                "insurance": ["Aetna", "Blue Cross", "United", "Medicare"],
                "languages": ["English", "Spanish"],
                "rating": 4.8
            },
            {
                "id": "dr_johnson_002",
                "name": "Michael Johnson",
                "specialty": "Internal Medicine",
                "accepting_new": True,
                "insurance": ["Blue Cross", "Cigna", "Humana", "United"],
                "languages": ["English"],
                "rating": 4.6
            },
            {
                "id": "dr_patel_003",
                "name": "Priya Patel",
                "specialty": "Family Medicine",
                "accepting_new": True,
                "insurance": ["Aetna", "Cigna", "Kaiser", "Medicare"],
                "languages": ["English", "Hindi", "Gujarati"],
                "rating": 4.9
            },
            {
                "id": "dr_garcia_004",
                "name": "Carlos Garcia",
                "specialty": "Urgent Care",
                "accepting_new": True,
                "insurance": ["All major insurance accepted"],
                "languages": ["English", "Spanish"],
                "rating": 4.5
            },
            {
                "id": "dr_wong_005",
                "name": "Jennifer Wong",
                "specialty": "Internal Medicine",
                "accepting_new": True,
                "insurance": ["Blue Cross", "Kaiser", "United", "Medicaid"],
                "languages": ["English", "Mandarin", "Cantonese"],
                "rating": 4.7
            }
        ]
    
    async def get_available_providers(
        self, 
        chief_complaint: Optional[str] = None,
        insurance: Optional[str] = None
    ) -> List[Dict]:
        """Get available providers based on criteria."""
        
        available = []
        
        for provider in self.providers:
            # Check if accepting new patients
            if not provider["accepting_new"]:
                continue
            
            # Check insurance compatibility
            if insurance:
                insurance_lower = insurance.lower()
                provider_insurance = [ins.lower() for ins in provider["insurance"]]
                
                # Check if insurance is accepted
                if "all major" in " ".join(provider_insurance):
                    pass  # Accept all
                elif not any(insurance_lower in ins or ins in insurance_lower 
                           for ins in provider_insurance):
                    continue
            
            # Score based on complaint matching
            score = self._calculate_match_score(provider, chief_complaint)
            
            available.append({
                **provider,
                "match_score": score
            })
        
        # Sort by match score and rating
        available.sort(key=lambda x: (x["match_score"], x["rating"]), reverse=True)
        
        return available[:5]  # Return top 5 matches
    
    def _calculate_match_score(self, provider: Dict, complaint: Optional[str]) -> float:
        """Calculate how well provider matches the complaint."""
        
        if not complaint:
            return provider["rating"]
        
        complaint_lower = complaint.lower()
        score = provider["rating"]
        
        # Urgent/immediate care keywords
        urgent_keywords = ["urgent", "immediate", "today", "asap", "emergency", "severe"]
        if any(keyword in complaint_lower for keyword in urgent_keywords):
            if provider["specialty"] == "Urgent Care":
                score += 2.0
            elif provider["specialty"] == "Family Medicine":
                score += 1.0
        
        # Chronic condition keywords
        chronic_keywords = ["diabetes", "hypertension", "chronic", "ongoing", "management"]
        if any(keyword in complaint_lower for keyword in chronic_keywords):
            if provider["specialty"] == "Internal Medicine":
                score += 1.5
            elif provider["specialty"] == "Family Medicine":
                score += 1.0
        
        # General/routine care
        routine_keywords = ["checkup", "physical", "routine", "annual", "prevention"]
        if any(keyword in complaint_lower for keyword in routine_keywords):
            if provider["specialty"] == "Family Medicine":
                score += 1.5
        
        return score
    
    async def get_available_slots(self, provider_id: str) -> List[Dict]:
        """Get available appointment slots for a provider."""
        
        slots = []
        now = datetime.now()
        
        # Generate slots for next 7 days
        for days_ahead in range(1, 8):
            date = now + timedelta(days=days_ahead)
            
            # Skip weekends for non-urgent care
            if date.weekday() >= 5 and "urgent" not in provider_id:
                continue
            
            # Morning slots (9 AM - 12 PM)
            for hour in [9, 10, 11]:
                for minute in [0, 30]:
                    slot_time = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    # Random availability (70% chance)
                    if random.random() < 0.7:
                        slots.append(self._create_slot(slot_time))
            
            # Afternoon slots (2 PM - 5 PM)
            for hour in [14, 15, 16]:
                for minute in [0, 30]:
                    slot_time = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    
                    # Random availability (60% chance)
                    if random.random() < 0.6:
                        slots.append(self._create_slot(slot_time))
        
        # For urgent care, add some same-day slots
        if "urgent" in provider_id or "garcia" in provider_id:
            # Add slots for today if after current time
            for hour in range(now.hour + 1, 18):  # Until 6 PM
                slot_time = now.replace(hour=hour, minute=0, second=0, microsecond=0)
                if random.random() < 0.5:
                    slots.append(self._create_slot(slot_time))
        
        return slots[:10]  # Return first 10 available slots
    
    def _create_slot(self, slot_time: datetime) -> Dict:
        """Create a slot dictionary with display information."""
        
        # Determine if it's today, tomorrow, or later
        now = datetime.now()
        days_diff = (slot_time.date() - now.date()).days
        
        if days_diff == 0:
            day_str = "today"
        elif days_diff == 1:
            day_str = "tomorrow"
        else:
            day_str = slot_time.strftime("%A")  # Day name
        
        # Format time
        time_str = slot_time.strftime("%I:%M %p").lstrip('0')
        
        # Create display string
        if days_diff <= 1:
            display = f"{day_str} at {time_str}"
        else:
            display = f"{day_str}, {slot_time.strftime('%B %d')} at {time_str}"
        
        return {
            "datetime": slot_time,
            "display": display,
            "keywords": [
                day_str.lower(),
                slot_time.strftime("%A").lower(),
                "morning" if slot_time.hour < 12 else "afternoon"
            ]
        }
    
    async def book_appointment(
        self, 
        provider_id: str, 
        slot_datetime: datetime,
        patient_info: Dict
    ) -> Dict:
        """Book an appointment (mock implementation)."""
        
        # Generate confirmation number
        confirmation = f"APT{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Find provider details
        provider = next((p for p in self.providers if p["id"] == provider_id), None)
        
        if not provider:
            raise ValueError(f"Provider {provider_id} not found")
        
        return {
            "confirmation_number": confirmation,
            "provider": provider,
            "appointment_time": slot_datetime,
            "patient": patient_info,
            "status": "confirmed",
            "created_at": datetime.now()
        }