# utils/email_service.py
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.from_email = settings.DEFAULT_FROM_EMAIL

    def send_email(self, subject, template_name, context, recipient_list,
                   attachments=None, cc=None, bcc=None):
        """
        Send email with template and optional attachments
        """
        try:
            # Render HTML template
            html_content = render_to_string(template_name, context)

            # Create email message
            email = EmailMultiAlternatives(
                subject=subject,
                body=html_content,
                from_email=self.from_email,
                to=recipient_list,
                cc=cc or [],
                bcc=bcc or []
            )

            # Attach HTML content
            email.attach_alternative(html_content, "text/html")

            # Add attachments if provided
            if attachments:
                for attachment in attachments:
                    email.attach_file(attachment)

            # Send email
            email.send()
            logger.info(f"Email sent successfully to {recipient_list}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

