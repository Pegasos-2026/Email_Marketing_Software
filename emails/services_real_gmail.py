import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from django.conf import settings

def send_email_real_gmail(user, to_email, subject, html_content):
    """
    Real SMTP email sending function.
    Uses Gmail defaults by default, but can be configured with SMTP_* environment variables.
    """
    try:
        # Get SMTP credentials from environment or use Gmail defaults
        smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_user = os.getenv('SMTP_USER', os.getenv('GMAIL_USER', 'varshinii1407@gmail.com'))
        smtp_password = os.getenv('SMTP_PASSWORD', os.getenv('GMAIL_APP_PASSWORD', ''))
        
        if not smtp_password:
            return {
                "success": False,
                "error": "SMTP password not configured. Please set SMTP_PASSWORD or GMAIL_APP_PASSWORD in environment."
            }
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = f"{user.first_name or 'Email Marketing'} <{smtp_user}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_content, 'html'))
        
        # Connect to SMTP server
        smtp_server = smtplib.SMTP(smtp_host, smtp_port)
        smtp_server.starttls()
        smtp_server.login(smtp_user, smtp_password)
        
        # Send email
        text = msg.as_string()
        smtp_server.sendmail(smtp_user, to_email, text)
        smtp_server.quit()
        
        print(f"Email sent successfully via Gmail SMTP:")
        print(f"From: {smtp_user}")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        
        return {
            "success": True,
            "message": f"Email sent successfully to {to_email}",
            "from": smtp_user,
            "to": to_email,
            "subject": subject
        }
        
    except Exception as e:
        print(f"Gmail SMTP Error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def create_sendgrid_domain_auth_gmail(setting):
    """
    Mock domain verification for Gmail setup
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
