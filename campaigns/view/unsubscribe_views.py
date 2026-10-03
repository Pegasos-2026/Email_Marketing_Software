from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from campaigns.models import CampaignRecipient, EmailEvent
from campaigns.analytics_service import AnalyticsService


@csrf_exempt
def track_unsubscribe(request, recipient_id):
    """Public one-click unsubscribe link from campaign emails."""
    try:
        recipient = CampaignRecipient.objects.select_related(
            'contact', 'campaign'
        ).get(id=recipient_id)
        contact = recipient.contact
        if contact.is_subscribed:
            contact.is_subscribed = False
            contact.save(update_fields=['is_subscribed'])
            EmailEvent.objects.create(
                campaign_recipient=recipient,
                event_type='unsubscribed',
                timestamp=timezone.now(),
            )
            AnalyticsService().update_campaign_analytics(recipient.campaign_id)
        html = (
            '<!DOCTYPE html><html><body style="font-family:sans-serif;padding:2rem">'
            '<h1>Unsubscribed</h1><p>You have been removed from this mailing list.</p>'
            '</body></html>'
        )
        return HttpResponse(html, content_type='text/html')
    except CampaignRecipient.DoesNotExist:
        return HttpResponse('Invalid link.', status=404)
