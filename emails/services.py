from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email
import requests

def send_email(
    user,
    to_email,
    subject,
    html_content,
    plain_text_content=None,
    from_email=None,
    from_name=None,
    reply_to=None,
):
    setting = None
    api_key = None
    try:
        setting = user.emailsetting
    except Exception:
        setting = None

    if setting:
        if not setting.domain_verified:
            return {
                "success": False,
                "error": "Domain not verified"
            }
        api_key = setting.get_api_key()
    else:
        api_key = getattr(settings, "SENDGRID_API_KEY", None)
        if not api_key:
            return {
                "success": False,
                "error": "Email settings are not configured for this user. Please configure an EmailSetting or set SENDGRID_API_KEY."
            }

    from_email = from_email or (setting.from_email if setting else None)
    from_name = from_name or (setting.from_name if setting else None) or user.get_full_name() or user.username

    if not from_email:
        return {
            "success": False,
            "error": "From email is required to send this email."
        }

    sg = SendGridAPIClient(api_key)

    message = Mail(
        from_email=(from_email, from_name),
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
    )
    if plain_text_content is not None:
        message.plain_text_content = plain_text_content
    if reply_to:
        message.reply_to = Email(reply_to)

    try:
        response = sg.send(message)
        status_code = getattr(response, 'status_code', None)
        if status_code in (200, 202):
            return {
                "success": True,
                "status_code": status_code,
                "message": f"Email sent successfully to {to_email}",
            }
        return {
            "success": False,
            "error": f"SendGrid failed with status code {status_code}",
            "status_code": status_code,
            "response_body": getattr(response, 'body', None),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


SENDGRID_DOMAIN_AUTH_URL = "https://api.sendgrid.com/v3/whitelabel/domains"
def create_sendgrid_domain_auth(setting):
    """Create domain authentication in sendgrid
    Return DNS records for user
    """
    payload={
        "domain":setting.sending_domain,
        "automatic_security":True,
        "custom_spf":True,
    }
    headers={
        "Authorization":f"Bearer {setting.get_api_key()}",
        "Content-Type":"application/json"
    }
    response=requests.post(
        SENDGRID_DOMAIN_AUTH_URL,json=payload,headers=headers,timeout=10
    )
    if response.status_code not in (200,201):
        raise Exception("Failed to create domain authentucation")
    data=response.json()
    return{
        "domain_id":data.get("id"),
        "domain":data.get("domain"),
        "verified":data.get("valid"),
        "dns_records":data.get("dns")
    }