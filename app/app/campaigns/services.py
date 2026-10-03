from django.utils import timezone
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail,Email,To,Content,Attachment
from .models import Campaign,CampaignRecipient,EmailEvent,OpenTracking,ClickTracking,Contact
from .analytics_service import AnalyticsService
import base64
import time
class EmailService:
    """SendGrid email sending service"""
    def __init__(self):
        api_key=settings.SENDGRID_API_KEY
        if not api_key:
            raise ValueError("SENDGRID_API_KEY not found")
        self.sg=SendGridAPIClient(api_key)
class CampaignService:
    def __init__(self):
        self.email_service=EmailService()
        self.analytics_service=AnalyticsService()
    def send_campaign(self,campaign_id):
        """Send Campaign and intialize analytics"""
        campaign=Campaign.objects.get(id=campaign_id)
        #Validation
        if campaign.status=='sent':
            raise ValueError("Campaign already sent")
        if campaign.status=='sending':
            raise ValueError("Campaign is already sending")
        #initialize analytics
        self.analytics_service.initialize_campaign_analytics(campaign_id)
        #update status
        campaign.status='sending'
        campaign.save()
        recipients=CampaignRecipient.objects.filter(campaign=campaign,status="pending").select_related("contact")
        if not recipients.exists():
            raise ValueError("No recipients found for this campaign")
        success_count=0
        failed_count=0
        #send emails in batches
        BATCH_SIZE=100
        recipient_list=list(recipients)
        for i in range(0,len(recipient_list),BATCH_SIZE):
            batch=recipient_list[i:i+BATCH_SIZE]
            for recipient in batch:
                try:
                    contact=recipient.contact
                    open_tracking=OpenTracking.objects.create(campaign_recipient=recipient)
                    is_sent=self._send_email_with_tracking(campaign,recipient,open_tracking)
                    if is_sent:
                        recipient.status="sent"
                        recipient.sent_at=timezone.now()
                        recipient.save()
                        EmailEvent.objects.create(campaign_recipient=recipient,event_type="sent",timestamp=timezone.now())
                        success_count +=1
                    else:
                        recipient.status="failed"
                        recipient.save()
                        EmailEvent.objects.create(campaign_recipient=recipient,event_type="failed",timestamp=timezone.now())
                        failed_count +=1
                except Exception as e:
                    recipient.status="failed"
                    recipient.error_message=str(e)
                    recipient.save()
                    failed_count +=1
            if i + BATCH_SIZE < len(recipient_list):
                time.sleep(1)
            #update campaign status
            campaign.status='sent'
            campaign.sent_at=timezone.now()
            campaign.save()
            self.analytics_service.update_campaign_analytics(campaign_id)
            return {"total":success_count + failed_count,
                    "success":success_count,
                    "failed":failed_count,}
    def _send_email_with_tracking(self,campaign,recipient,open_tracking):
            """Send email with tracking pixel and click tracking"""
            try:
                contact=recipient.contact
                content=campaign.content
                #add tracking pixel to HTML
                tracking_pixel_url=f"http://your-domain.com/track/open/{open_tracking.tracking_id}/"
                tracking_pixel=f'<img src="{tracking_pixel_url}" width="1" height="1" alt=""/>'
                html_content=content.html_content
                html_content=html_content.replace('{{name}}',contact.name or "there")
                html_content=html_content.replace('{{email}}',contact.email)
                html_content=self._add_click_tracking(html_content,campaign,recipient)
                #add tracking pixel before </body>
                if '</body>' in html_content:
                    html_content = html_content.replace('</body>',f'{tracking_pixel}</body>')
                else:
                    html_content +=tracking_pixel
                message=Mail(from_email=Email(campaign.from_email,campaign.from_name or ""),
                             to_emails=To(contact.email),
                             subject=campaign.subject,
                             html_content=Content("text/html",html_content),
                             )
                attachments=campaign.attachments.all()
                for file in attachments:
                    with open(file.file.path,"rb") as f:
                        data=f.read()
                    encoded_file=base64.b64encode(data).decode()
                    attachment=Attachment(file_content=encoded_file,file_type="application/octet-stream",file_name=file.file_name,disposition="attachment")
                    message.add_attachment(attachment)
                if campaign.reply_to:
                    message.reply_to=Email(campaign.reply_to)
                sg=SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
                response=sg.send(message)
                if response.status_code in [200,202]:
                    recipient.status='sent'
                    recipient.sent_at=timezone.now()
                    recipient.save()
                    return True
                else:
                    raise Exception(f"SendGrid Failed:{response.status_code}")
            except Exception as e:
                recipient.status='failed'
                recipient.error_message=str(e)
                recipient.save()
                return False
    def _add_click_tracking(self,html_content,campaign,recipient):
        """Replace URLS with tracking URLs"""
        import re
        import hashlib
        url_pattern=r'href=["\']([^"\']+)["\']'
        urls=re.findall(url_pattern,html_content)
        for url in urls:
            if url.startswith('http'):
                short_code=hashlib.md5(f"{campaign.id}-{url}".encode()).hexdigest()[:10]
                click_tracking,created=ClickTracking.objects.get_or_create(campaign=campaign,original_url=url,defaults={'short_code':short_code})
                tracking_url=f"http://your-domain.com/track/click/{click_tracking.short_code}/{recipient.id}/"
                html_content=html_content.replace(f'href="{url}"',f'href="{tracking_url}"')
        return html_content