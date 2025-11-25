"""Email service for sending appointment confirmations.

Uses aiosmtplib for async email sending to avoid blocking the event loop.
"""
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Optional

import aiosmtplib

from src.core.models import ConversationState
from src.config.settings import get_settings
from src.config.constants import EmailConfig
from src.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


class EmailService:
    """Service for sending appointment confirmation emails asynchronously."""

    def __init__(self):
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_email = settings.smtp_email
        self.smtp_password = settings.get_smtp_password()
        # Determine staff recipients: use test override in non-production app envs
        if settings.is_testing or settings.app_env in {"development", "staging"}:
            self.notification_emails = [settings.test_notification_email]
        else:
            self.notification_emails = settings.notification_emails

    async def send_appointment_confirmation(self, state: ConversationState) -> bool:
        """Send appointment confirmation to patient and notification to staff.

        Args:
            state: Current conversation state with patient info

        Returns:
            True if all emails sent successfully, False otherwise
        """
        success = True

        try:
            # Send to patient if email provided
            if state.patient_info.email:
                patient_result = await self._send_patient_confirmation(state)
                if not patient_result:
                    success = False

            # Always send notification to staff
            staff_result = await self._send_staff_notification(state)
            if not staff_result:
                success = False

            return success

        except Exception as e:
            logger.error(f"Email sending error: {e}", exc_info=True)
            return False

    async def _send_patient_confirmation(self, state: ConversationState) -> bool:
        """Send confirmation email to patient.

        Args:
            state: Conversation state with patient info

        Returns:
            True if email sent successfully
        """
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

        return await self._send_email(
            to_email=state.patient_info.email,
            subject=subject,
            body=body,
            is_html=True
        )

    async def _send_staff_notification(self, state: ConversationState) -> bool:
        """Send notification to staff members.

        Args:
            state: Conversation state with patient info

        Returns:
            True if all staff emails sent successfully
        """
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

        # Send to all notification recipients concurrently
        tasks = [
            self._send_email(
                to_email=email,
                subject=subject,
                body=body,
                is_html=True
            )
            for email in self.notification_emails
        ]

        if not tasks:
            return True

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Check for any failures
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Staff notification failed: {result}")
                return False
            if result is False:
                return False

        return True

    async def _send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        is_html: bool = False
    ) -> bool:
        """Send email via async SMTP.

        Uses aiosmtplib for non-blocking email sending.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body content
            is_html: Whether body is HTML

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.smtp_email or not self.smtp_password:
            logger.warning("SMTP not configured, skipping email send")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.smtp_email
            msg['To'] = to_email
            msg['Subject'] = subject

            # Attach body
            mime_type = 'html' if is_html else 'plain'
            msg.attach(MIMEText(body, mime_type))

            # Send email asynchronously with retry
            for attempt in range(EmailConfig.MAX_RETRY_ATTEMPTS):
                try:
                    await aiosmtplib.send(
                        msg,
                        hostname=self.smtp_host,
                        port=self.smtp_port,
                        start_tls=True,
                        username=self.smtp_email,
                        password=self.smtp_password,
                        timeout=EmailConfig.SMTP_TIMEOUT_SEC
                    )
                    logger.info(f"Email sent successfully to {to_email}")
                    return True

                except aiosmtplib.SMTPException as smtp_error:
                    if attempt < EmailConfig.MAX_RETRY_ATTEMPTS - 1:
                        delay = EmailConfig.RETRY_BASE_DELAY_SEC * (attempt + 1)
                        logger.warning(
                            f"SMTP error (attempt {attempt + 1}), retrying in {delay}s: {smtp_error}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        raise

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}", exc_info=True)
            # Don't raise - we don't want email failures to break the flow
            return False

        return False

    def _format_address(self, address) -> str:
        """Format address for display.

        Args:
            address: Address object

        Returns:
            Formatted address string
        """
        if not address:
            return "Not provided"
        return f"{address.street}, {address.city}, {address.state} {address.zip_code}"

    def _calculate_duration(self, start_time: datetime) -> int:
        """Calculate call duration in minutes.

        Args:
            start_time: Call start time

        Returns:
            Duration in minutes
        """
        duration = datetime.utcnow() - start_time
        return int(duration.total_seconds() / 60)
