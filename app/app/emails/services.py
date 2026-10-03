from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import requests
def send_email(user,to_email,subject,html_content):
    setting=user.emailsetting
    if not setting.domain_verified:
        return{
            "success":False,
            "error":"Domain not verified"
        }
    sg=SendGridAPIClient(setting.get_api_key())
    message=Mail(from_email=(setting.from_email,setting.from_name),
                 to_emails=to_email,subject=subject,html_content=html_content)
    response=sg.send(message)
    return response


SENDGRID_DOMAIN_AUTH_URL="https://api.sendgrid.com/v3/whitelabel/domains"
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
def check_domain_verification(setting,domain_id):
    url=f"https://api.sendgrid.com/v3/whitelabel/domains/{domain_id}"
    headers={"Authorization":f"Bearer {setting.get_api_key()}",
             "Content-Type":"application/json"
             }
    response=requests.get(url,headers=headers,timeout=10)
    if response.status_code!=200:
        raise Exception("Failed to check domain status")
    data=response.json()
    return data.get("valid")