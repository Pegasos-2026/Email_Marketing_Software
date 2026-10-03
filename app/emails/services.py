import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    BypassListManagement,
    ClickTracking,
    Content,
    Header,
    Mail,
    MailSettings,
    OpenTracking,
    SandBoxMode,
    SubscriptionTracking,
    TrackingSettings,
)
import requests

from .deliverability import apply_inbox_friendly_format, format_list_unsubscribe, normalize_email_html, is_prepared_campaign_html, is_transient_network_error


def _html_to_plain_text(html_content):
    if not html_content:
        return ''
    text = re.sub(r'(?is)<(script|style).*?>.*?</\1>', '', html_content)
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)</p\s*>', '\n\n', text)
    text = re.sub(r'(?s)<.*?>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _configure_sendgrid_tracking(message):
    """Use Pegasos tracking when configured; disable SendGrid link/pixel rewrites."""
    tracking = TrackingSettings()
    tracking.click_tracking = ClickTracking(enable=False, enable_text=False)
    tracking.open_tracking = OpenTracking(enable=False)
    tracking.subscription_tracking = SubscriptionTracking(enable=False)
    message.tracking_settings = tracking


def _configure_sendgrid_mail_settings(message, bypass_list_management=False):
    """Ensure sandbox mode is off and optionally bypass SendGrid suppression lists."""
    mail_settings = MailSettings()
    mail_settings.sandbox_mode = SandBoxMode(enable=False)
    if bypass_list_management:
        mail_settings.bypass_list_management = BypassListManagement(enable=True)
    message.mail_settings = mail_settings


def _extract_sendgrid_message_id(response):
    headers = getattr(response, "headers", None) or {}
    if hasattr(headers, "get"):
        return headers.get("X-Message-Id") or headers.get("x-message-id")
    return None


def find_sendgrid_suppressed_emails(setting, emails):
    """
    Return {email: reason} for addresses on SendGrid suppression lists.
    These addresses will not receive mail unless list management is bypassed.
    """
    api_key = setting.get_api_key()
    if not api_key:
        return {}

    targets = {(email or "").strip().lower() for email in emails if email}
    if not targets:
        return {}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    suppressed = {}
    endpoints = [
        ("https://api.sendgrid.com/v3/suppression/bounces", "on SendGrid bounce list"),
        ("https://api.sendgrid.com/v3/suppression/blocks", "on SendGrid block list"),
        ("https://api.sendgrid.com/v3/suppression/invalid_emails", "marked invalid by SendGrid"),
        ("https://api.sendgrid.com/v3/suppression/spam_reports", "on SendGrid spam report list"),
        ("https://api.sendgrid.com/v3/suppression/unsubscribes", "unsubscribed in SendGrid"),
    ]

    for url, reason in endpoints:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                continue
            payload = response.json() or []
            if isinstance(payload, dict):
                payload = payload.get("results", [])
            for entry in payload:
                email = (entry.get("email") or "").strip().lower()
                if email in targets and email not in suppressed:
                    suppressed[email] = reason
        except Exception:
            continue

    return suppressed


def _resolve_sender_identity(setting, from_email=None, from_name=None):
    sender_email = (from_email or setting.from_email or setting.smtp_user or "").strip()
    sender_name = from_name if from_name is not None else (setting.from_name or "")
    if not str(sender_name).strip():
        sender_name = "Pegasos"
    return sender_email, sender_name


def validate_user_email_settings(user, require_verified_domain=False, from_email=None):
    """Return None if settings are ready to send, otherwise an error message."""
    try:
        setting = user.emailsetting
    except Exception:
        return (
            "Email settings are not configured. Open Settings, enter your SMTP credentials, "
            "and click Save email settings before sending campaigns."
        )

    provider = (setting.provider or "SMTP").strip().lower()
    if provider == "sendgrid":
        if not setting.get_api_key():
            return "SendGrid API key is not configured in Settings."
        if require_verified_domain and not sendgrid_is_ready_to_send(setting, from_email=from_email):
            return (
                "Sender is not verified in SendGrid. Verify your From email under "
                "SendGrid → Sender Authentication → Single Sender, or complete domain DNS for pegasos.in, "
                "then click Check verification status in Pegasos Settings."
            )
        return None

    if provider == "smtp":
        if not setting.smtp_host or not setting.smtp_user:
            return "SMTP host and username are required in Settings."
        if not setting.smtp_password:
            return (
                "SMTP password is not saved. Enter your password in Settings and click "
                "Save email settings before sending campaigns."
            )
        return None

    return "Unsupported email provider configured in Settings."


def send_email(
    user,
    to_email,
    subject,
    html_content,
    is_test=False,
    from_email=None,
    from_name=None,
    reply_to=None,
    plain_text_content=None,
    unsubscribe_url=None,
    preview_text=None,
    bypass_list_management=False,
    inbox_friendly=False,
    custom_args=None,
    plain_text_only=False,
):
    try:
        setting = user.emailsetting
    except Exception:
        return {
            "success": False,
            "error": "Email settings not configured. Go to Settings, enter SMTP credentials, and click Save email settings.",
        }
    provider = (setting.provider or "SMTP").strip().lower()

    if provider == "sendgrid":
        return _send_email_sendgrid(
            setting,
            to_email,
            subject,
            html_content,
            is_test=is_test,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            plain_text_content=plain_text_content,
            unsubscribe_url=unsubscribe_url,
            preview_text=preview_text,
            bypass_list_management=bypass_list_management,
            inbox_friendly=inbox_friendly,
            custom_args=custom_args,
            plain_text_only=plain_text_only,
        )
    if provider == "smtp":
        return _send_email_smtp(
            setting,
            to_email,
            subject,
            html_content,
            from_email=from_email,
            from_name=from_name,
            reply_to=reply_to,
            plain_text_content=plain_text_content,
            unsubscribe_url=unsubscribe_url,
            plain_text_only=plain_text_only,
        )

    return {
        "success": False,
        "error": "Unsupported email provider. Please configure SMTP or SendGrid settings.",
    }


def _send_email_sendgrid(
    setting,
    to_email,
    subject,
    html_content,
    is_test=False,
    from_email=None,
    from_name=None,
    reply_to=None,
    plain_text_content=None,
    unsubscribe_url=None,
    preview_text=None,
    bypass_list_management=False,
    inbox_friendly=False,
    custom_args=None,
    plain_text_only=False,
):
    if not sendgrid_is_ready_to_send(setting, from_email=from_email, is_test=is_test):
        return {
            "success": False,
            "error": (
                "Sender is not verified in SendGrid. Verify your From email as a Single Sender, "
                "or complete domain authentication for pegasos.in."
            ),
        }

    api_key = setting.get_api_key()
    if not api_key:
        return {
            "success": False,
            "error": "SendGrid API key is not configured"
        }

    try:
        sg = SendGridAPIClient(api_key)
        sender_email, sender_name = _resolve_sender_identity(setting, from_email, from_name)
        if inbox_friendly:
            if is_prepared_campaign_html(html_content) and (plain_text_content or '').strip():
                plain_body = plain_text_content.strip()
            else:
                html_content, plain_text_content = apply_inbox_friendly_format(
                    html_content,
                    plain_text_content,
                    from_name=sender_name,
                )
                plain_body = plain_text_content or _html_to_plain_text(html_content)
        else:
            html_content = normalize_email_html(html_content)
            plain_body = plain_text_content or _html_to_plain_text(html_content)
        if unsubscribe_url and not inbox_friendly:
            plain_body = f"{plain_body}\n\nUnsubscribe: {unsubscribe_url}".strip()

        message = Mail(
            from_email=(sender_email, sender_name),
            to_emails=to_email,
            subject=subject,
        )
        message.add_content(Content('text/plain', plain_body or subject))
        if not plain_text_only:
            if inbox_friendly:
                if not is_prepared_campaign_html(html_content):
                    html_content = normalize_email_html(html_content or plain_body.replace('\n', '<br>'))
                message.add_content(Content('text/html', html_content))
            else:
                message.add_content(Content('text/html', html_content))

        reply_address = (reply_to or sender_email or "").strip()
        if inbox_friendly and plain_text_only:
            reply_address = sender_email
        if reply_address:
            message.reply_to = reply_address

        if preview_text and not inbox_friendly:
            message.add_header(Header('X-Preview-Text', preview_text))

        if not inbox_friendly:
            list_unsubscribe = format_list_unsubscribe(
                unsubscribe_url=unsubscribe_url,
                mailto_email=reply_address or sender_email,
            )
            if list_unsubscribe:
                message.add_header(Header('List-Unsubscribe', list_unsubscribe))
                if unsubscribe_url:
                    message.add_header(
                        Header('List-Unsubscribe-Post', 'List-Unsubscribe=One-Click')
                    )

        _configure_sendgrid_tracking(message)
        _configure_sendgrid_mail_settings(message, bypass_list_management=bypass_list_management)

        if custom_args:
            from sendgrid.helpers.mail import CustomArg
            for key, value in custom_args.items():
                if value is not None:
                    message.custom_arg = CustomArg(str(key), str(value))

        response = None
        last_error = None
        import time as _time
        for attempt in range(5):
            try:
                response = sg.send(message)
                break
            except Exception as exc:
                last_error = exc
                err = str(exc).lower()
                retryable = (
                    '429' in err
                    or is_transient_network_error(err)
                )
                if retryable and attempt < 4:
                    _time.sleep(min(2 ** attempt, 12))
                    continue
                raise

        return {
            "success": True,
            "message": f"Email sent successfully to {to_email}",
            "status_code": response.status_code if response else None,
            "message_id": _extract_sendgrid_message_id(response) if response else None,
        }
    except Exception as e:
        error_text = str(e)
        if '403' in error_text or 'Forbidden' in error_text:
            return {
                'success': False,
                'error': (
                    'SendGrid rejected the send (403). Verify your sender in SendGrid: '
                    'Settings → Sender Authentication → verify pegasos.in domain OR '
                    'Single Sender Verification for your From email. Also ensure your API key has Mail Send permission.'
                ),
            }
        return {
            'success': False,
            'error': error_text,
        }


def _send_email_smtp(
    setting,
    to_email,
    subject,
    html_content,
    from_email=None,
    from_name=None,
    reply_to=None,
    plain_text_content=None,
    unsubscribe_url=None,
    plain_text_only=False,
):
    if not setting.smtp_host or not setting.smtp_user:
        return {
            "success": False,
            "error": "SMTP host and username are required. Save your email settings before sending.",
        }
    if not setting.smtp_password:
        return {
            "success": False,
            "error": "SMTP password is not saved. Enter your password in Settings and click Save email settings.",
        }

    try:
        smtp_password = setting.get_smtp_password()
        if not smtp_password:
            return {
                "success": False,
                "error": "SMTP password could not be decrypted. Re-enter your password and save settings.",
            }

        from_address = from_email or setting.from_email or setting.smtp_user
        display_name = from_name if from_name is not None else (setting.from_name or "")
        if not str(display_name).strip():
            display_name = "Pegasos"
        plain_body = plain_text_content or _html_to_plain_text(html_content)
        if unsubscribe_url and not plain_text_only:
            plain_body = f"{plain_body}\n\nUnsubscribe: {unsubscribe_url}".strip()

        if plain_text_only:
            msg = MIMEText(plain_body or subject, "plain", "utf-8")
            msg["From"] = f"{display_name} <{from_address}>".strip() if display_name else from_address
            msg["To"] = to_email
            msg["Subject"] = subject
            reply_address = (reply_to or from_address or "").strip() or from_address
            msg["Reply-To"] = reply_address
            smtp_payload = msg.as_string()
        else:
            html_content = normalize_email_html(html_content)
            msg = MIMEMultipart('alternative')
            msg["From"] = f"{display_name} <{from_address}>".strip() if display_name else from_address
            msg["To"] = to_email
            msg["Subject"] = subject
            reply_address = (reply_to or from_address or "").strip()
            if reply_address:
                msg["Reply-To"] = reply_address
            list_unsubscribe = format_list_unsubscribe(
                unsubscribe_url=unsubscribe_url,
                mailto_email=reply_address or from_address,
            )
            if list_unsubscribe:
                msg["List-Unsubscribe"] = list_unsubscribe

            msg.attach(MIMEText(plain_body or subject, "plain", "utf-8"))
            msg.attach(MIMEText(html_content, "html", "utf-8"))
            smtp_payload = msg.as_string()

        port = int(setting.smtp_port or 587)
        if port == 465:
            smtp_server = smtplib.SMTP_SSL(setting.smtp_host, port, timeout=30)
        else:
            smtp_server = smtplib.SMTP(setting.smtp_host, port, timeout=30)
            smtp_server.starttls()

        smtp_server.login(setting.smtp_user, smtp_password)
        smtp_server.sendmail(from_address, [to_email], smtp_payload)
        smtp_server.quit()

        return {
            "success": True,
            "message": f"Email sent successfully to {to_email}",
        }
    except smtplib.SMTPAuthenticationError:
        return {
            "success": False,
            "error": "SMTP authentication failed. Check your username and password (use an app password for Gmail).",
        }
    except smtplib.SMTPException as e:
        return {
            "success": False,
            "error": f"SMTP error: {e}",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


SENDGRID_DOMAIN_AUTH_URL = "https://api.sendgrid.com/v3/whitelabel/domains"
SENDGRID_VERIFIED_SENDERS_URL = "https://api.sendgrid.com/v3/verified_senders"


def is_sendgrid_sender_verified(setting, sender_email):
    """Return True if the address is a verified Single Sender in SendGrid."""
    api_key = setting.get_api_key()
    if not api_key or not sender_email:
        return False

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = requests.get(SENDGRID_VERIFIED_SENDERS_URL, headers=headers, timeout=15)
    if response.status_code != 200:
        return False

    payload = response.json()
    senders = payload.get("results", payload) if isinstance(payload, dict) else payload
    if not isinstance(senders, list):
        return False

    target = sender_email.strip().lower()
    for sender in senders:
        email = (sender.get("from_email") or sender.get("email") or "").strip().lower()
        verified = bool(sender.get("verified"))
        status = (sender.get("verification_status") or "").strip().lower()
        if email == target and (verified or status == "verified"):
            return True
    return False


def sendgrid_is_ready_to_send(setting, from_email=None, is_test=False):
    if is_test:
        return True
    if setting.domain_verified:
        return True
    sender = (from_email or setting.from_email or "").strip()
    return bool(sender) and is_sendgrid_sender_verified(setting, sender)


def create_sendgrid_domain_auth(setting):
    """Create domain authentication in sendgrid
    Return DNS records for user
    """
    if (setting.provider or "").strip().lower() != "sendgrid":
        raise Exception("SendGrid domain authentication is only available for SendGrid provider")

    payload = {
        "domain": setting.sending_domain,
        "automatic_security": True,
        "custom_spf": True,
    }
    headers = {
        "Authorization": f"Bearer {setting.get_api_key()}",
        "Content-Type": "application/json"
    }
    response = requests.post(
        SENDGRID_DOMAIN_AUTH_URL, json=payload, headers=headers, timeout=10
    )
    if response.status_code not in (200, 201):
        raise Exception("Failed to create domain authentication")
    data = response.json()
    return {
        "domain_id": data.get("id"),
        "domain": data.get("domain"),
        "verified": data.get("valid"),
        "dns_records": data.get("dns")
    }


def check_domain_verification(setting, domain_id):
    if (setting.provider or "").strip().lower() != "sendgrid":
        raise Exception("SendGrid domain verification is only available for SendGrid provider")

    url = f"{SENDGRID_DOMAIN_AUTH_URL}/{domain_id}/validate"
    headers = {
        "Authorization": f"Bearer {setting.get_api_key()}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, timeout=10)
    if response.status_code not in (200, 201):
        raise Exception("Failed to validate domain with SendGrid")

    status_response = requests.get(
        f"{SENDGRID_DOMAIN_AUTH_URL}/{domain_id}",
        headers=headers,
        timeout=10,
    )
    if status_response.status_code != 200:
        raise Exception("Failed to check domain status")
    data = status_response.json()
    return bool(data.get("valid"))


def sync_sendgrid_domain_status(setting):
    """
    Look up the configured sending domain in SendGrid and sync verification status.
    Returns (verified: bool, message: str)
    """
    if (setting.provider or "").strip().lower() != "sendgrid":
        return False, "Switch provider to SendGrid to verify a domain."

    api_key = setting.get_api_key()
    if not api_key:
        return False, "SendGrid API key is not configured."

    domain_name = (setting.sending_domain or "").strip().lower()
    if not domain_name:
        return False, "Enter your sending domain (e.g. pegasos.in) and save settings."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = requests.get(SENDGRID_DOMAIN_AUTH_URL, headers=headers, timeout=15)
    if response.status_code != 200:
        return False, "Could not fetch domains from SendGrid. Check your API key permissions."

    domains = response.json() or []
    matched = None
    for entry in domains:
        if (entry.get("domain") or "").lower() == domain_name:
            matched = entry
            break

    if not matched:
        return (
            False,
            f"Domain '{domain_name}' was not found in SendGrid. Add it under Settings → Sender Authentication.",
        )

    domain_id = matched.get("id")
    setting.domain_id = str(domain_id) if domain_id is not None else None

    is_verified = bool(matched.get("valid"))
    if domain_id and not is_verified:
        try:
            is_verified = check_domain_verification(setting, domain_id)
        except Exception:
            is_verified = bool(matched.get("valid"))

    setting.domain_verified = is_verified
    setting.save(update_fields=["domain_id", "domain_verified"])

    if is_verified:
        return True, f"Domain '{domain_name}' is verified. You can send campaigns now."

    from_email = (setting.from_email or "").strip()
    if from_email and is_sendgrid_sender_verified(setting, from_email):
        setting.domain_verified = True
        setting.save(update_fields=["domain_verified"])
        return True, f"Single sender '{from_email}' is verified. You can send campaigns now."

    return (
        False,
        f"Domain '{domain_name}' is not verified yet. Add the DNS records SendGrid provided, wait up to 48 hours, then check again.",
    )
