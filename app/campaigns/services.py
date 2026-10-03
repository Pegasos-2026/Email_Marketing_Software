from django.utils import timezone
from django.conf import settings
from .models import Campaign,CampaignRecipient,EmailEvent,OpenTracking,ClickTracking,Contact,CampaignContent,EmailTemplate
from .analytics_service import AnalyticsService
from app.emails.services import send_email, validate_user_email_settings, find_sendgrid_suppressed_emails
from app.emails.deliverability import (
    is_public_site_url,
    is_transient_network_error,
    personalize_campaign_text,
    add_recipient_unique_marker,
    prepare_inbox_priority_message,
    resolve_campaign_reply_to,
)
from app.emails.warmup import apply_warmup_batch, daily_send_limit, get_warmup_status, is_warmup_enabled
import random
import time

GMAIL_DOMAINS = frozenset({'gmail.com', 'googlemail.com'})


def _recipient_send_delay(contact_email, base_delay):
    domain = (contact_email or '').split('@')[-1].strip().lower()
    delay = max(0.0, float(base_delay))
    if domain in GMAIL_DOMAINS:
        gmail_delay = float(getattr(settings, 'GMAIL_SEND_DELAY_SECONDS', 2))
        jitter = float(getattr(settings, 'GMAIL_SEND_DELAY_JITTER_SECONDS', 0))
        delay = max(delay, gmail_delay)
        if jitter > 0:
            delay += random.uniform(0, jitter)
    return delay


class CampaignService:
    def __init__(self):
        self.analytics_service=AnalyticsService()

    def create_campaign_with_recipients(self,user,data):
        template=None
        template_id=data.get('template_id')
        if template_id:
            try:
                template=EmailTemplate.objects.get(id=template_id,is_active=True)
                if template.user != user and not template.is_public:
                    raise ValueError("You do not have access to this template")
            except EmailTemplate.DoesNotExist:
                raise ValueError(f"Template {template_id} not found")

        campaign_data={
            'user':user,
            'name':data['name'],
            'template':template,
            'from_email':data.get('from_email',''),
            'from_name':data.get('from_name',''),
            'reply_to':data.get('reply_to',''),
            'scheduled_at':data.get('scheduled_at'),
            'inbox_priority':data.get('inbox_priority',True),
        }
        if template:
            campaign_data['subject']=data.get('subject',template.subject)
            campaign_data['preview_text']=data.get('preview_text',template.preview_text)
            html_content=data.get('html_content',template.html_content)
            plain_text_content=data.get('plain_text_content',template.plain_text_content)
        else:
            campaign_data['subject']=data['subject']
            campaign_data['preview_text']=data.get('preview_text','')
            html_content=data.get('html_content','')
            plain_text_content=data.get('plain_text_content','')

        if data.get('scheduled_at'):
            campaign_data['status']='scheduled'
        else:
            campaign_data['status']='draft'

        campaign=Campaign.objects.create(**campaign_data)
        CampaignContent.objects.create(
            campaign=campaign,
            html_content=html_content,
            plain_text_content=plain_text_content,
        )

        list_ids=data.get('list_ids',[])
        contact_ids=data.get('contact_ids',[])
        if list_ids:
            self.add_recipients_from_lists(campaign,list_ids)
        if contact_ids:
            self.add_recipients_from_contact_ids(campaign,contact_ids)
        if template:
            template.increment_usage()
        return campaign

    def add_recipients_from_contact_ids(self,campaign,contact_ids):
        contacts=Contact.objects.filter(
            id__in=contact_ids,
            user=campaign.user,
        ).distinct()
        recipients=[
            CampaignRecipient(campaign=campaign,contact=contact,status='pending')
            for contact in contacts
        ]
        CampaignRecipient.objects.bulk_create(recipients,ignore_conflicts=True)

    def add_recipients_from_lists(self,campaign,list_ids):
        contacts=Contact.objects.filter(
            lists__id__in=list_ids,
            lists__user=campaign.user,
            is_subscribed=True,
        ).distinct()
        recipients=[
            CampaignRecipient(campaign=campaign,contact=contact,status='pending')
            for contact in contacts
        ]
        CampaignRecipient.objects.bulk_create(recipients,ignore_conflicts=True)

    def assert_send_ready(self, campaign_id):
        """Validate campaign can be sent; raise ValueError when not ready."""
        campaign = Campaign.objects.get(id=campaign_id)
        pending_recipients = campaign.recipients.filter(status__in=['pending', 'failed'])
        if campaign.status == 'sent' and not pending_recipients.exists():
            raise ValueError('Campaign already sent')
        if campaign.status == 'sending' and not pending_recipients.exists():
            campaign.status = 'sent'
            campaign.save(update_fields=['status'])
            raise ValueError('Campaign already sent')
        if not hasattr(campaign, 'content'):
            raise ValueError('Campaign content not found')
        if not campaign.recipients.exists():
            raise ValueError('No recipients added to campaign')

        settings_error = validate_user_email_settings(
            campaign.user,
            require_verified_domain=True,
            from_email=campaign.from_email,
        )
        if settings_error:
            raise ValueError(settings_error)

        inbox_priority = getattr(campaign, 'inbox_priority', True)
        recipient_list = list(
            CampaignRecipient.objects.filter(
                campaign=campaign,
                status__in=['pending', 'failed'],
            ).select_related('contact')
        )
        if not recipient_list:
            raise ValueError('No recipients found for this campaign')

        recipient_list, _warmup_meta = apply_warmup_batch(
            recipient_list,
            campaign.user,
            inbox_priority=inbox_priority,
        )
        if not recipient_list:
            limit = daily_send_limit()
            raise ValueError(
                f'Daily inbox warm-up limit reached ({limit} emails sent today). '
                'Continue tomorrow — open this campaign and click Send again.'
            )
        return len(recipient_list)

    def send_campaign(self,campaign_id):
        """Send campaign emails with daily warm-up batching for inbox priority campaigns."""
        campaign=Campaign.objects.get(id=campaign_id)
        pending_recipients=campaign.recipients.filter(status__in=['pending', 'failed'])
        if campaign.status == 'sent' and not pending_recipients.exists():
            raise ValueError("Campaign already sent")
        if campaign.status == 'sending' and not pending_recipients.exists():
            campaign.status='sent'
            campaign.save()
            raise ValueError("Campaign already sent")

        settings_error=validate_user_email_settings(
            campaign.user,
            require_verified_domain=True,
            from_email=campaign.from_email,
        )
        if settings_error:
            raise ValueError(settings_error)

        self.analytics_service.initialize_campaign_analytics(campaign_id)
        campaign.status='sending'
        campaign.save()

        recipients=CampaignRecipient.objects.filter(
            campaign=campaign,
            status__in=['pending', 'failed'],
        ).select_related('contact')
        if not recipients.exists():
            campaign.status='draft'
            campaign.save()
            raise ValueError("No recipients found for this campaign")

        success_count=0
        failed_count=0
        failure_details=[]
        sent_emails=[]
        BATCH_SIZE=100
        recipient_list=list(recipients)
        warmup_meta=None
        inbox_priority=getattr(campaign, 'inbox_priority', True)
        recipient_list, warmup_meta=apply_warmup_batch(
            recipient_list,
            campaign.user,
            inbox_priority=inbox_priority,
        )
        if not recipient_list:
            limit=daily_send_limit()
            raise ValueError(
                f"Daily inbox warm-up limit reached ({limit} emails sent today). "
                "Continue tomorrow — open this campaign and click Send again."
            )

        send_delay=max(0.0, float(getattr(settings, 'CAMPAIGN_SEND_DELAY_SECONDS', 3.0)))
        suppressed_emails={}
        suppression_warnings=[]
        try:
            email_setting=campaign.user.emailsetting
            if (email_setting.provider or '').strip().lower()=='sendgrid':
                suppressed_emails=find_sendgrid_suppressed_emails(
                    email_setting,
                    [recipient.contact.email for recipient in recipient_list],
                )
        except Exception:
            suppressed_emails={}

        for i in range(0,len(recipient_list),BATCH_SIZE):
            batch=recipient_list[i:i+BATCH_SIZE]
            for index, recipient in enumerate(batch):
                try:
                    contact=recipient.contact
                    suppressed_reason=suppressed_emails.get((contact.email or '').strip().lower())
                    if suppressed_reason:
                        suppression_warnings.append({
                            'email': contact.email,
                            'warning': (
                                f"Address was {suppressed_reason}; Pegasos attempted delivery anyway."
                            ),
                        })
                    open_tracking, _created=OpenTracking.objects.get_or_create(
                        campaign_recipient=recipient,
                    )
                    is_sent=False
                    for attempt in range(3):
                        is_sent=self._send_email_with_tracking(
                            campaign,
                            recipient,
                            open_tracking,
                            bypass_list_management=True,
                        )
                        if is_sent:
                            break
                        error_text=recipient.error_message or ''
                        if attempt < 2 and is_transient_network_error(error_text):
                            time.sleep(min(2 ** (attempt + 1), 8))
                            continue
                        break
                    if is_sent:
                        recipient.status='sent'
                        recipient.sent_at=timezone.now()
                        recipient.error_message=''
                        recipient.save()
                        EmailEvent.objects.create(
                            campaign_recipient=recipient,
                            event_type='sent',
                            timestamp=timezone.now(),
                        )
                        success_count +=1
                        sent_emails.append(contact.email)
                    else:
                        recipient.status='failed'
                        recipient.save()
                        EmailEvent.objects.create(
                            campaign_recipient=recipient,
                            event_type='failed',
                            timestamp=timezone.now(),
                        )
                        failed_count +=1
                        failure_details.append({
                            'email': contact.email,
                            'error': recipient.error_message or 'Email send failed',
                        })
                except Exception as exc:
                    recipient.status='failed'
                    recipient.error_message=str(exc)
                    recipient.save()
                    EmailEvent.objects.create(
                        campaign_recipient=recipient,
                        event_type='failed',
                        timestamp=timezone.now(),
                    )
                    failed_count +=1
                    failure_details.append({
                        'email': recipient.contact.email,
                        'error': str(exc),
                    })

                global_index=(i + index + 1)
                if global_index < len(recipient_list):
                    delay = _recipient_send_delay(contact.email, send_delay)
                    if delay > 0:
                        time.sleep(delay)

            if i + BATCH_SIZE < len(recipient_list):
                time.sleep(1)

        pending_remaining=CampaignRecipient.objects.filter(
            campaign=campaign,
            status='pending',
        ).count()
        if pending_remaining > 0:
            campaign.status='sending'
            if not campaign.sent_at and success_count > 0:
                campaign.sent_at=timezone.now()
        elif success_count > 0:
            campaign.status='sent'
            campaign.sent_at=timezone.now()
        else:
            campaign.status='draft'
            campaign.sent_at=None
        campaign.save()
        self.analytics_service.update_campaign_analytics(campaign_id)

        result={
            'total': success_count + failed_count,
            'success': success_count,
            'failed': failed_count,
            'failures': failure_details[:20],
            'sent_emails': sent_emails[:50],
            'suppression_warnings': suppression_warnings[:20],
            'pending_remaining': pending_remaining,
            'warmup': get_warmup_status(campaign.user),
        }
        if warmup_meta:
            result['warmup'].update(warmup_meta)
        if success_count == 0:
            result['message'] = (
                failure_details[0]['error']
                if failure_details
                else 'No emails were delivered. Check your email settings and try again.'
            )
        elif pending_remaining > 0 and is_warmup_enabled():
            deferred=warmup_meta.get('deferred', pending_remaining) if warmup_meta else pending_remaining
            result['message'] = (
                f"Sent {success_count} email(s) today. {deferred} recipient(s) remaining — "
                f"click Send again tomorrow (max {daily_send_limit()} per day for inbox warm-up)."
            )
        elif pending_remaining > 0:
            result['message'] = (
                f"Campaign partially sent: {success_count} delivered, {pending_remaining} still pending."
            )
        elif failed_count > 0:
            result['message'] = (
                f"Campaign partially sent: {success_count} delivered, {failed_count} failed."
            )
        else:
            result['message'] = f"Campaign sent successfully to {success_count} recipient(s)."

        if success_count > 0:
            if is_warmup_enabled():
                result['deliverability_note'] = (
                    "Inbox warm-up sends up to "
                    f"{daily_send_limit()} plain text-only emails per day to improve Gmail Primary placement. "
                    "Gmail may still filter new senders to All Mail until recipients add you to Contacts and reply once."
                )
            else:
                result['deliverability_note'] = (
                    "Inbox Priority sends as personal plain-text email (best for Gmail Primary). "
                    "Recipients may see plain layout, not HTML design. "
                    f"Gmail spacing: {getattr(settings, 'GMAIL_SEND_DELAY_SECONDS', 5)}s + jitter between Gmail addresses. "
                    "Primary inbox is not guaranteed for every recipient — ask contacts to move one message to Primary and add you to Contacts."
                )

        return result
    def _send_email_with_tracking(self, campaign, recipient, open_tracking, bypass_list_management=False):
            """Send email with optional tracking; inbox priority sends personal plain-style mail."""
            try:
                contact=recipient.contact
                content=campaign.content
                inbox_priority=getattr(campaign, 'inbox_priority', True)
                site_url = settings.SITE_URL.rstrip('/')
                use_tracking = is_public_site_url(site_url)
                plain_text_only = inbox_priority and not use_tracking and getattr(
                    settings, 'INBOX_PRIORITY_PLAIN_ONLY', True
                )
                differentiate_min = getattr(settings, 'INBOX_DIFFERENTIATE_MIN_RECIPIENTS', 50)

                if inbox_priority:
                    differentiate = campaign.recipients.count() >= differentiate_min
                    subject, plain_text, html_content = prepare_inbox_priority_message(
                        content.html_content,
                        content.plain_text_content,
                        contact.name,
                        contact.email,
                        campaign.from_name,
                        campaign.subject,
                        recipient.id,
                        differentiate_recipients=differentiate,
                        include_html_alternative=not plain_text_only,
                    )
                    unsubscribe_url = (
                        f"{site_url}/api/campaigns/unsubscribe/{recipient.id}/" if use_tracking else None
                    )
                    send_inbox_friendly = True
                else:
                    html_content = personalize_campaign_text(
                        content.html_content,
                        contact.name,
                        contact.email,
                        recipient.id,
                    )
                    subject = personalize_campaign_text(
                        campaign.subject,
                        contact.name,
                        contact.email,
                        recipient.id,
                    )
                    html_content = add_recipient_unique_marker(html_content, recipient.id, contact.email)
                    plain_text = (content.plain_text_content or '').strip()
                    if plain_text:
                        plain_text = personalize_campaign_text(
                            plain_text,
                            contact.name,
                            contact.email,
                            recipient.id,
                        )
                    unsubscribe_url = (
                        f"{site_url}/api/campaigns/unsubscribe/{recipient.id}/" if use_tracking else None
                    )
                    send_inbox_friendly = False

                if use_tracking:
                    html_content = self._add_click_tracking(html_content, campaign, recipient, site_url)
                    tracking_pixel_url = f"{site_url}/track/open/{open_tracking.tracking_id}/"
                    tracking_pixel = (
                        f'<img src="{tracking_pixel_url}" width="1" height="1" alt="" style="display:none;"/>'
                    )
                    import re as _re
                    body_close_pattern = _re.compile(r'</body>', _re.IGNORECASE)
                    if body_close_pattern.search(html_content):
                        html_content = body_close_pattern.sub(f'{tracking_pixel}</body>', html_content, count=1)
                    else:
                        html_content += tracking_pixel

                result=send_email(
                    campaign.user,
                    contact.email,
                    subject,
                    html_content,
                    from_email=campaign.from_email,
                    from_name=campaign.from_name,
                    reply_to=resolve_campaign_reply_to(
                        campaign.from_email,
                        campaign.reply_to,
                    ),
                    plain_text_content=plain_text or None,
                    unsubscribe_url=unsubscribe_url,
                    preview_text=campaign.preview_text if not inbox_priority else None,
                    bypass_list_management=bypass_list_management if inbox_priority else True,
                    inbox_friendly=send_inbox_friendly if inbox_priority else False,
                    plain_text_only=plain_text_only,
                    custom_args={
                        'campaign_recipient_id': recipient.id,
                        'campaign_id': campaign.id,
                    },
                )
                if result.get('success'):
                    return True
                raise Exception(result.get('error','Email send failed'))
            except Exception as e:
                recipient.status='failed'
                recipient.error_message=str(e)
                recipient.save()
                return False
    def _add_click_tracking(self, html_content, campaign, recipient, site_url=None):
        """Replace URLS with tracking URLs."""
        import re
        import hashlib

        site_url = (site_url or settings.SITE_URL).rstrip('/')
        pattern = r'href=(?P<quote>["\'])(?P<url>http[^"\']+)(?P=quote)'

        def replace_link(match):
            url = match.group('url')
            quote = match.group('quote')
            short_code = hashlib.md5(f"{campaign.id}-{url}".encode()).hexdigest()[:10]
            click_tracking, _created = ClickTracking.objects.get_or_create(
                campaign=campaign,
                original_url=url,
                defaults={'short_code': short_code},
            )
            tracking_url = f"{site_url}/track/click/{click_tracking.short_code}/{recipient.id}/"
            return f'href={quote}{tracking_url}{quote}'

        return re.sub(pattern, replace_link, html_content)
