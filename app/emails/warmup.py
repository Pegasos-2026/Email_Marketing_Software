from django.conf import settings
from django.utils import timezone


def is_warmup_enabled():
    return getattr(settings, 'CAMPAIGN_WARMUP_ENABLED', True)


def daily_send_limit():
    return int(getattr(settings, 'DAILY_CAMPAIGN_SEND_LIMIT', 100))


def count_user_sends_today(user):
    from app.campaigns.models import CampaignRecipient

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return CampaignRecipient.objects.filter(
        campaign__user=user,
        status='sent',
        sent_at__gte=today_start,
    ).count()


def remaining_daily_sends(user):
    if not is_warmup_enabled():
        return None
    return max(0, daily_send_limit() - count_user_sends_today(user))


def get_warmup_status(user):
    limit = daily_send_limit()
    sent_today = count_user_sends_today(user)
    remaining = max(0, limit - sent_today)
    return {
        'enabled': is_warmup_enabled(),
        'daily_limit': limit,
        'sent_today': sent_today,
        'remaining_today': remaining,
    }


def apply_warmup_batch(recipients, user, inbox_priority=True):
    """
    Limit how many recipients are sent in one run when warm-up is enabled.
    Returns (batch, warmup_meta). warmup_meta is None when the full list is sent.
    """
    if not inbox_priority or not is_warmup_enabled():
        return recipients, None

    remaining = remaining_daily_sends(user)
    if remaining <= 0:
        return [], {
            'limited': True,
            'daily_limit': daily_send_limit(),
            'sent_today': count_user_sends_today(user),
            'batch_size': 0,
            'deferred': len(recipients),
        }

    if len(recipients) <= remaining:
        return recipients, None

    deferred = len(recipients) - remaining
    return recipients[:remaining], {
        'limited': True,
        'daily_limit': daily_send_limit(),
        'sent_today': count_user_sends_today(user),
        'batch_size': remaining,
        'deferred': deferred,
    }
