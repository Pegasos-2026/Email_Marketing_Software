"""Service for bulk email sending to multiple contacts."""
import time

from django.conf import settings
from django.db import transaction

from app.emails.services import send_email, validate_user_email_settings

from .models import Contact, ContactList


class BulkEmailService:
    def __init__(self, user):
        self.user = user

    def _send_delay(self):
        return max(0.0, float(getattr(settings, 'CAMPAIGN_SEND_DELAY_SECONDS', 1.5)))

    def _sender_settings(self):
        try:
            setting = self.user.emailsetting
        except Exception as exc:
            raise ValueError('Email settings are not configured.') from exc
        return setting

    @transaction.atomic
    def send_to_contacts(self, contact_ids, subject, html_content, plain_text_content=None):
        settings_error = validate_user_email_settings(
            self.user,
            require_verified_domain=True,
        )
        if settings_error:
            raise ValueError(settings_error)

        contacts = list(
            Contact.objects.filter(
                user=self.user,
                id__in=contact_ids,
                is_subscribed=True,
            )
        )
        if not contacts:
            raise ValueError('No active contacts found to send to')

        setting = self._sender_settings()
        results = {
            'total': len(contacts),
            'sent': 0,
            'failed': 0,
            'errors': [],
            'deliverability_note': (
                'SendGrid accepted these messages for delivery. Ask recipients to check spam/junk folders.'
            ),
        }
        delay = self._send_delay()

        for index, contact in enumerate(contacts):
            try:
                result = send_email(
                    user=self.user,
                    to_email=contact.email,
                    subject=subject,
                    html_content=html_content,
                    from_email=setting.from_email,
                    from_name=setting.from_name,
                    reply_to=setting.from_email,
                    plain_text_content=plain_text_content,
                )
                if result.get('success'):
                    results['sent'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'email': contact.email,
                        'error': result.get('error', 'Unknown error'),
                    })
            except Exception as exc:
                results['failed'] += 1
                results['errors'].append({'email': contact.email, 'error': str(exc)})

            if delay and index + 1 < len(contacts):
                time.sleep(delay)

        return results

    @transaction.atomic
    def send_to_list(self, list_id, subject, html_content, plain_text_content=None):
        try:
            contact_list = ContactList.objects.get(id=list_id, user=self.user)
        except ContactList.DoesNotExist as exc:
            raise ValueError(f'Contact list {list_id} not found') from exc

        contact_ids = list(
            contact_list.contacts.filter(is_subscribed=True).values_list('id', flat=True),
        )
        return self.send_to_contacts(contact_ids, subject, html_content, plain_text_content)
