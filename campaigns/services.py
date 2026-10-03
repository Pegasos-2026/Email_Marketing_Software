from django.utils import timezone
from django.conf import settings
from .models import Campaign,CampaignRecipient,Contact,EmailEvent,OpenTracking,ClickTracking,EmailTemplate,CampaignContent
from .analytics_service import AnalyticsService
from emails.services import send_email
import time

class CampaignService:
    def __init__(self):
        self.analytics_service=AnalyticsService()
    def create_campaign_with_recipients(self,user,data):
        """Create campaign with optional template
        Args:
        user:User creating campaign
        data:{
        'name':'Campaign name',
        'template_id':1,#optional-use template
        'subject':'Email Subject',
        'list_ids':[1,2,3],
        'html_content':'<html>...',
        }
        Returns:Campaign instance
        """
        template=None
        template_id=data.get('template_id')
        if template_id:
            try:
                template=EmailTemplate.objects.get(id=template_id,is_active=True)
                if template.user != user and not template.is_public:
                    raise ValueError("you dont have access to this template")
            except EmailTemplate.DoesNotExist:
                raise ValueError(f"Template {template_id} not found")
        campaign_data={
            'user':user,
            'name':data['name'],
            'template':template,
            'status':'draft'
        }
        if template:
            #auto fill from template
            campaign_data['subject']=data.get('subject',template.subject)
            campaign_data['preview_text']=data.get('preview_text',template.preview_text)
            #use template content or override
            html_content=data.get('html_content',template.html_content)
            plain_text_content=data.get('plain_text_content',template.plain_text_content)
        else:
            campaign_data['subject']=data['subject']
            campaign_data['preview_text']=data.get('preview_text','')
            html_content=data.get('html_content','')
            plain_text_content=data.get('plain_text_content','')
        campaign_data['from_email']=data.get('from_email','')
        campaign_data['from_name']=data.get('from_name','')
        campaign_data['reply_to']=data.get('reply_to','')
        campaign_data['scheduled_at']=data.get('scheduled_at')
        #create campaign
        campaign = Campaign.objects.create(**campaign_data)
        #create content
        CampaignContent.objects.create(campaign=campaign, html_content=html_content, plain_text_content=plain_text_content)

        list_ids = data.get('list_ids', [])
        contact_ids = data.get('contact_ids', [])
        if list_ids:
            self.add_recipients_from_lists(campaign, list_ids)
        if contact_ids:
            self.add_recipients_from_contact_ids(campaign, contact_ids)
        if template:
            template.increment_usage()
        return campaign

    def add_recipients_from_contact_ids(self, campaign, contact_ids):
        from .models import CampaignRecipient

        contacts = Contact.objects.filter(
            id__in=contact_ids,
            user=campaign.user,
            is_subscribed=True
        ).distinct()
        recipients = [
            CampaignRecipient(campaign=campaign, contact=contact, status='pending')
            for contact in contacts
        ]
        CampaignRecipient.objects.bulk_create(recipients, ignore_conflicts=True)

    def add_recipients_from_lists(self, campaign, list_ids):
        from .models import CampaignRecipient

        contacts = Contact.objects.filter(
            lists__id__in=list_ids,
            lists__user=campaign.user,
            is_subscribed=True
        ).distinct()
        recipients = [
            CampaignRecipient(campaign=campaign, contact=contact, status='pending')
            for contact in contacts
        ]
        CampaignRecipient.objects.bulk_create(recipients, ignore_conflicts=True)

    def update_campaign_from_template(self,campaign_id,template_id):
        """update existing campaign with template
        Args:
        campaign_id:Campaign to update
        template_id:Template to apply
        """
        campaign = Campaign.objects.get(id=campaign_id)
        if campaign.status != 'draft':
            raise ValueError("Can you apply template to draft campaigns")
        template = EmailTemplate.objects.get(id=template_id, is_active=True)
        #Verify access
        if template.user !=campaign.user and not template.is_public:
            raise ValueError("you dont have access to this template")
        #update campaign
        campaign.template=template
        campaign.subject=template.subject
        campaign.preview_text=template.preview_text
        campaign.save()
        #update content
        if hasattr(campaign,'content'):
            campaign.content.html_content=template.html_content
            campaign.content.plain_text_content=template.plain_text_content
            campaign.content.save()
        else:
            CampaignContent.objects.create(campaign=campaign,html_content=template.html_content,plain_text_content=template.plain_text_content)
        #increment template usage
        template.increment_usage()
        return campaign
    def preview_campaign_with_template(self,campaign_id,sample_data=None):
        """Preview campaign with sample contact data
        Args:
        campaign_id:Campaign to preview
        sample_data:optional dict with sample values
        Returns:
        Rendered html with sample data
        """
        campaign=Campaign.objects.get(id=campaign_id)
        #default sample data
        if not sample_data:
            sample_data={
                'name':'John Doe',
                'first_name':'John',
                'last_name':'Doe',
                'email':'john@example.com',
                'company':'Acme Corp',
                'phone':'1234567890',
                'unsubscribe_url':'https://example.com/unsusbscribe',
                'discount_code':'SAVE20',
                'discount':'20',
                'product_name':'Amazing Product'
            }
        content=campaign.content
        rendered_subject=content.html_content
        for key,value in sample_data.items():
            rendered_subject=campaign.subject.replace(f'{{{{{key}}}}}',str(value))
        rendered_html=content.html_content
        for key,value in sample_data.items():
            rendered_html=rendered_html.replace(f'{{{{{key}}}}}',str(value))
        rendered_plain=content.plain_text_content or ''
        for key,value in sample_data.items():
            rendered_plain=rendered_plain.replace(f'{{{{{key}}}}}',str(value))
        return {
            'subject':rendered_subject,
            'html_content':rendered_html,
            'plain_text_content':rendered_plain,
            'sample_data':sample_data
        }
    def get_campaign_template_info(self,campaign_id):
        """Get template information for campaign"""
        campaign=Campaign.objects.select_related('template').get(id=campaign_id)
        if not campaign.template:
            return None
        template=campaign.template
        return{
            'template_id':template.id,
            'template_name':template.name,
            'template_category':template.category,
            'template_usage_count':template.usage_count,
            'template_variables':template.available_variables,
        }
    def save_campaign_as_template(self,campaign_id,template_data):
        """Save existing campaign as a template
        Args:
        campaign_id:Campaign to save as template
        template_data:{
        'name':'Template name',
        'category':'promotional',
        'description':'Template description',
        'is_public':'false'}
        Returns:
        EmailTemplate instance"""
        campaign=Campaign.objects.get(id=campaign_id)
        template=EmailTemplate.objects.create(
            user=campaign.user,
            name=template_data['name'],
            category=template_data.get('category','newsletter'),
            description=template_data.get('description',''),
            subject=campaign.subject,
            preview_text=campaign.preview_text,
            html_content=campaign.content.html_content,
            available_variables=self._extract_variables(campaign.content.html_content),
            is_public=template_data.get('is_public',False),
            is_ative=True
        )
        return template
    def _extract_variables(self,content):
        """Extract {{variable}} from content"""
        import re
        pattern=r'\{\{(\w+)\}\}'
        variables=re.findall(pattern,content)
        return list(set(variables))
    def send_campaign(self,campaign_id):
        """Send Campaign and initialize analytics"""
        campaign=Campaign.objects.get(id=campaign_id)
        if campaign.status=='sent':
            raise ValueError("Campaign already sent")
        analytics=self.analytics_service.initialize_campaign_analytics(campaign_id)
        campaign.status='sending'
        campaign.save()
        recipients=CampaignRecipient.objects.filter(campaign=campaign,status='pending').select_related('contact')
        if not recipients.exists():
            raise ValueError("No recipients found")
        success_count=0
        failed_count=0
        BATCH_SIZE=100
        for i in range(0,len(recipients),BATCH_SIZE):
            batch=recipients[i:i+BATCH_SIZE]
            for recipient in batch:
                open_tracking, _ = OpenTracking.objects.get_or_create(campaign_recipient=recipient)
                if self._send_email_with_tracking(campaign,recipient,open_tracking):
                    now = timezone.now()
                    EmailEvent.objects.create(
                        campaign_recipient=recipient, event_type='sent', timestamp=now
                    )
                    EmailEvent.objects.create(
                        campaign_recipient=recipient, event_type='delivered', timestamp=now
                    )
                    success_count += 1
                else:
                    EmailEvent.objects.create(
                        campaign_recipient=recipient, event_type='failed', timestamp=timezone.now()
                    )
                    failed_count += 1
            if i + BATCH_SIZE < len(recipients):
                time.sleep(1)
        campaign.status='sent'
        campaign.sent_at=timezone.now()
        campaign.save()
        self.analytics_service.update_campaign_analytics(campaign_id)
        return {
            "total":success_count + failed_count,
            "success":success_count,
            "failed":failed_count,
        }
    def _api_campaigns_base(self):
        site = (settings.SITE_URL or 'http://localhost:8000').rstrip('/')
        return f"{site}/api/campaigns"

    def _tracking_base_url(self):
        return f"{self._api_campaigns_base()}/track"

    def _send_email_with_tracking(self, campaign, recipient, open_tracking):
            """Send email with tracking pixel and click tracking"""
            contact = recipient.contact
            content = campaign.content
            tracking_pixel_url = (
                f"{self._tracking_base_url()}/open/{open_tracking.tracking_id}/"
            )
            tracking_pixel = f'<img src="{tracking_pixel_url}" width="1" height="1" alt=""/>'
            html_content = content.html_content
            unsubscribe_url = f"{self._api_campaigns_base()}/unsubscribe/{recipient.id}/"
            html_content = html_content.replace('{{name}}', contact.name or 'there')
            html_content = html_content.replace('{{email}}', contact.email)
            html_content = html_content.replace('{{unsubscribe_url}}', unsubscribe_url)
            html_content = self._add_click_tracking(html_content, campaign, recipient)

            if '</body>' in html_content:
                html_content = html_content.replace('</body>', f'{tracking_pixel}</body>')
            else:
                html_content += tracking_pixel

            from_email = campaign.from_email
            from_name = campaign.from_name
            if not from_email or not from_name:
                try:
                    setting = campaign.user.emailsetting
                    if not from_email:
                        from_email = setting.from_email
                    if not from_name:
                        from_name = setting.from_name
                except Exception:
                    raise ValueError(
                        "Email settings are not configured for this user. "
                        "Please configure an email delivery account before sending campaigns."
                    )

            if not from_email:
                raise ValueError("From email is required to send this campaign.")

            send_result = send_email(
                user=campaign.user,
                to_email=contact.email,
                subject=campaign.subject,
                html_content=html_content,
                from_email=from_email,
                from_name=from_name,
                reply_to=campaign.reply_to,
            )

            if send_result.get('success'):
                recipient.status = 'sent'
                recipient.sent_at = timezone.now()
                recipient.save()
                return True

            recipient.status = 'failed'
            recipient.error_message = send_result.get('error', 'Email send failed')
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
                tracking_url = (
                    f"{self._tracking_base_url()}/click/{click_tracking.short_code}/{recipient.id}/"
                )
                html_content=html_content.replace(f'href="{url}"',f'href="{tracking_url}"')
        return html_content