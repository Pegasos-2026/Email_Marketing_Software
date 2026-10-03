from django.db.models import Count, Q, Avg
from django.utils import timezone
from app.campaigns.models import (
    Campaign,
    CampaignAnalytics,
    EmailEvent,
    CampaignRecipient,
    ClickTracking,
    OpenTracking,
)


class AnalyticsService:
    def refresh_user_campaign_analytics(self, user):
        """Recompute analytics for every campaign owned by the user."""
        campaign_ids = Campaign.objects.filter(user=user).values_list('id', flat=True)
        for campaign_id in campaign_ids:
            self.update_campaign_analytics(campaign_id)

    def initialize_campaign_analytics(self, campaign_id):
        """Initialize analytics when campaign is sent"""
        campaign = Campaign.objects.get(id=campaign_id)
        analytics, created = CampaignAnalytics.objects.get_or_create(campaign=campaign)
        analytics.total_recipients = campaign.recipients.count()
        analytics.save()
        return analytics

    def update_campaign_analytics(self, campaign_id):
        """Update campaign analytics based on events."""
        campaign = Campaign.objects.get(id=campaign_id)
        analytics, created = CampaignAnalytics.objects.get_or_create(campaign=campaign)
        recipients = CampaignRecipient.objects.filter(campaign=campaign)
        analytics.total_recipients = recipients.count()
        analytics.total_sent = recipients.filter(status='sent').count()
        analytics.total_failed = recipients.filter(status='failed').count()
        delivered_recipients = recipients.filter(
            Q(events__event_type='delivered') | Q(status='sent')
        ).distinct()
        analytics.total_delivered = delivered_recipients.count()
        analytics.total_bounced = recipients.filter(
            events__event_type='bounced'
        ).distinct().count()
        opened_recipients = recipients.filter(events__event_type='opened').distinct()
        analytics.unique_opens = opened_recipients.count()
        analytics.total_opened = EmailEvent.objects.filter(
            campaign_recipient__campaign=campaign, event_type='opened'
        ).count()
        clicked_recipients = recipients.filter(events__event_type='clicked').distinct()
        analytics.unique_clicks = clicked_recipients.count()
        analytics.total_clicked = EmailEvent.objects.filter(
            campaign_recipient__campaign=campaign, event_type='clicked'
        ).count()
        analytics.total_spam_reports = EmailEvent.objects.filter(
            campaign_recipient__campaign=campaign, event_type='spam'
        ).count()
        analytics.total_unsubscribes = EmailEvent.objects.filter(
            campaign_recipient__campaign=campaign, event_type='unsubscribed'
        ).count()
        analytics.calculate_rates()
        return analytics

    def get_campaign_charts(self, campaign_id, analytics=None):
        """Chart-ready series for live dashboard widgets."""
        if analytics is None:
            analytics = self.update_campaign_analytics(campaign_id)
        funnel = [
            {'label': 'Recipients', 'value': analytics.total_recipients},
            {'label': 'Sent', 'value': analytics.total_sent},
            {'label': 'Delivered', 'value': analytics.total_delivered},
            {'label': 'Opens', 'value': analytics.unique_opens},
            {'label': 'Clicks', 'value': analytics.unique_clicks},
        ]
        breakdown = [
            {'label': 'Opened', 'value': analytics.unique_opens, 'color': '#0a2540'},
            {'label': 'Clicked', 'value': analytics.unique_clicks, 'color': '#0d3254'},
            {'label': 'Bounced', 'value': analytics.total_bounced, 'color': '#dc2626'},
            {'label': 'Unsubscribed', 'value': analytics.total_unsubscribes, 'color': '#d97706'},
            {'label': 'Spam', 'value': analytics.total_spam_reports, 'color': '#64748b'},
        ]
        hourly = self.get_hourly_opens(campaign_id)
        hourly_series = []
        for row in hourly:
            hour = row.get('hour')
            if hour:
                hourly_series.append({
                    'label': hour.strftime('%H:%M') if hasattr(hour, 'strftime') else str(hour)[11:16],
                    'value': row.get('count', 0),
                })
        return {
            'funnel': funnel,
            'engagement_breakdown': breakdown,
            'hourly_opens': hourly_series[:12],
            'rates': {
                'delivery_rate': analytics.delivery_rate,
                'open_rate': analytics.open_rate,
                'click_rate': analytics.click_rate,
                'bounce_rate': analytics.bounce_rate,
                'click_to_open_rate': analytics.click_to_open_rate,
            },
        }

    def get_dashboard_charts(self, user):
        """Account-wide chart data."""
        self.refresh_user_campaign_analytics(user)
        campaigns = Campaign.objects.filter(user=user)
        all_analytics = CampaignAnalytics.objects.filter(campaign__user=user)
        total_sent = sum(a.total_sent for a in all_analytics)
        total_delivered = sum(a.total_delivered for a in all_analytics)
        total_opened = sum(a.unique_opens for a in all_analytics)
        total_clicked = sum(a.unique_clicks for a in all_analytics)
        total_bounced = sum(a.total_bounced for a in all_analytics)
        total_unsubscribes = sum(a.total_unsubscribes for a in all_analytics)
        funnel = [
            {'label': 'Sent', 'value': total_sent},
            {'label': 'Delivered', 'value': total_delivered},
            {'label': 'Opens', 'value': total_opened},
            {'label': 'Clicks', 'value': total_clicked},
        ]
        breakdown = [
            {'label': 'Opens', 'value': total_opened, 'color': '#0a2540'},
            {'label': 'Clicks', 'value': total_clicked, 'color': '#0d3254'},
            {'label': 'Bounces', 'value': total_bounced, 'color': '#dc2626'},
            {'label': 'Unsubscribes', 'value': total_unsubscribes, 'color': '#d97706'},
        ]
        status_counts = []
        for status, label in [
            ('draft', 'Draft'),
            ('scheduled', 'Scheduled'),
            ('sending', 'Sending'),
            ('sent', 'Sent'),
        ]:
            status_counts.append({
                'label': label,
                'value': campaigns.filter(status=status).count(),
            })
        return {
            'funnel': funnel,
            'engagement_breakdown': breakdown,
            'campaign_status': status_counts,
        }

    def get_campaign_recipient_status(self, campaign_id, limit=500):
        """Per-recipient delivery and engagement status for live dashboard."""
        recipients = (
            CampaignRecipient.objects.filter(campaign_id=campaign_id)
            .select_related('contact')
            .prefetch_related('events')
            .order_by('-sent_at', 'contact__email')[:limit]
        )
        status_priority = [
            'bounced',
            'spam',
            'unsubscribed',
            'failed',
            'clicked',
            'opened',
            'delivered',
            'sent',
            'pending',
        ]
        result = []
        for recipient in recipients:
            event_types = {event.event_type for event in recipient.events.all()}
            if 'bounced' in event_types:
                delivery_status = 'bounced'
            elif 'spam' in event_types:
                delivery_status = 'spam'
            elif 'unsubscribed' in event_types:
                delivery_status = 'unsubscribed'
            elif recipient.status == 'failed' or 'failed' in event_types:
                delivery_status = 'failed'
            elif 'clicked' in event_types:
                delivery_status = 'clicked'
            elif 'opened' in event_types:
                delivery_status = 'opened'
            elif 'delivered' in event_types:
                delivery_status = 'delivered'
            elif recipient.status == 'sent':
                delivery_status = 'sent'
            else:
                delivery_status = 'pending'

            last_event = max(
                recipient.events.all(),
                key=lambda event: event.timestamp,
                default=None,
            )
            result.append({
                'id': recipient.id,
                'email': recipient.contact.email,
                'name': recipient.contact.name or '',
                'send_status': recipient.status,
                'delivery_status': delivery_status,
                'sent_at': recipient.sent_at.isoformat() if recipient.sent_at else None,
                'error_message': recipient.error_message or '',
                'opened': 'opened' in event_types,
                'clicked': 'clicked' in event_types,
                'bounced': 'bounced' in event_types,
                'spam_reported': 'spam' in event_types,
                'unsubscribed': 'unsubscribed' in event_types,
                'last_event_at': last_event.timestamp.isoformat() if last_event else None,
                'last_event_type': last_event.event_type if last_event else None,
            })
        result.sort(
            key=lambda row: (
                status_priority.index(row['delivery_status'])
                if row['delivery_status'] in status_priority
                else len(status_priority),
                row['email'],
            )
        )
        return result

    def get_campaign_stats(self, campaign_id):
        """Get formatted campaign statistics"""
        campaign = Campaign.objects.get(id=campaign_id)
        analytics = self.update_campaign_analytics(campaign_id)
        sent_at = campaign.sent_at.isoformat() if campaign.sent_at else None
        created_at = campaign.created_at.isoformat() if campaign.created_at else None
        return {
            'campaign': {
                'id': campaign.id,
                'name': campaign.name,
                'subject': campaign.subject,
                'status': campaign.status,
                'sent_at': sent_at,
                'created_at': created_at,
            },
            'last_updated': analytics.last_updated.isoformat() if analytics.last_updated else None,
            'sending': {
                'total_recipients': analytics.total_recipients,
                'total_sent': analytics.total_sent,
                'total_delivered': analytics.total_delivered,
                'total_failed': analytics.total_failed,
                'delivery_rate': analytics.delivery_rate,
            },
            'engagement': {
                'total_opened': analytics.total_opened,
                'unique_opens': analytics.unique_opens,
                'open_rate': analytics.open_rate,
                'total_clicked': analytics.total_clicked,
                'unique_clicks': analytics.unique_clicks,
                'click_rate': analytics.click_rate,
                'click_to_open_rate': analytics.click_to_open_rate,
            },
            'negative': {
                'total_bounced': analytics.total_bounced,
                'bounce_rate': analytics.bounce_rate,
                'total_spam_reports': analytics.total_spam_reports,
                'total_unsubscribes': analytics.total_unsubscribes,
            },
            'timeline': self.get_event_timeline(campaign_id, limit=50),
            'top_links': self.get_top_clicked_links(campaign_id),
            'recipients': self.get_campaign_recipient_status(campaign_id),
            'device_breakdown': self.get_device_breakdown(campaign_id),
            'charts': self.get_campaign_charts(campaign_id, analytics),
        }

    def get_event_timeline(self, campaign_id, limit=20):
        """Get recent events timeline"""
        events = EmailEvent.objects.filter(
            campaign_recipient__campaign_id=campaign_id
        ).select_related('campaign_recipient__contact').order_by('-timestamp')[:limit]
        return [{
            'event_type': event.event_type,
            'email': event.campaign_recipient.contact.email,
            'timestamp': event.timestamp.isoformat(),
            'clicked_url': event.clicked_url,
            'device_type': event.device_type,
        } for event in events]

    def get_top_clicked_links(self, campaign_id, limit=10):
        """Get most clicked links in campaign"""
        links = ClickTracking.objects.filter(campaign_id=campaign_id).order_by('-total_clicks')[:limit]
        return [{
            'url': link.original_url,
            'total_clicks': link.total_clicks,
            'unique_clicks': link.unique_clicks,
        } for link in links]

    def get_dashboard_overview(self, user):
        """Overall dashboard stats for user"""
        self.refresh_user_campaign_analytics(user)
        campaigns = Campaign.objects.filter(user=user)
        total_campaigns = campaigns.count()
        sent_campaigns = campaigns.filter(status='sent').count()
        draft_campaigns = campaigns.filter(status='draft').count()
        scheduled_campaigns = campaigns.filter(status='scheduled').count()
        all_analytics = CampaignAnalytics.objects.filter(campaign__user=user)
        total_sent = sum(a.total_sent for a in all_analytics)
        total_delivered = sum(a.total_delivered for a in all_analytics)
        total_failed = sum(a.total_failed for a in all_analytics)
        total_opened = sum(a.unique_opens for a in all_analytics)
        total_clicked = sum(a.unique_clicks for a in all_analytics)
        total_bounced = sum(a.total_bounced for a in all_analytics)
        total_spam_reports = sum(a.total_spam_reports for a in all_analytics)
        total_unsubscribes = sum(a.total_unsubscribes for a in all_analytics)
        total_pending = CampaignRecipient.objects.filter(
            campaign__user=user,
            status='pending',
        ).count()
        bounce_rate = round((total_bounced / total_sent) * 100, 2) if total_sent > 0 else 0
        avg_open_rate = all_analytics.aggregate(Avg('open_rate'))['open_rate__avg'] or 0
        avg_click_rate = all_analytics.aggregate(Avg('click_rate'))['click_rate__avg'] or 0
        avg_delivery_rate = all_analytics.aggregate(Avg('delivery_rate'))['delivery_rate__avg'] or 0
        avg_ctr = round((total_clicked / total_delivered) * 100, 2) if total_delivered > 0 else 0
        return {
            'last_updated': timezone.now().isoformat(),
            'overview': {
                'total_campaigns': total_campaigns,
                'sent_campaigns': sent_campaigns,
                'draft_campaigns': draft_campaigns,
                'scheduled_campaigns': scheduled_campaigns,
            },
            'totals': {
                'total_emails_sent': total_sent,
                'total_delivered': total_delivered,
                'total_failed': total_failed,
                'total_bounced': total_bounced,
                'total_opened': total_opened,
                'total_clicked': total_clicked,
                'total_spam_reports': total_spam_reports,
                'total_unsubscribes': total_unsubscribes,
                'total_pending': total_pending,
            },
            'rates': {
                'bounce_rate': bounce_rate,
                'delivery_rate': round(avg_delivery_rate, 2),
                'open_rate': round(avg_open_rate, 2),
                'click_rate': round(avg_click_rate, 2),
                'click_through_rate': avg_ctr,
            },
            'averages': {
                'avg_delivery_rate': round(avg_delivery_rate, 2),
                'avg_open_rate': round(avg_open_rate, 2),
                'avg_click_rate': round(avg_click_rate, 2),
            },
            'recent_campaigns': self.get_recent_campaigns(user, limit=5),
            'top_performing': self.get_top_peforming_campaigns(user, limit=5),
            'charts': self.get_dashboard_charts(user),
        }

    def get_recent_campaigns(self, user, limit=5):
        """Get recent sent campaigns with basic stats"""
        campaigns = Campaign.objects.filter(
            user=user, status='sent'
        ).select_related('analytics').order_by('-sent_at')[:limit]
        result = []
        for campaign in campaigns:
            try:
                analytics = campaign.analytics
                result.append({
                    'id': campaign.id,
                    'name': campaign.name,
                    'subject': campaign.subject,
                    'sent_at': campaign.sent_at.isoformat() if campaign.sent_at else None,
                    'total_sent': analytics.total_sent,
                    'open_rate': analytics.open_rate,
                    'click_rate': analytics.click_rate,
                })
            except CampaignAnalytics.DoesNotExist:
                pass
        return result

    def get_top_peforming_campaigns(self, user, limit=5):
        """Get top performing campaigns by open rate"""
        campaigns = CampaignAnalytics.objects.filter(
            campaign__user=user, campaign__status='sent'
        ).select_related('campaign').order_by('-open_rate')[:limit]
        return [{
            'id': analytics.campaign.id,
            'name': analytics.campaign.name,
            'open_rate': analytics.open_rate,
            'click_rate': analytics.click_rate,
            'total_sent': analytics.total_sent,
        } for analytics in campaigns]

    def get_hourly_opens(self, campaign_id):
        """Get hourly open distribution"""
        from django.db.models.functions import TruncHour
        events = EmailEvent.objects.filter(
            campaign_recipient__campaign_id=campaign_id,
            event_type='opened',
        ).annotate(hour=TruncHour('timestamp')).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        return list(events)

    def get_device_breakdown(self, campaign_id):
        """Get device type breakdown"""
        events = EmailEvent.objects.filter(
            campaign_recipient__campaign_id=campaign_id,
            event_type='opened',
            device_type__isnull=False,
        ).values('device_type').annotate(count=Count('id')).order_by('-count')
        return list(events)
