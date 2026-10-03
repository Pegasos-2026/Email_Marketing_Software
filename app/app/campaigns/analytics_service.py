from django.db.models import Count,Q,Avg
from django.utils import timezone
from campaigns.models import(Campaign,CampaignAnalytics,EmailEvent,CampaignRecipient,ClickTracking,OpenTracking)
class AnalyticsService:
    def initialize_campaign_analytics(self,campaign_id):
        """Initialize analytics when campaign is sent"""
        campaign=Campaign.objects.get(id=campaign_id)
        analytics,created=CampaignAnalytics.objects.get_or_create(campaign=campaign)
        analytics.total_recipients=campaign.recipients.count()
        analytics.save()
        return analytics
    def update_campaign_analytics(self,campaign_id):
        """update campaign analytics based on events this should be called periodically or after events"""
        campaign=Campaign.objects.get(id=campaign_id)
        analytics,created=CampaignAnalytics.objects.get_or_create(campaign=campaign)
        recipients=CampaignRecipient.object.filter(campaign=campaign)
        #total recipients
        analytics.total_recipients=recipients.count()
        #sent count
        analytics.total_sent=recipients.filter(status='sent').count()
        #failed count
        analytics.total_failed=recipients.filter(status='failed').count()
        #delivered count(recipient with delivered event)
        delivered_recipients=recipients.filter(events__event_type='delivered').distinct()
        analytics.total_delivered=delivered_recipients.count()
        #open stats
        opened_recipients=recipients.filter(events__event_type='opened').distinct()
        analytics.unique_opens=opened_recipients.count()
        #total opens(can be multiple per recipient)
        analytics.total_opened=EmailEvent.objects.filter(campaign_recipient__campaign=campaign,event_type='opened').count()
        #click stats
        clicked_recipients=recipients.filter(events__vent_type='clicked').distinct()
        analytics.unique_clicks=clicked_recipients.count()
        #Total clicks
        analytics.total_clicked=EmailEvent.objects.filter(campaign_recipient__campaign=campaign,event_type='bounced').count()
        #spam reports
        analytics.total_spam_reports=EmailEvent.objects.filter(campaign_recipient__campaign=campaign,event_type='spam').count()
        #unsubscribes
        analytics.total_unsubscribes=EmailEvent.objects.filter(campaign_recipient__campaign=campaign,event_type='unsubscribed').count()
        #calculate rates
        analytics.calculate_rates()
        return analytics
    def get_campaign_stats(self,campaign_id):
        """Get formatted campaign statidtics"""
        campaign=Campaign.objects.get(id=campaign_id)
        #update analytics first
        analytics=self.update_campaign_analytics(campaign_id)
        return {
            'campaign':{
                'id':campaign.id,
                'name':campaign.name,
                'subject':campaign.subject,
                'status':campaign.status,
                'sent_at':campaign.sent_at,
                'created_at':campaign.created_at
            },
            'sending':{
                'total_recipients':analytics.total_recipients,
                'total_sent':analytics.total_sent,
                'total_delivered':analytics.total_delivered,
                'total_failed':analytics.total_failed,
                'delivery_rate':analytics.delivery_rate,
            },
            'engagement':{
                'total_opened':analytics.total_opened,
                'unique_opens':analytics.unique_opens,
                'open_rate':analytics.open_rate,
                'total_clicked':analytics.total_clicked,
                'unique_clicks':analytics.unique_clicks,
                'click_rate':analytics.click_rate,
                'click_to_open_rate':analytics.click_to_open_rate,
            },
            'negative':{
                'total_bounced':analytics.total_bounced,
                'bounce_rate':analytics.bounce_rate,
                'total_spam_reports':analytics.total_spam_reports,
                'total_unsubscribes':analytics.click_to_open_rate,
            },
            'timeline':self.get_event_timeline(campaign_id),
            'top_links':self.get_top_clicked_links(campaign_id),
        }
    def get_event_timeline(self,campaign_id,limit=20):
        """Get recent events timeline"""
        events=EmailEvent.objects.filter(campaign_recipient__campaign_id=campaign_id).select_related('campaign_recipient__contact').order_by('-timestamp')[:limit]
        return [{
            'event_type':event.event_type,
            'email':event.campaign_recipient.contact.email,
            'timestamp':event.timestamp.isoformat(),
            'clicked_url':event.clicked_url,
            'device_type':event.device_type,
        } for event in events]
    def get_top_clicked_links(self,campaign_id,limit=10):
        """Get most clicked links in campaign"""
        links=ClickTracking.objects.filter(campaign_id=campaign_id).order_by('-total_clicks')[:limit]
        return [{
            'url':link.original_url,
            'total_clicks':link.total_clicks,
            'unique_clicks':link.unique_clicks,
        }for link in links]
    def get_dashboard_overview(self,user):
        """Overall dashbaord stats for user"""
        campaigns=Campaign.objects.filter(user=user)
        total_campaigns=campaigns.count()
        sent_campaigns=campaigns.filter(status='sent').count()
        draft_campaigns=campaigns.filter(status='draft').count()
        scheduled_campaigns=campaigns.filter(status='scheduled').count()
        #aggregrate analytics
        all_analytics=CampaignAnalytics.objects.filter(campaign__user=user)
        total_sent=sum(a.total_sent for a in all_analytics)
        total_delivered=sum(a.total_delivered for a in all_analytics)
        total_opened=sum(a.unique_opens for a in all_analytics)
        total_clicked=sum(a.unique_clicks for a in all_analytics)
        #avgerage rates 
        avg_open_rate=0
        avg_click_rate=0
        avg_delivery_rate=0
        if sent_campaigns>0:
            avg_open_rate=all_analytics.aggregate(Avg('open_rate'))['open_rate__avg'] or 0
            avg_click_rate=all_analytics.aggregate(Avg('click_rate'))['click_rate__avg'] or 0
            avg_delivery_rate=all_analytics.aggregate(Avg('delivery_rate'))['delivery_rate__avg'] or 0
            return{
                'overview':{
                    'total_campaigns':total_campaigns,
                    'sent_campaigns':sent_campaigns,
                    'draft_campaigns':draft_campaigns,
                    'scheduled_campaigns':scheduled_campaigns,
                },
                'totals':{
                    'total_emails_sent':total_sent,
                    'total_delivered':total_delivered,
                    'total_opens':total_opened,
                    'total_clicks':total_clicked,
                },
                'averages':{
                    'avg_delivery_rate':round(avg_delivery_rate,2),
                    'avg_open_rate':round(avg_open_rate,2),
                    'avg_click_rate':round(avg_click_rate,2),
                },
                'recent_campaigns':self.get_recent_campaigns(user,limit=5),
                'top_performing':self.get_top_perfroming_campaigns(user,limit=5),
            }
    def get_recent_campaigns(self,user,limit=5):
        """Get recnet sent campaigns with basic stats"""
        campaigns=Campaign.objects.filter(user=user,status='sent').select_related('analytics').order_by('-sent_at')[:limit]
        result=[]
        for campaign in campaigns:
            try:
                analytics=campaign.analytics
                result.append({
                    'id':campaign.id,
                    'name':campaign.name,
                    'subject':campaign.subject,
                    'sent_at':campaign.sent_at.isoformat() if campaign.sent_at else None,
                    'total_sent':analytics.total_sent,
                    'open_rate':analytics.open_rate,
                    'click_rate':analytics.click_rate,
                })
            except CampaignAnalytics.DoesNotExist:
                pass
        return result
    def get_top_peforming_campaigns(self,user,limit=5):
        """Get top performing campaign by open rate"""
        campaigns=CampaignAnalytics.objects.filter(campaign__user=user,campaign__status='sent').select_related('campaign').order_by('-open_rate')[:limit]
        return [{
            'id':analytics.campaign.id,
            'name':analytics.campaign.name,
            'open_rate':analytics.open_rate,
            'click_rate':analytics.click_rate,
            'total_sent':analytics.total_sent,
            }for analytics in campaigns]
    def get_hourly_opens(self,campaign_id):
        """Get hourly open distribution Useful for finding best send time"""
        from django.db.models.functions import TruncHour
        events=EmailEvent.objects.filter(campaign_recipient__campaign_id=campaign_id,event_type='opened').annotate(hour=TruncHour('timestamp')).values('hour').annotate(
            count=Count('id')
        ).order_by('hour')
        return list(events)
    def get_device_breakdown(self,campaign_id):
        """Get device type breakdown"""
        events=EmailEvent.objects.filter(campaign_recipient__campaign_id=campaign_id,event_type='opened',device_type__isnull=False).values('device_type').annotate(count=Count('id')).order_by('-count')
        return list(events)