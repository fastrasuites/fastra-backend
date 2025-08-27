from django.core.mail import EmailMessage
import os
from smtplib import SMTPServerDisconnected

class Util:
    @staticmethod
    def send_email(data):
        email = EmailMessage(subject=data['email_subject'], body=data['email_body'], to=[data['to_email']])
        email.send(fail_silently=False)

    def send_mail_with_attachment(data):
        """
        Sends an email with optional attachment from email_attachment field.
        """
        subject = data["email_subject"] or "Return Incoming Product"
        body = data["email_body"] or "Please see the attached file."
        to_email = [data["supplier_email"]] if data["supplier_email"] else []

        # Create email
        email = EmailMessage(
            subject=subject,
            body=body,
            to=to_email,
        )

        # Attach file if it exists
        if data["email_attachment"]:
            uploaded_file = data["email_attachment"]
            email.attach(
                uploaded_file.name,           
                uploaded_file.read(),         
                uploaded_file.content_type    
            )

        try:
            email.send(fail_silently=False)
            print(f"Email sent successfully to the Supplier with the email of {to_email}")
            return True
        
        except SMTPServerDisconnected as e:
            print(f"Email Server connection failed: SMTP server disconnected.")
            return False
        except Exception as e:
            print(f"Error sending email: {e}")
            return False
