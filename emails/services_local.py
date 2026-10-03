import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from django.conf import settings

def send_email_local(user, to_email, subject, html_content):
    """
    Local email sending function for testing purposes
    Uses Python's built-in SMTP for testing without SendGrid
    """
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = user.email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Attach HTML content
        msg.attach(MIMEText(html_content, 'html'))
        
        # For testing, we'll simulate successful email sending
        # In production, you'd configure actual SMTP settings here
        
        print(f"Email prepared successfully:")
        print(f"From: {user.email}")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"HTML Content Length: {len(html_content)} characters")
        
        # Simulate successful send
        return {
            "success": True,
            "message": "Email sent successfully (local test mode)",
            "from": user.email,
            "to": to_email,
            "subject": subject
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def create_sendgrid_domain_auth(setting):
    """
    Mock domain verification for local testing
    """
    return {
        "domain": "localhost",
        "verified": True,
        "dns_records": [
            {
                "type": "TXT",
                "name": "test._domainkey",
                "value": "test_verification_record"
            }
        ]
    }
