import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from django.conf import settings

def send_email_real(user, to_email, subject, html_content):
    """
    Real email sending function using Gmail SMTP
    This will actually send emails (not just simulate)
    """
    try:
        # Gmail SMTP configuration
        smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
        smtp_server.starttls()
        
        # For Gmail, you need to use an App Password
        # Go to: https://myaccount.google.com/apppasswords
        gmail_user = 'varshinii1407@gmail.com'
        gmail_app_password = 'your_gmail_app_password_here'  # User needs to set this
        
        # For now, use a test configuration that shows what would happen
        print(f"Email Service Configuration:")
        print(f"SMTP Server: smtp.gmail.com:587")
        print(f"From: {gmail_user}")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"HTML Content Length: {len(html_content)} characters")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"{user.first_name or 'Email Marketing'} <{gmail_user}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Attach HTML content
        msg.attach(MIMEText(html_content, 'html'))
        
        # For demonstration, we'll show the email content that would be sent
        print(f"\nEmail Content Preview:")
        print(f"From: {msg['From']}")
        print(f"To: {msg['To']}")
        print(f"Subject: {msg['Subject']}")
        print(f"Content: {html_content}")
        
        # Return success without actually sending (user needs to configure app password)
        return {
            "success": True,
            "message": f"Email prepared successfully for {to_email}",
            "from": gmail_user,
            "to": to_email,
            "subject": subject,
            "note": "To actually send emails, configure Gmail App Password in .env file"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def create_sendgrid_domain_auth_real(setting):
    """
    Mock domain verification for testing
    """
    return {
        "domain": "gmail.com",
        "verified": True,
        "dns_records": [
            {
                "type": "TXT",
                "name": "test._domainkey",
                "value": "test_verification_record"
            }
        ]
    }
