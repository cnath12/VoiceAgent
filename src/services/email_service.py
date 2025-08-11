"""Email service for sending appointment confirmations."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List

from src.core.models import ConversationState
from src.config.settings import get_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmailService:
    """Service for sending appointment confirmation emails."""
    
    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_email = settings.smtp_email
        self.smtp_password = settings.smtp_password
        # Determine staff recipients: use test override in non-production app envs
        if settings.app_env.lower() in {"development", "test", "testing", "staging"}:
            self.notification_emails = [settings.test_notification_email]
        else:
            self.notification_emails = settings.notification_emails
    
    async def send_appointment_confirmation(self, state: ConversationState) -> bool:
        """Send appointment confirmation to patient and notification to staff."""
        
        try:
            # Send to patient if email provided
            if state.patient_info.email:
                await self._send_patient_confirmation(state)
            
            # Always send notification to staff
            await self._send_staff_notification(state)
            
            return True
            
        except Exception as e:
            logger.error(f"Email sending error: {e}")
            return False
    
    async def _send_patient_confirmation(self, state: ConversationState):
        """Send confirmation email to patient."""
        
        subject = "Appointment Confirmation - Assort Health"
        
        # Format appointment time
        appt_time = state.patient_info.appointment_datetime
        if appt_time:
            appt_str = appt_time.strftime("%A, %B %d at %I:%M %p")
        else:
            appt_str = "Time to be confirmed"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>Appointment Confirmation</h2>
            
            <p>Dear Patient,</p>
            
            <p>Your appointment has been successfully scheduled.</p>
            
            <h3>Appointment Details:</h3>
            <ul>
                <li><strong>Provider:</strong> {state.patient_info.selected_provider or 'To be assigned'}</li>
                <li><strong>Date & Time:</strong> {appt_str}</li>
                <li><strong>Reason for Visit:</strong> {state.patient_info.chief_complaint or 'General consultation'}</li>
            </ul>
            
            <h3>What to Bring:</h3>
            <ul>
                <li>Photo ID</li>
                <li>Insurance card</li>
                <li>List of current medications</li>
                <li>Any relevant medical records</li>
            </ul>
            
            <p>If you need to reschedule or cancel, please call us at least 24 hours in advance.</p>
            
            <p>We look forward to seeing you!</p>
            
            <p>Best regards,<br>
            Assort Health Team</p>
        </body>
        </html>
        """
        
        await self._send_email(
            to_email=state.patient_info.email,
            subject=subject,
            body=body,
            is_html=True
        )
    
    async def _send_staff_notification(self, state: ConversationState):
        """Send notification to staff members."""
        
        subject = f"New Appointment Scheduled - {datetime.now().strftime('%m/%d/%Y %I:%M %p')}"
        
        # Format patient information
        patient_info = state.patient_info
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <h2>New Appointment Notification</h2>
            
            <h3>Patient Information:</h3>
            <table border="1" cellpadding="5" cellspacing="0">
                <tr>
                    <td><strong>Call SID:</strong></td>
                    <td>{state.call_sid}</td>
                </tr>
                <tr>
                    <td><strong>Insurance Provider:</strong></td>
                    <td>{patient_info.insurance.payer_name if patient_info.insurance else 'Not provided'}</td>
                </tr>
                <tr>
                    <td><strong>Member ID:</strong></td>
                    <td>{patient_info.insurance.member_id if patient_info.insurance else 'Not provided'}</td>
                </tr>
                <tr>
                    <td><strong>Chief Complaint:</strong></td>
                    <td>{patient_info.chief_complaint or 'Not provided'}</td>
                </tr>
                <tr>
                    <td><strong>Urgency Level:</strong></td>
                    <td>{patient_info.urgency_level or 'Not assessed'}/10</td>
                </tr>
                <tr>
                    <td><strong>Address:</strong></td>
                    <td>{self._format_address(patient_info.address) if patient_info.address else 'Not provided'}</td>
                </tr>
                <tr>
                    <td><strong>Phone:</strong></td>
                    <td>{patient_info.phone_number or 'Not provided'}</td>
                </tr>
                <tr>
                    <td><strong>Email:</strong></td>
                    <td>{patient_info.email or 'Not provided'}</td>
                </tr>
                <tr>
                    <td><strong>Selected Provider:</strong></td>
                    <td>{patient_info.selected_provider or 'Not selected'}</td>
                </tr>
                <tr>
                    <td><strong>Appointment Time:</strong></td>
                    <td>{patient_info.appointment_datetime.strftime('%m/%d/%Y %I:%M %p') if patient_info.appointment_datetime else 'Not scheduled'}</td>
                </tr>
            </table>
            
            <h3>Call Statistics:</h3>
            <ul>
                <li>Call Duration: {self._calculate_duration(state.start_time)} minutes</li>
                <li>Error Count: {state.error_count}</li>
                <li>Conversation Completed: Yes</li>
            </ul>
            
            <p><em>This appointment was scheduled via the automated voice AI system.</em></p>
        </body>
        </html>
        """
        
        # Send to all notification recipients
        for email in self.notification_emails:
            await self._send_email(
                to_email=email,
                subject=subject,
                body=body,
                is_html=True
            )
    
    async def _send_email(
        self, 
        to_email: str, 
        subject: str, 
        body: str, 
        is_html: bool = False
    ):
        """Send email via SMTP."""
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.smtp_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Attach body
            mime_type = 'html' if is_html else 'plain'
            msg.attach(MIMEText(body, mime_type))
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_email, self.smtp_password)
                server.send_message(msg)
                
            logger.info(f"Email sent successfully to {to_email}")
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            # Don't raise - we don't want email failures to break the flow
    
    def _format_address(self, address) -> str:
        """Format address for display."""
        if not address:
            return "Not provided"
        return f"{address.street}, {address.city}, {address.state} {address.zip_code}"
    
    def _calculate_duration(self, start_time: datetime) -> int:
        """Calculate call duration in minutes."""
        duration = datetime.utcnow() - start_time
        return int(duration.total_seconds() / 60)