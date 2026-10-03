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
    #template=models.ForeignKey(EmailTemplate,on_delete=models.SET_NULL,null=True,blank=True,related_name='campaigns',help_text="Template used for this campaign")
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
    lists=models.ManyToManyField('ContactList',blank=True)
    tags=models.ManyToManyField('Tag',blank=True)
    filter_type=models.CharField(max_length=10,choices=[('and','AND'),('or','OR')],default='or')
    class Meta:
        ordering=['-created_at']
        verbose_name="Campaign"
        verbose_name_plural="Campaigns"
    def __str__(self):
        return self.name
class CampaignAttachment(models.Model):
    campaign=models.ForeignKey("Campaign",on_delete=models.CASCADE,related_name="attachments")
    file=models.FileField(upload_to="campaign_attachemnts/")
    file_name=models.CharField(max_length=255)
    uploaded_at=models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.file_name
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
        def __str__(self):
            return self.name
class Contact(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='contacts',null=True,blank=True)
    email=models.EmailField(unique=True)
    name=models.CharField(max_length=255,blank=True,null=True)
    is_subscribed=models.BooleanField(default=True)
    lists=models.ManyToManyField(ContactList,related_name='contacts',blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    tags=models.ManyToManyField(Tag,related_name='tags',blank=True)
    class meta:
        ordering=['email']
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
        #Delivery rate
        if self.total_sent > 0:
            self.delivery_rate=round((self.total_delivered/self.total_sent)*100,2)
            self.bounce_rate=round((self.total_bounced/self.total_sent)*100,2)
        #Open rate(based on delivered)
        if self.total_delivered>0:
            self.open_rate=round((self.unique_opens/self.total_delivered)*100,2)
            self.click_rate=round((self.unique_clicks/self.total_delivered)*100,2)
        #click-to-open rate
        if self.unique_opens>0:
            self.click_to_open_rate=round((self.unique_clicks/self.unique_opens)*100,2)
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
class DripCampaign(models.Model):
    TRIGGER_CHOICES=[
        ('contact_added','Contact Added'),
        ('tag_added','Tag Added'),
        ('manual','Manual'),
        ('webhook','Webhook Event'),
    ]
    STATUS_CHOICES=[
        ('draft','Draft'),
        ('active','Active'),
        ('paused','Paused'),
        ('archived','Archived'),
    ]
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='drip_campaigns')
    name=models.CharField(max_length=255,help_text="Campaign name")
    description=models.TextField(blank=True,null=True)
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default="draft")
    #trigger
    trigger_type=models.CharField(max_length=50,choices=TRIGGER_CHOICES,default='contact_added')
    #if trigger is added through tag 
    trigger_tag=models.ForeignKey(Tag,on_delete=models.SET_NULL,null=True,blank=True,help_text="start campaogn after the speicifc tag is assigned to the user")
    #if trigger='webhook'
    trigger_webhook_event=models.CharField(max_length=100,blank=True,null=True,help_text="webhook event name e.g 'member_checkin'")
    #which list contact will enroll
    lists=models.ManyToManyField(ContactList,blank=True,help_text="enroll the contact of this list automatically")
    #whic tag's contact should enroll
    tags=models.ManyToManyField(Tag,blank=True,related_name='drip_campaigns',help_text="enroll those tag contact automatically")
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['created_at']
        verbose_name="Drip Campaign"
        verbose_name_plural="Drip campaigns"
    def __str__(self):
        return f"{self.name} ({self.status})"
#drip step model
class DripStep(models.Model):
    ACTION_CHOICES=[('send_email','Send Email'),#send Email
                    ('wait','Wait'),#stop
                    ('condition','Check Condition'),#condition check karo
                    ('add_tag','Add tag'),#assign tag
                    ('remove_tag','Remove Tag'),#Remove tag
                    ('end','End Campaign'),#end of campaign
                    ]
    drip_campaign=models.ForeignKey(DripCampaign,on_delete=models.CASCADE,related_name='steps')
    #order of the step-1,2,3,4..
    step_number=models.PositiveIntegerField()
    #action defined by the step
    action=models.CharField(max_length=50,choices=ACTION_CHOICES)
    #email fields(action=send_email)
    subject=models.CharField(max_length=255,blank=True,null=True,help_text="Email subject")
    from_email=models.EmailField(blank=True,null=True,help_text="Sender email")
    from_name=models.CharField(max_length=255,blank=True,null=True)
    reply_to=models.EmailField(blank=True,null=True)
    html_content=models.TextField(blank=True,null=True,help_text="HTML Content")
    plain_text_content=models.TextField(blank=True,null=True)
    delay_days=models.PositiveIntegerField(default=0,help_text="after how many days?")
    delay_hours=models.PositiveIntegerField(default=0,help_text="After how many hours?")
    #---Tag fields(if action=add_tag/remove_tag)---
    tag=models.ForeignKey(Tag,on_delete=models.SET_NULL,null=True,blank=True,help_text="which tag shoul be added or removed")
    follow_up_campaign=models.ForeignKey(DripCampaign,on_delete=models.SET_NULL,null=True,blank=True,related_name='triggered_by_steps',help_text="Start this campaign if follow-up rule triggers on this step")
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['step_number']
        unique_together=['drip_campaign','step_number']
        verbose_name="Drip Step"
        verbose_name_plural="Drip Steps"
    def __str__(self):
        return f"Step{self.step_number}-{self.action} ({self.drip_campaign.name})"
#DRIP CONDITION-Behaviour based condition
#only use when step action='condition'
class DripCondition(models.Model):
    CONDITION_CHOICES=[
        ('email_opened','Email Opened'), #opened email
        ('email_clicked','Email Clicked'),#if link clicked
        ('tag_exists','Tag Exists'),#uf there is tag
        ('webhook_event','Webhook Event'),#any custom event 
    ]
    #on which step those conditions are applied
    step=models.OneToOneField(DripStep,on_delete=models.CASCADE,related_name='condition')
    #check the condition
    condition_type=models.CharField(max_length=50,choices=CONDITION_CHOICES)
    #on which step condition must be checked
    #e.g step 1 
    refrence_step=models.ForeignKey(DripStep,on_delete=models.SET_NULL,null=True,blank=True,related_name='refrenced_in_conditions',help_text="which step email needs to be checked")
    #webhook event name(if condition=webhook_event)
    webhook_event_name=models.CharField(max_length=100,blank=True,null=True,help_text="e.g.'purchase_done','member_checkin'")
    #tag(if condition=tag_exists)
    tag=models.ForeignKey(Tag,on_delete=models.SET_NULL,null=True,blank=True)
    #if YES then which step
    yes_next_step=models.ForeignKey(DripStep,on_delete=models.SET_NULL,null=True,blank=True,related_name='condition_yes_path',help_text="if condition is true the  run the next step")
    #if no then which step
    no_next_step=models.ForeignKey(DripStep,on_delete=models.SET_NULL,null=True,blank=True,related_name="condition_no_path",help_text="if condition is wronged the run this step")
    class Meta:
        verbose_name="Drip Condition"
        verbose_name_plural="Drip Conditions"
    def __str__(self):
        return f"Condition:{self.condition_type} on Step {self.step.step_number}"
#Drip Enrollment-which contact which campaign
class DripEnrollment(models.Model):
    STATUS_CHOICES=[
        ('active','Active'),
        ('completed','Completed'),
        ('stopped','Stopped'),
        ('failed','Failed'),
    ]
    contact=models.ForeignKey(Contact,on_delete=models.CASCADE,related_name='drip_enrollments')
    drip_campaign=models.ForeignKey(DripCampaign,on_delete=models.CASCADE,related_name='enrollments')
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='active')
    current_step=models.ForeignKey(DripStep,on_delete=models.SET_NULL,null=True,blank=True,related_name='current_enrollments')
    next_send_at=models.DateTimeField(null=True,blank=True,help_text="when next need to be send")
    enrolled_at=models.DateTimeField(auto_now_add=True)
    completed_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        unique_together=['contact','drip_campaign']
        ordering=['-enrolled_at']
        verbose_name="Drip Enrollment"
        verbose_name_plural="Drip Enrollments"
    def __str__(self):
        return f"{self.contact.email} -> {self.drip_campaign.name} ({self.status})"
#Drip Email log-record of sent email
#connected with existing email event
class DripEmailLog(models.Model):
    STATUS_CHOICES=[
        ('sent','Sent'),
        ('failed','Failed'),
    ]
    enrollment=models.ForeignKey(DripEnrollment,on_delete=models.CASCADE,related_name='email_logs')
    step=models.ForeignKey(DripStep,on_delete=models.CASCADE,related_name='email_logs')
    contact=models.ForeignKey(Contact,on_delete=models.CASCADE,related_name='drip_email_logs')
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='sent')
    open_tracking=models.OneToOneField(OpenTracking,on_delete=models.SET_NULL,null=True,related_name='drip_log',help_text="Open tracking pixel")
    error_message=models.TextField(blank=True,null=True)
    sent_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-sent_at']
        verbose_name="Drip Email Log"
        verbose_name_plural="Drip Email Logs"
    def __str__(self):
        return f"{self.contact.email} | Step{self.step.step_number} | {self.status}"
#WEBHOOK EVENT LOG-external system se anne wale event
#(behaviour based campaign)
class WebhookEventLog(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='webhook_events')
    contact=models.ForeignKey(Contact,on_delete=models.CASCADE,related_name='webhook_events',null=True,blank=True)
    #event name e.g 'member_checkin','purchase_done'
    event_name=models.CharField(max_length=100,help_text="e.g.member_checkin,purchase_done")
    #extra data
    event_data=models.JSONField(default=dict,blank=True,help_text="JSON dats that comes with event")
    #is that event processed or not
    is_processed=models.BooleanField(default=False,)
    received_at=models.DateTimeField(auto_now_add=True)
    processed_at=models.DateTimeField(auto_now_add=True,blank=True)
    class Meta:
        ordering=['-received_at']
        indexes=[models.Index(fields=['user','event_name']),
                 models.Index(fields=['contact','event_name']),
                 models.Index(fields=['is_processed']),
                ]
        verbose_name="Webhook Event Log"
        verbose_name_plural="Webhook Event Logs"
    def __str__(self):
        return f"{self.event_name} - {self.contact.email if self.contact else 'Unknown'}"
#new-step level followup rule'
# step level IF/THEN
# if email_opened on step 2
# Then start "offer followup campaign"
# Buisness owner can set the rule for evebry step
class StepFollowUpRule(models.Model):
    TRIGGER_CHOICES=[
        ('email_opened','Email_opened'),
        ('email_clicked','Email clicked'),
        ('email_not_opened','Email Not Opened'),
        ('email_not_clicked','Email Not Clicked'),
    ]
    #on which step thos rule should apply
    step=models.ForeignKey(DripStep,on_delete=models.CASCADE,related_name='follow_up_rules',help_text="On whic step this IF/THEN rule apply")
    #IF-what shoul trigger
    trigger=models.CharField(max_length=50,choices=TRIGGER_CHOICES,help_text="IF this hapeens on the step email...")
    check_after_days=models.PositiveIntegerField(default=3,help_text="For not_opened/not_clicked:check after how many days ")
    #THEN-which campaign start
    follow_up_campaign=models.ForeignKey(DripCampaign,on_delete=models.CASCADE,related_name='step_level_rules',help_text="THEN strat this followup campaign")
    #stop main campaign when there follow up started
    stop_main_campaign=models.BooleanField(default=False,help_text="Stop main campaign when followup starts?")
    is_active=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name="Step Follow-up Rule"
        verbose_name_plural="Step Follow-up Rules"
    def __str__(self):
        return (f"IF{self.trigger} on Step {self.step.step_number}"
                F"THEN -> '{self.follow_up_campaign.name}'")
#new campaign level event
#rule
#campaign if/then
#if webhook="purchase_done during campaign"
#THEN start "Thank You" campaign
#Buisness owner can set event for whole campaign
class CampaignEventRule(models.Model):
    TRIGGER_CHOICES=[
        ('webhook_event','Webhook Event'),
        ('tag_added','Tag Added'),
        ('tag_removed','Tag Removed'),
        ('inactie_days','Contact Inactive in X Days')
    ]
    #for whic campaign this rule should apply
    campaign=models.ForeignKey(DripCampaign,on_delete=models.CASCADE,related_name='event_rules',help_text="On whic campaign this rule applies")
    #if -which trigger
    trigger=models.CharField(max_length=50,choices=TRIGGER_CHOICES,help_text="IF this event happens during the campaign...")
    #Webhook event name(trigger=webhook_event)
    webhook_event_name=models.CharField(max_length=100,blank=True,null=True,help_text="e.g 'purchase_done','member_left'")
    #tag(trigger=tag_added/tag_removed)
    tag=models.ForeignKey(Tag,on_delete=models.SET_NULL,null=True,blank=True,help_text="which tag triggers this rule")
    #Inactive days(trigeer=inactive_days)
    inactive_days=models.PositiveIntegerField(null=True,blank=True,help_text="After how many inactive days to trigger")
    #THEN-which campaign needs to start
    follow_up_campaign=models.ForeignKey(DripCampaign,on_delete=models.CASCADE,related_name='campaign_level_rules',help_text="THEN start this follow-up-campaign")
    #current campaign stop
    stop_current_campaign=models.BooleanField(default=False,help_text="Stop current campaign when follow-up starts?")
    is_active=models.BooleanField(default=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name="Campaign Event Rule"
        verbose_name_plural="Campaign Event Rules"
    def __str__(self):
        return (f"IF{self.trigger} in '{self.campaign.name}'"
                f"THEN -> '{self.follow_up_campaign.name}'")
#new-Follow up Trigger Log
#track which follow-up has triggered
class FollowUpTriggerLog(models.Model):
    #on which enrollment its trigger
    enrollment=models.ForeignKey(DripEnrollment,on_delete=models.CASCADE,related_name='follow_up_logs')
    #trigger from step rule
    step_rule=models.ForeignKey(StepFollowUpRule,on_delete=models.SET_NULL,null=True,blank=True,related_name='trigge_logs')
    #trigger from campaign rule
    campaign_rule=models.ForeignKey(CampaignEventRule,on_delete=models.SET_NULL,null=True,blank=True,related_name='trigger_logs')
    #which followup campaign started
    follow_up_campaign=models.ForeignKey(DripCampaign,on_delete=models.CASCADE,related_name='trigger_logs')
    #new enrollment which is created for followup
    follow_up_enrollment=models.ForeignKey(DripEnrollment,on_delete=models.SET_NULL,null=True,blank=True,related_name='triggered_from')
    triggered_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering=['-triggered_at']
        verbose_name="Follow-up Trigger Log"
        verbose_name_plural="Follow-up Trigger Logs"
    def __str__(self):
        return(f"{self.enrollment.contact.email}->"
               f"'{self.follow_up_campaign.name}' triggered at {self.triggered_at}")
# -------------------------------------------------------
# 1. AB TEST — Main A/B test container
#    Har campaign ke liye ek A/B test hoga
# -------------------------------------------------------
class ABTest(models.Model):

    STATUS_CHOICES = [
        ('draft', 'Draft'),           # Abhi setup ho raha hai
        ('running', 'Running'),       # Test chal raha hai
        ('completed', 'Completed'),   # Winner decide ho gaya
        ('cancelled', 'Cancelled'),   # Test cancel kiya
    ]

    WINNER_CRITERIA_CHOICES = [
        ('open_rate', 'Open Rate'),         # Kaun sa zyada open hua
        ('click_rate', 'Click Rate'),       # Kaun sa zyada click hua
        ('manual', 'Manual Selection'),     # Business owner khud decide kare
    ]

    # Kis campaign ka A/B test hai
    campaign = models.OneToOneField(
        Campaign,
        on_delete=models.CASCADE,
        related_name='ab_test',
        help_text="Kis campaign ka A/B test hai"
    )

    name = models.CharField(
        max_length=255,
        help_text="Test ka naam e.g. 'Subject Line Test'"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    # Winner kaun se criteria pe decide hoga
    winner_criteria = models.CharField(
        max_length=20,
        choices=WINNER_CRITERIA_CHOICES,
        default='open_rate'
    )

    # Kitne % contacts ko test variants milenge
    # Baaki contacts ko winner milega
    # Example: 30% → 15% Version A, 15% Version B
    #          70% → Winner version milega
    test_percentage = models.PositiveIntegerField(
        default=100,
        help_text="Kitne % contacts test mein shamil honge (1-100)"
    )

    # Kitne ghante baad winner decide hoga
    test_duration_hours = models.PositiveIntegerField(
        default=24,
        help_text="Kitne ghante baad winner decide hoga"
    )

    # Winner variant — test complete hone par set hoga
    winner_variant = models.ForeignKey(
        'ABTestVariant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='won_tests',
        help_text="Winning variant — test complete hone par set hoga"
    )

    # Test kab shuru hua
    started_at = models.DateTimeField(null=True, blank=True)

    # Test kab complete hua
    completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "A/B Test"
        verbose_name_plural = "A/B Tests"

    def _str_(self):
        return f"A/B Test: {self.name} ({self.campaign.name})"


# -------------------------------------------------------
# 2. AB TEST VARIANT — Har version (A, B, C...)
#    Ek test mein 2 ya zyada variants ho sakte hain
# -------------------------------------------------------
class ABTestVariant(models.Model):

    ab_test = models.ForeignKey(
        ABTest,
        on_delete=models.CASCADE,
        related_name='variants'
    )

    # Variant ka naam — Version A, Version B
    name = models.CharField(
        max_length=100,
        help_text="e.g. 'Version A', 'Version B'"
    )

    # ---- Kya test kar rahe hain ----

    # Subject line test (most common)
    subject = models.CharField(
        max_length=255,
        help_text="Is variant ka subject line"
    )

    # From name test (optional)
    from_name = models.CharField(
        max_length=255,
        blank=True, null=True,
        help_text="Alag sender name test karna ho toh"
    )

    # Content test (optional)
    html_content = models.TextField(
        blank=True, null=True,
        help_text="Alag content test karna ho toh — blank = campaign ka original content use hoga"
    )

    preview_text = models.CharField(
        max_length=255,
        blank=True, null=True,
        help_text="Alag preview text test karna ho toh"
    )

    # Kitne % contacts ko yeh variant milega
    # Default: 50/50 split
    recipient_percentage = models.PositiveIntegerField(
        default=50,
        help_text="Kitne % test contacts ko yeh variant milega"
    )

    # ---- Stats — automatically update hote hain ----
    sent_count = models.PositiveIntegerField(default=0)
    open_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)
    open_rate = models.FloatField(default=0.0)
    click_rate = models.FloatField(default=0.0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = ['ab_test', 'name']
        verbose_name = "A/B Test Variant"
        verbose_name_plural = "A/B Test Variants"

    def _str_(self):
        return f"{self.name} — {self.ab_test.name}"

    def update_stats(self):
        """
        Stats recalculate karo.
        Called after each open/click event.
        """
        if self.sent_count > 0:
            self.open_rate = round(
                (self.open_count / self.sent_count) * 100, 2
            )
            self.click_rate = round(
                (self.click_count / self.sent_count) * 100, 2
            )
            self.save(update_fields=['open_rate', 'click_rate'])


# -------------------------------------------------------
# 3. AB TEST RECIPIENT — Kaun sa contact kaun sa variant
#    Track karo ki kisko kaun sa version mila
# -------------------------------------------------------
class ABTestRecipient(models.Model):

    ab_test = models.ForeignKey(
        ABTest,
        on_delete=models.CASCADE,
        related_name='test_recipients'
    )

    variant = models.ForeignKey(
        ABTestVariant,
        on_delete=models.CASCADE,
        related_name='recipients'
    )

    # Aapka existing CampaignRecipient model
    campaign_recipient = models.OneToOneField(
        CampaignRecipient,
        on_delete=models.CASCADE,
        related_name='ab_test_recipient'
    )

    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='ab_test_recipients'
    )

    # Is contact ko winner email bhi bheja gaya?
    received_winner = models.BooleanField(
        default=False,
        help_text="Winner decide hone par is contact ko winner email mila?"
    )

    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['ab_test', 'contact']
        verbose_name = "A/B Test Recipient"
        verbose_name_plural = "A/B Test Recipients"

    def _str_(self):
        return (
            f"{self.contact.email} → "
            f"{self.variant.name} ({self.ab_test.name})"
        )
class Event(models.Model):

    EVENT_TYPE_CHOICES = [
        ('webinar', 'Webinar'),
        ('workshop', 'Workshop'),
        ('conference', 'Conference'),
        ('meetup', 'Meetup'),
        ('training', 'Training'),
        ('other', 'Other'),
    ]

    FORMAT_CHOICES = [
        ('online', 'Online'),
        ('offline', 'Offline'),
        ('hybrid', 'Hybrid'),       # Both online + offline
    ]

    PLATFORM_CHOICES = [
        ('zoom', 'Zoom'),
        ('google_meet', 'Google Meet'),
        ('microsoft_teams', 'Microsoft Teams'),
        ('webex', 'Webex'),
        ('youtube_live', 'YouTube Live'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]

    # Owner
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='events'
    )

    # Basic details
    name = models.CharField(
        max_length=255,
        help_text="Event name e.g. 'Summer Business Webinar'"
    )
    description = models.TextField(
        blank=True, null=True,
        help_text="Event description — what to expect, speaker details etc."
    )
    event_type = models.CharField(
        max_length=50,
        choices=EVENT_TYPE_CHOICES,
        default='webinar'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    # Date and time
    start_date = models.DateTimeField(
        help_text="Event start date and time"
    )
    end_date = models.DateTimeField(
        help_text="Event end date and time"
    )
    timezone = models.CharField(
        max_length=100,
        default='Asia/Kolkata',
        help_text="Event timezone e.g. 'Asia/Kolkata', 'UTC'"
    )

    # Format — online / offline / hybrid
    format = models.CharField(
        max_length=20,
        choices=FORMAT_CHOICES,
        default='online'
    )

    # ---- Online meeting details ----
    platform = models.CharField(
        max_length=50,
        choices=PLATFORM_CHOICES,
        blank=True, null=True,
        help_text="Online platform — Zoom, Google Meet, Teams etc."
    )
    meeting_link = models.URLField(
        blank=True, null=True,
        help_text="Meeting join link — paste any platform link here"
    )
    meeting_id = models.CharField(
        max_length=100,
        blank=True, null=True,
        help_text="Meeting ID (optional)"
    )
    meeting_password = models.CharField(
        max_length=100,
        blank=True, null=True,
        help_text="Meeting password (optional)"
    )
    meeting_instructions = models.TextField(
        blank=True, null=True,
        help_text="Special instructions e.g. 'Use Chrome browser'"
    )

    # ---- Offline venue details ----
    venue_name = models.CharField(
        max_length=255,
        blank=True, null=True,
        help_text="Venue name e.g. 'The Grand Hotel'"
    )
    venue_address = models.TextField(
        blank=True, null=True,
        help_text="Full venue address"
    )
    venue_city = models.CharField(
        max_length=100,
        blank=True, null=True
    )
    venue_maps_link = models.URLField(
        blank=True, null=True,
        help_text="Google Maps link for venue"
    )

    # ---- Registration settings ----
    is_registration_required = models.BooleanField(
        default=True,
        help_text="Do contacts need to register?"
    )
    is_public = models.BooleanField(
        default=False,
        help_text="Public event — anyone can register via link"
    )
    max_capacity = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Maximum attendees — blank means unlimited"
    )
    waitlist_enabled = models.BooleanField(
        default=False,
        help_text="Enable waitlist when capacity is full"
    )

    # Unique public registration link
    slug = models.SlugField(
        unique=True,
        blank=True, null=True,
        help_text="Public URL slug e.g. 'summer-webinar-2026'"
    )

    # Cover image
    cover_image = models.ImageField(
        upload_to='event_covers/',
        blank=True, null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Event"
        verbose_name_plural = "Events"

    def __str__(self):
        return f"{self.name} ({self.start_date.date()})"

    @property
    def is_full(self):
        """Check if event has reached max capacity"""
        if not self.max_capacity:
            return False
        confirmed_count = self.registrations.filter(
            status='confirmed'
        ).count()
        return confirmed_count >= self.max_capacity

    @property
    def available_spots(self):
        """How many spots are left"""
        if not self.max_capacity:
            return None
        confirmed_count = self.registrations.filter(
            status='confirmed'
        ).count()
        return max(0, self.max_capacity - confirmed_count)


# -------------------------------------------------------
# 2. EVENT REGISTRATION FORM
#    Custom fields business owner can add
# -------------------------------------------------------
class EventRegistrationForm(models.Model):

    FIELD_TYPE_CHOICES = [
        ('text', 'Text'),
        ('email', 'Email'),
        ('phone', 'Phone'),
        ('number', 'Number'),
        ('select', 'Dropdown'),
        ('checkbox', 'Checkbox'),
        ('textarea', 'Text Area'),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='form_fields'
    )

    # Field details
    field_name = models.CharField(
        max_length=100,
        help_text="Field name e.g. 'company', 'job_title'"
    )
    field_label = models.CharField(
        max_length=255,
        help_text="Label shown to contact e.g. 'Your Company Name'"
    )
    field_type = models.CharField(
        max_length=20,
        choices=FIELD_TYPE_CHOICES,
        default='text'
    )

    # For dropdown fields — comma separated options
    options = models.TextField(
        blank=True, null=True,
        help_text="For dropdown — comma separated options e.g. 'CEO,Manager,Developer'"
    )

    is_required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name = "Event Form Field"
        verbose_name_plural = "Event Form Fields"

    def __str__(self):
        return f"{self.field_label} ({self.event.name})"


# -------------------------------------------------------
# 3. EVENT REGISTRATION
#    Track who registered for the event
# -------------------------------------------------------
class EventRegistration(models.Model):

    STATUS_CHOICES = [
        ('confirmed', 'Confirmed'),
        ('waitlisted', 'Waitlisted'),
        ('cancelled', 'Cancelled'),
        ('attended', 'Attended'),
        ('no_show', 'No Show'),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='registrations'
    )

    # Existing contact or new contact
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='event_registrations',
        null=True, blank=True
    )

    # For public registrations — contact may not exist yet
    email = models.EmailField(
        help_text="Registrant email"
    )
    name = models.CharField(
        max_length=255,
        blank=True, null=True
    )
    phone = models.CharField(
        max_length=20,
        blank=True, null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='confirmed'
    )

    # Custom form field answers stored as JSON
    form_responses = models.JSONField(
        default=dict,
        blank=True,
        help_text="Answers to custom registration form fields"
    )

    # Unique token for this registration
    # Used in confirmation emails and cancel links
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        help_text="Unique token for this registration"
    )

    # Confirmation email sent?
    confirmation_sent = models.BooleanField(default=False)

    registered_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['event', 'email']
        ordering = ['-registered_at']
        verbose_name = "Event Registration"
        verbose_name_plural = "Event Registrations"

    def __str__(self):
        return f"{self.email} → {self.event.name} ({self.status})"


# -------------------------------------------------------
# 4. EVENT REMINDER
#    Automated emails before and after event
# -------------------------------------------------------
class EventReminder(models.Model):

    TIMING_TYPE_CHOICES = [
        ('before', 'Before Event'),     # days_offset negative
        ('on_day', 'On Event Day'),     # days_offset = 0
        ('after', 'After Event'),       # days_offset positive
    ]

    RECIPIENT_CHOICES = [
        ('all', 'All Registrants'),
        ('confirmed', 'Confirmed Only'),
        ('waitlisted', 'Waitlisted Only'),
        ('attended', 'Attended Only'),
        ('no_show', 'No Show Only'),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='reminders'
    )

    # Reminder name — internal
    name = models.CharField(
        max_length=255,
        help_text="Internal name e.g. '7 day reminder', 'Thank you email'"
    )

    # Timing
    timing_type = models.CharField(
        max_length=20,
        choices=TIMING_TYPE_CHOICES,
        default='before'
    )
    days_offset = models.IntegerField(
        default=-1,
        help_text=(
            "Days relative to event: "
            "-7 = 7 days before, "
            "0 = event day, "
            "+1 = 1 day after"
        )
    )
    send_time = models.TimeField(
        default='09:00',
        help_text="What time to send this reminder e.g. 09:00 AM"
    )

    # Who gets this reminder
    send_to = models.CharField(
        max_length=20,
        choices=RECIPIENT_CHOICES,
        default='confirmed'
    )

    # Email content
    subject = models.CharField(max_length=255)
    html_content = models.TextField(
        help_text=(
            "Email content. Available variables: "
            "{{event_name}}, {{event_date}}, {{event_time}}, "
            "{{platform}}, {{meeting_link}}, {{meeting_id}}, "
            "{{meeting_password}}, {{venue_name}}, {{venue_address}}, "
            "{{attendee_name}}, {{cancel_link}}"
        )
    )
    plain_text_content = models.TextField(blank=True, null=True)

    # Include meeting link automatically in email?
    include_meeting_details = models.BooleanField(
        default=True,
        help_text="Automatically include meeting link/venue details"
    )

    # Include cancel registration link?
    include_cancel_link = models.BooleanField(
        default=True,
        help_text="Include link to cancel registration"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['days_offset', 'send_time']
        verbose_name = "Event Reminder"
        verbose_name_plural = "Event Reminders"

    def __str__(self):
        if self.days_offset < 0:
            return f"{abs(self.days_offset)} days before — {self.name}"
        elif self.days_offset == 0:
            return f"Event day — {self.name}"
        else:
            return f"{self.days_offset} days after — {self.name}"


# -------------------------------------------------------
# 5. EVENT REMINDER LOG
#    Track which reminders were sent
#    Prevents duplicate sending
# -------------------------------------------------------
class EventReminderLog(models.Model):

    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('skipped', 'Skipped'),
    ]

    reminder = models.ForeignKey(
        EventReminder,
        on_delete=models.CASCADE,
        related_name='logs'
    )
    registration = models.ForeignKey(
        EventRegistration,
        on_delete=models.CASCADE,
        related_name='reminder_logs'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='sent'
    )
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Make sure same reminder is not sent twice to same person
        unique_together = ['reminder', 'registration']
        ordering = ['-sent_at']
        verbose_name = "Event Reminder Log"
        verbose_name_plural = "Event Reminder Logs"

    def __str__(self):
        return (
            f"{self.registration.email} | "
            f"{self.reminder.name} | "
            f"{self.status}"
        )


# -------------------------------------------------------
# 6. EVENT INVITE
#    Track who was invited to the event
# -------------------------------------------------------
class EventInvite(models.Model):

    STATUS_CHOICES = [
        ('sent', 'Invite Sent'),
        ('opened', 'Invite Opened'),
        ('registered', 'Registered'),
        ('declined', 'Declined'),
    ]

    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='invites'
    )
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name='event_invites'
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='sent'
    )

    # Unique invite token
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True
    )

    invited_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['event', 'contact']
        ordering = ['-invited_at']
        verbose_name = "Event Invite"
        verbose_name_plural = "Event Invites"

    def __str__(self):
        return f"{self.contact.email} -> {self.event.name} ({self.status})"