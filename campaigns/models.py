from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import uuid
class Campaign(models.Model):
    STATUS_CHOICES=[
        ('draft','Draft'),
        ('scheduled','Scheduled'),
        ('sending','Sending'),
        ('sent','Sent'),
        ('paused','Paused'),
    ]
    #User link
    user=models.ForeignKey(User,on_delete=models.CASCADE,null=True,blank=True)
    template=models.ForeignKey('EmailTemplate',on_delete=models.SET_NULL,null=True,blank=True,related_name='campaigns',help_text="Template used for this campaign")
    name=models.CharField(max_length=255,help_text="Internal campaign name")
    subject=models.CharField(max_length=255,help_text="Email subject Line")
    preview_text=models.CharField(max_length=255,blank=True,null=True,help_text="Preview text show in inbox")
    from_email=models.EmailField(help_text="Send Email Address")
    from_name=models.CharField(max_length=255,blank=True,null=True,help_text="Sender name")
    reply_to=models.EmailField(blank=True,null=True,help_text="Reply-to Email address")
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='draft')
    scheduled_at=models.DateTimeField(blank=True,null=True,help_text="when to send this campaign")
    sent_at=models.DateTimeField(blank=True,null=True,help_text="When Campaign was sent")
    created_at=models.DateTimeField(auto_now=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['-created_at']
        verbose_name="Campaign"
        verbose_name_plural="Campaigns"
    def __str__(self):
        return self.name
class CampaignContent(models.Model):
    campaign=models.OneToOneField(
        Campaign,
        on_delete=models.CASCADE,
        related_name='content'
    )
    html_content=models.TextField(help_text="HTML email content")
    plain_text_content=models.TextField(blank=True,null=True,help_text="Plain text version")
    created_at=models.DateTimeField(auto_now=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        verbose_name="Campaign Content"
        verbose_name_plural="Campaign Contents"
    def __str__(self):
        return f"Content for {self.campaign.name}"
class ContactList(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,null=True,blank=True)
    name=models.CharField(max_length=255)
    description=models.TextField(blank=True,null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['name']
    def __str__(self):
        return self.name
class Tag(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    name=models.CharField(max_length=100)
    category=models.CharField(max_length=50)
    is_system=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together=('user','name')
class Contact(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='contacts',null=True,blank=True)
    email=models.EmailField()
    name=models.CharField(max_length=255,blank=True,null=True)
    is_subscribed=models.BooleanField(default=True)
    lists=models.ManyToManyField(ContactList,related_name='contacts',blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    tags=models.ManyToManyField(Tag,related_name='contacts',blank=True)
    class Meta:
        ordering=['email']
        unique_together = ('user','email')
    def __str__(self):
        return self.email
class CampaignRecipient(models.Model):
    STATUS_CHOICES=[
        ('sent','Sent'),
        ('pending','Pending'),
        ('failed','Failed'),
    ]
    campaign=models.ForeignKey(Campaign,on_delete=models.CASCADE,related_name="recipients")
    contact=models.ForeignKey(Contact,on_delete=models.CASCADE)
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending')
    sent_at=models.DateTimeField(blank=True,null=True)
    error_message=models.TextField(blank=True,null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together=['campaign','contact']
    def __str__(self):
        return f"{self.campaign.name} - {self.contact.email}"

class EmailLog(models.Model):
    """Store individual bulk email send attempts."""
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='email_logs')
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=[('sent', 'Sent'), ('failed', 'Failed')])
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Email Log"
        verbose_name_plural = "Email Logs"

    def __str__(self):
        return f"{self.contact.email} - {self.subject} - {self.status}"

class CampaignAnalytics(models.Model):
    """Campaign-level analytics-aggregrate stats"""
    campaign=models.OneToOneField('Campaign',on_delete=models.CASCADE,related_name='analytics')
    #sending metrics
    total_recipients=models.IntegerField(default=0)
    total_sent=models.IntegerField(default=0)
    total_delivered=models.IntegerField(default=0)
    total_failed=models.IntegerField(default=0)
    # Engagement metrics
    total_opened=models.IntegerField(default=0) #total opens(can be multiple per user)
    unique_opens=models.IntegerField(default=0) #unique users who opened
    total_clicked=models.IntegerField(default=0) #Total clicks
    unique_clicks=models.IntegerField(default=0) #unique users who clicked
    #negative metrics
    total_bounced=models.IntegerField(default=0)
    total_spam_reports=models.IntegerField(default=0)
    total_unsubscribes=models.IntegerField(default=0)
    #calculated rates(percentage)
    delivery_rate=models.FloatField(default=0.0)
    open_rate=models.FloatField(default=0.0)
    click_rate=models.FloatField(default=0.0)
    click_to_open_rate=models.FloatField(default=0.0)
    bounce_rate=models.FloatField(default=0.0)
    #Timestamps
    last_updated=models.DateTimeField(auto_now=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name="Campaign Analytics"
        verbose_name_plural="Campaign Analytics"
    def calculate_rates(self):
        """calculating all percentage rates"""
        self.delivery_rate = 0.0
        self.open_rate = 0.0
        self.click_rate = 0.0
        self.click_to_open_rate = 0.0
        self.bounce_rate = 0.0

        # Delivery rate and bounce rate
        if self.total_sent > 0:
            self.delivery_rate = round((self.total_delivered / self.total_sent) * 100, 2)
            self.bounce_rate = round((self.total_bounced / self.total_sent) * 100, 2)

        # Open rate (based on delivered)
        if self.total_delivered > 0:
            self.open_rate = round((self.unique_opens / self.total_delivered) * 100, 2)
            self.click_rate = round((self.unique_clicks / self.total_delivered) * 100, 2)

        # Click-to-open rate
        if self.unique_opens > 0:
            self.click_to_open_rate = round((self.unique_clicks / self.unique_opens) * 100, 2)

        # persist analytics values even when no events have occurred yet
        self.save()

    def __str__(self):
        return f"Analytics:{self.campaign.name}"

class EmailEvent(models.Model):
    """Individual email events-detailed tracking
    Every action on an email creates an event"""
    EVENT_TYPES=[
        ('sent','Sent'),
        ('delivered','Delivered'),
        ('opened','Opened'),
        ('clicked','Clicked'),
        ('bounced','Bounced'),
        ('spam','Marked as Spam'),
        ('unsubscribed','Unsubscribed'),
        ('failed','Failed'),
    ]
    campaign_recipient=models.ForeignKey('CampaignRecipient',on_delete=models.CASCADE,related_name='events')
    event_type=models.CharField(max_length=20,choices=EVENT_TYPES)
    #additional event data 
    clicked_url=models.URLField(blank=True,null=True) #for click events
    user_agent=models.CharField(max_length=500,blank=True,null=True)
    ip_address=models.GenericIPAddressField(blank=True,null=True)
    device_type=models.CharField(max_length=50,blank=True,null=True)
    #Raw event data from SendGrid webhook
    event_data=models.JSONField(blank=True,null=True)
    timestamp=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-timestamp']
        indexes=[
            models.Index(fields=['event_type','timestamp']),
            models.Index(fields=['campaign_recipient','event_type']),
        ]
        verbose_name="Email Event"
        verbose_name_plural="Email Events"
    def __str__(self):
        return f"{self.event_type}-{self.campaign_recipient.contact.email}"
class OpenTracking(models.Model):
    """Track email opens using tracking pixel Each recipient gets uniques tracking ID"""
    campaign_recipient=models.OneToOneField('CampaignRecipient',on_delete=models.CASCADE,related_name='open_tracking')
    tracking_id=models.UUIDField(default=uuid.uuid4,unique=True,db_index=True)
    #open statistics
    first_opened_at=models.DateTimeField(blank=True,null=True)
    last_opened_at=models.DateTimeField(blank=True,null=True)
    open_count=models.IntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name="Open Tracking"
        verbose_name_plural="Open Tracking"
    def __str__(self):
        return f"Opens:{self.open_count} - {self.campaign_recipient.contact.email}"
class ClickTracking(models.Model):
    """Track link Clicks in emails Ecah URL in Campaign gets unique short code"""
    campaign=models.ForeignKey('Campaign',on_delete=models.CASCADE,related_name='click_tracking')
    original_url=models.URLField()
    short_code=models.CharField(max_length=50,unique=True,db_index=True)
    #Click statistics
    total_clicks=models.IntegerField(default=0)
    unique_clicks=models.IntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name="Click Tracking"
        verbose_name_plural="Click Tracking"
        unique_together=['campaign','original_url']
    def __str__(self):
        return f"{self.original_url}-{self.total_clicks} clicks"
class ClickEvent(models.Model):
    """Individual click events"""
    click_tracking=models.ForeignKey(ClickTracking,on_delete=models.CASCADE,related_name='click_events')
    campaign_recipient=models.ForeignKey('CampaignRecipient',on_delete=models.CASCADE,related_name='click_events')
    ip_address=models.GenericIPAddressField(blank=True,null=True)
    user_agent=models.CharField(max_length=500,blank=True,null=True)
    clicked_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-clicked_at']
        indexes=[
            models.Index(fields=['clicked_at']),
        ]
    def __str__(self):
        return f"Click:{self.campaign_recipient.contact.email}-{self.clicked_at}"
class EmailTemplate(models.Model):
    CATEGORY_CHOICES=[
        ('newsletter','Newsletter'),
        ('promotional','Promotional'),
        ('event','Event'),
        ('welcome','Welcome'),
        ('announcement','Announcement'),
    ]
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='email_templates')
    name=models.CharField(max_length=255,help_text="Template name(internal)")
    category=models.CharField(max_length=50,choices=CATEGORY_CHOICES,default='newsletter')
    description=models.TextField(blank=True,null=True)
    #template content
    subject=models.CharField(max_length=255,help_text="Email subject line")
    preview_text=models.CharField(max_length=255,blank=True,null=True)
    html_content=models.TextField(help_text="HTML email template")
    plain_text_content=models.TextField(blank=True,null=True)
    available_variables=models.JSONField(default=list,help_text="list of varibles that can be used:['name','email','company',]")
    thumbnail=models.ImageField(upload_to='template_thumbnails/',blank=True,null=True,help_text="Template preview image")
    is_active=models.BooleanField(default=True)
    is_public=models.BooleanField(default=False,help_text="Make template available to all users")
    usage_count=models.IntegerField(default=0,help_text="How many times used")
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['-created_at']
        verbose_name="Email Template"
        verbose_name_plural="Email Templates"
        indexes=[
            models.Index(fields=['user','category']),
            models.Index(fields=['is_active','is_public']),
        ]
    def __str__(self):
        return f"{self.name} ({self.category})"
    def increment_usage(self):
        """Increment usage count"""
        self.usage_count +=1
        self.save(update_fields=['usage_count'])
