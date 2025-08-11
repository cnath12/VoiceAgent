#!/usr/bin/env python3
"""
Simple test script to verify Twilio setup
"""
import os
from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables
load_dotenv()

def test_twilio_setup():
    """Test Twilio credentials and phone number"""
    try:
        # Get credentials from environment
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        # Check if credentials are set
        if not account_sid or account_sid == 'your_account_sid_here':
            print("❌ TWILIO_ACCOUNT_SID not set in .env file")
            return False
            
        if not auth_token or auth_token == 'your_auth_token_here':
            print("❌ TWILIO_AUTH_TOKEN not set in .env file")
            return False
            
        if not phone_number or phone_number == 'your_twilio_phone_number_here':
            print("❌ TWILIO_PHONE_NUMBER not set in .env file")
            return False
        
        # Test Twilio client
        client = Client(account_sid, auth_token)
        
        # Try to fetch account info to verify credentials
        account = client.api.accounts(account_sid).fetch()
        print(f"✅ Twilio credentials verified!")
        print(f"   Account: {account.friendly_name}")
        print(f"   Status: {account.status}")
        print(f"   Phone Number: {phone_number}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Twilio setup: {e}")
        return False

if __name__ == "__main__":
    print("Testing Twilio Setup...")
    test_twilio_setup() 