"""Address validation service using USPS API."""
import asyncio
import xml.etree.ElementTree as ET
from typing import Optional
import httpx
import urllib.parse

from src.core.models import Address
from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class AddressService:
    """Service for validating addresses via USPS or mock."""
    
    def __init__(self):
        self.usps_user_id = settings.usps_user_id
        self.base_url = "https://secure.shippingapis.com/ShippingAPI.dll"
        
    async def validate_address(
        self, 
        street: str, 
        city: str, 
        state: str, 
        zip_code: str
    ) -> Optional[Address]:
        """Validate address using USPS API or intelligent mock."""
        
        # If no USPS credentials, use mock validation
        if not self.usps_user_id:
            return self._mock_validate_address(street, city, state, zip_code)
        
        try:
            # Build USPS API request
            xml_request = self._build_usps_request(street, city, state, zip_code)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    params={
                        "API": "Verify",
                        "XML": xml_request
                    },
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    return self._parse_usps_response(response.text)
                else:
                    logger.error(f"USPS API error: {response.status_code}")
                    return self._mock_validate_address(street, city, state, zip_code)
                    
        except Exception as e:
            logger.error(f"Address validation error: {e}")
            return self._mock_validate_address(street, city, state, zip_code)
    
    def _build_usps_request(self, street: str, city: str, state: str, zip_code: str) -> str:
        """Build USPS XML request."""
        xml = f'''<AddressValidateRequest USERID="{self.usps_user_id}">
            <Revision>1</Revision>
            <Address ID="0">
                <Address1></Address1>
                <Address2>{street}</Address2>
                <City>{city}</City>
                <State>{state}</State>
                <Zip5>{zip_code[:5]}</Zip5>
                <Zip4></Zip4>
            </Address>
        </AddressValidateRequest>'''
        return xml
    
    def _parse_usps_response(self, xml_response: str) -> Optional[Address]:
        """Parse USPS XML response."""
        try:
            root = ET.fromstring(xml_response)
            
            # Check for error
            error = root.find(".//Error")
            if error is not None:
                error_desc = error.find("Description").text
                logger.error(f"USPS validation error: {error_desc}")
                return None
            
            # Extract validated address
            address_elem = root.find(".//Address")
            if address_elem is not None:
                return Address(
                    street=address_elem.find("Address2").text or "",
                    city=address_elem.find("City").text or "",
                    state=address_elem.find("State").text or "",
                    zip_code=address_elem.find("Zip5").text or "",
                    validated=True,
                    validation_message="Address validated by USPS"
                )
                
        except Exception as e:
            logger.error(f"Error parsing USPS response: {e}")
            
        return None
    
    def _mock_validate_address(
        self, 
        street: str, 
        city: str, 
        state: str, 
        zip_code: str
    ) -> Address:
        """Intelligent mock validation when USPS is not available."""
        
        # Basic validation rules
        is_valid = True
        messages = []
        
        # Check street
        if not street or len(street) < 5:
            is_valid = False
            messages.append("Street address appears incomplete")
        elif not any(char.isdigit() for char in street):
            is_valid = False
            messages.append("Street address missing house number")
        
        # Check city
        if not city or len(city) < 2:
            is_valid = False
            messages.append("City is required")
        
        # Check state
        valid_states = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", 
                       "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
                       "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
                       "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
                       "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"]
        
        if state.upper() not in valid_states:
            is_valid = False
            messages.append("Invalid state code")
        
        # Check zip
        if not zip_code or not zip_code.isdigit() or len(zip_code) not in [5, 9]:
            is_valid = False
            messages.append("Invalid zip code format")
        
        # Common invalid patterns
        invalid_patterns = ["123 main", "test address", "asdf", "none", "n/a"]
        if any(pattern in street.lower() for pattern in invalid_patterns):
            is_valid = False
            messages.append("Address appears to be a placeholder")
        
        return Address(
            street=street.title(),
            city=city.title(),
            state=state.upper(),
            zip_code=zip_code,
            validated=is_valid,
            validation_message="; ".join(messages) if messages else "Address validation successful (mock)"
        )