from django.http import HttpResponse,HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from campaigns.models import OpenTracking,ClickTracking,EmailEvent,ClickEvent,CampaignRecipient
from campaigns.analytics_service import AnalyticsService
from django.utils import timezone
import logging
logger = logging.getLogger(__name__)

@csrf_exempt
def track_open(request,tracking_id):
    """Track email open via tracking pixel Returns 1x1 transparent GIF"""
    try:
        open_tracking=OpenTracking.objects.select_related('campaign_recipient__campaign').get(tracking_id=tracking_id)
        #update open tracking
        now=timezone.now()
        if not open_tracking.first_opened_at:
            open_tracking.first_opened_at=now
        open_tracking.last_opened_at=now
        open_tracking.open_count +=1
        open_tracking.save()
        #Get user agent and IP
        user_agent=request.META.get('HTTP_USER_AGENT','')
        ip_address=request.META.get('REMOTE_ADDR','')
        #detect device type
        device_type='desktop'
        if 'MOBILE' in user_agent:
            device_type='mobile'
        elif 'Tablet' in user_agent:
            device_type='tablet'
        #Create email event
        EmailEvent.objects.create(campaign_recipient=open_tracking.campaign_recipient,event_type='opened',user_agent=user_agent,ip_address=ip_address,
                                  device_type=device_type,timestamp=now)
        #update analytics asynchronously(optional)
        #you can use celery task here
        campaign_id=open_tracking.campaign_recipient.campaign.id
        try:
            analytics_service=AnalyticsService()
            analytics_service.update_campaign_analytics(campaign_id)
        except Exception as e:
            logger.exception('Failed to refresh analytics after open tracking for campaign %s', campaign_id)
    except OpenTracking.DoesNotExist:
        logger.warning('Open tracking record not found for tracking_id=%s', tracking_id)
    gif=b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    response=HttpResponse(gif,content_type='image/gif')
    response['Cache-Control']='no-cache,no-store,must-revalidate'
    response['Pragma']='no-cache'
    response['Expires']='0'
    return response
@csrf_exempt
def track_click(request,short_code,recipient_id):
    """Track link click and redirect to original URL"""
    try:
        click_tracking=ClickTracking.objects.get(short_code=short_code)
        recipient=CampaignRecipient.objects.get(id=recipient_id)
        #get user agent and IP
        user_agent=request.META.get('HTTP_USER_AGENT','')
        ip_address=request.META.get('REMOTE_ADDR','')
        ClickEvent.objects.create(click_tracking=click_tracking,campaign_recipient=recipient,ip_address=ip_address,user_agent=user_agent)
        click_tracking.total_clicks+=1
        #check if this is unique click for this recipient
        previous_click=ClickEvent.objects.filter(click_tracking=click_tracking,campaign_recipient=recipient).count()
        if previous_click==1:
            click_tracking.unique_clicks+=1
        click_tracking.save()
        #create email event
        EmailEvent.objects.create(campaign_recipient=recipient,event_type='clicked',clicked_url=click_tracking.original_url,user_agent=user_agent,ip_address=ip_address,timestamp=timezone.now())
        #update analytics
        analytics_service=AnalyticsService()
        analytics_service.update_campaign_analytics(recipient.campaign.id)
        return HttpResponseRedirect(click_tracking.original_url)
    except (ClickTracking.DoesNotExist,CampaignRecipient.DoesNotExist):
        return HttpResponseRedirect('/')
