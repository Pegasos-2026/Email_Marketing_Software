from rest_framework import serializers
from .models import Campaign,CampaignContent,ContactList,Contact,CampaignAnalytics,EmailEvent,ClickTracking,Tag,CampaignRecipient,CampaignAttachment,EmailTemplate
from .validators import validate_attachment
from app.emails.deliverability import resolve_campaign_reply_to
class CampaignContentSerializer(serializers.ModelSerializer):
    class Meta:
        model=CampaignContent
        fields=['html_content','plain_text_content']
class CampaignSerializer(serializers.ModelSerializer):
    content=CampaignContentSerializer(required=False)
    list_ids=serializers.ListField(child=serializers.IntegerField(),write_only=True,required=False)
    contact_ids=serializers.ListField(child=serializers.IntegerField(),write_only=True,required=False)
    manual_emails=serializers.ListField(child=serializers.EmailField(),required=False)
    tag_ids=serializers.ListField(child=serializers.IntegerField(),required=False)
    scheduled_at=serializers.DateTimeField(required=False)
    total_recipients=serializers.SerializerMethodField()
    delivery_summary=serializers.SerializerMethodField()
    user=serializers.StringRelatedField(read_only=True)
    class Meta:
        model=Campaign
        fields=['id','user','name','subject','preview_text','from_email',
                'from_name','reply_to','status','scheduled_at','sent_at','inbox_priority','created_at','updated_at','content','list_ids','contact_ids','manual_emails','tag_ids','total_recipients','delivery_summary']
    def get_total_recipients(self,obj):
        return obj.recipients.count()
    def get_delivery_summary(self,obj):
        recipients=obj.recipients.select_related('contact')
        failed=list(recipients.filter(status='failed'))
        return {
            'total': recipients.count(),
            'sent': recipients.filter(status='sent').count(),
            'failed': len(failed),
            'pending': recipients.filter(status='pending').count(),
            'failures': [
                {
                    'email': recipient.contact.email,
                    'error': recipient.error_message or 'Delivery failed',
                }
                for recipient in failed[:20]
            ],
        }
    def create(self,validated_data):
        request=self.context["request"]
        content_data=validated_data.pop('content',None)
        list_ids=validated_data.pop('list_ids',[])
        contact_ids=validated_data.pop('contact_ids',[])
        tag_ids=validated_data.pop('tag_ids',[])
        manual_emails=validated_data.pop('manual_emails',[])
        scheduled_at=validated_data.get('scheduled_at')
        validated_data['user']=self.context['request'].user
        validated_data['status']='scheduled' if scheduled_at else 'draft'
        if validated_data.get('from_email'):
            validated_data['reply_to'] = resolve_campaign_reply_to(
                validated_data.get('from_email'),
                validated_data.get('reply_to'),
            )
        campaign=Campaign.objects.create(**validated_data)
        if content_data:
            CampaignContent.objects.create(campaign=campaign,**content_data)
            files=request.FILES.getlist("attachments")
            for file in files:
                validate_attachment(file)
                CampaignAttachment.objects.create(campaign=campaign,file=file,file_name=file.name)
        if manual_emails:
            self._add_manual_recipients(campaign,manual_emails)
        if tag_ids:
            self._add_tag_recipients(campaign,tag_ids)
        if list_ids:
            self._add_recipients(campaign,list_ids)
        if contact_ids:
            self._add_contact_ids(campaign,contact_ids)
        return campaign
    def _add_recipients(self,campaign,list_ids):
        contacts=Contact.objects.filter(
            lists__id__in=list_ids,
            lists__user=campaign.user,
            is_subscribed=True
        ).distinct()
        recipients=[
            CampaignRecipient(campaign=campaign,contact=contact,status='pending')
            for contact in contacts
        ]
        CampaignRecipient.objects.bulk_create(recipients,ignore_conflicts=True)
    def _add_contact_ids(self,campaign,contact_ids):
        contacts=Contact.objects.filter(
            id__in=contact_ids,
            user=campaign.user,
        ).distinct()
        recipients=[
            CampaignRecipient(campaign=campaign,contact=contact,status='pending')
            for contact in contacts
        ]
        CampaignRecipient.objects.bulk_create(recipients,ignore_conflicts=True)
    def _add_tag_recipients(self,campaign,tag_ids):
        if not tag_ids:
            return
        contacts=Contact.objects.filter(tags__id__in=tag_ids,user=campaign.user,is_subscribed=True).distinct()
        for contact in contacts:
            CampaignRecipient.objects.get_or_create(campaign=campaign,contact=contact,defaults={'status':'pending'})
    def _add_manual_recipients(self,campaign,emails):
        for email in emails:
            contact,created=Contact.objects.get_or_create(email=email,user=campaign.user,defaults={'is_subscribed':True})
            CampaignRecipient.objects.get_or_create(campaign=campaign,contact=contact,defaults={'status':'pending'})
class CampaignListSerializer(serializers.ModelSerializer):
    total_recipients=serializers.SerializerMethodField()
    class Meta:
        model=Campaign
        fields=['id','name','subject','status','scheduled_at','sent_at','created_at','total_recipients']
    def get_total_recipients(self,obj):
        return obj.recipients.count()
class CampaignAnalyticsSerializer(serializers.ModelSerializer):
    campaign_name=serializers.CharField(source='campaign.name',read_only=True)
    campaign_subject=serializers.CharField(source='campaign.subject',read_only=True)
    class Meta:
        model=CampaignAnalytics
        fields=['campaign_name','campaign_subject','total_recipients','total_sent','total_delivered','total_failed','unique_opnes',
                'total_opened','unique_clicks','total_clicked','total_bounced','total_spam_reports','total_unsubscribes','delivery_rate',
                'open_rate','click_rate','click_to_open_rate','bounce_rate','last_updated',]
class EmailEventSerializer(serializers.ModelSerializer):
    contact_email=serializers.CharField(source='campaign_recipient.contact.email',read_only=True)
    class Meta:
        model=EmailEvent
        fields=[
            'id','contact_email','contact_name','event_type','clicked_url','device_type','ip_address','timestamp'
        ]
class ClickTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model=ClickTracking
        fields=['id','original_url','total_clicks','unique_clicks','created_at',]
class ContactSerailizer(serializers.ModelSerializer):
    tags=serializers.PrimaryKeyRelatedField(many=True,queryset=Tag.objects.all(),required=False)
    lists=serializers.PrimaryKeyRelatedField(many=True,queryset=ContactList.objects.all(),required=False)
    class Meta:
        model=Contact
        fields=[
            'id',
            'email',
            'name',
            'is_subscribed',
            'lists',
            'tags',
            'created_at'
        ]
        read_only_fields=['created_at']
    def validate_tags(self,value):
        user=self.context['request'].user
        for tag in value:
            if tag.user !=user:
                raise serializers.ValidationError("Invalid tag selection.")
        return value
    def validate_lists(self,value):
        user=self.context['request'].user
        for lst in value:
            if lst.user!=user:
                raise serializers.ValidationError("Invalid List selection")
        return value
    def create(self,validated_data):
        tags=validated_data.pop('tags',[])
        lists=validated_data.pop('lists',[])
        user=self.context['request'].user
        contact=Contact.objects.create(user=user,**validated_data)
        contact.tags.set(tags)
        contact.lists.set(lists)
        return contact
    def update(self,instance,validated_data):
        tags=validated_data.pop('tags',None)
        lists=validated_data.pop('lists',None)
        for attr,value in validated_data.items():
            setattr(instance,attr,value)
        instance.save()
        if tags is not None:
            instance.tags.set(tags)
        if lists is not None:
            instance.lists.set(lists)
        return instance
class CampaignAttachmentSerializer(serializers.ModelSerializer):
    file=serializers.FileField(validators=[validate_attachment])
    class Meta:
        model=CampaignAttachment
        fields=["id","file","file_name"]
class CampaignCreateWithTemplateSerializer(serializers.Serializer):
    """Simplified serializer for creating campaign from a template."""
    name=serializers.CharField(max_length=255)
    template_id=serializers.IntegerField()
    list_ids=serializers.ListField(child=serializers.IntegerField(),required=False,default=list)
    contact_list_ids=serializers.ListField(child=serializers.IntegerField(),required=False,default=list)
    contact_ids=serializers.ListField(child=serializers.IntegerField(),required=False,default=list)
    subject=serializers.CharField(max_length=255,required=False,allow_blank=True)
    from_email=serializers.EmailField()
    from_name=serializers.CharField(max_length=255,required=False,allow_blank=True)
    reply_to=serializers.EmailField(required=False,allow_blank=True)
    scheduled_at=serializers.DateTimeField(required=False,allow_null=True)

    def validate(self, attrs):
        list_ids=attrs.get('list_ids') or attrs.get('contact_list_ids') or []
        attrs['list_ids']=list_ids
        return attrs
class SaveCampaignAsTemplateSerializer(serializers.Serializer):
    """Serializer for saving campaign as template"""
    name=serializers.CharField(max_length=255)
    category=serializers.ChoiceField(choices=EmailTemplate.CATEGORY_CHOICES)
    description=serializers.CharField(required=False,allow_blank=True)
    is_public=serializers.BooleanField(default=False)
class EmailTemplateSerializer(serializers.ModelSerializer):
    user_name=serializers.CharField(source='user.username',read_only=True)
    category_display=serializers.CharField(source='get_category_display',read_only=True)
    class Meta:
        model=EmailTemplate
        fields=[
            'id',
            'user',
            'user_name',
            'name',
            'category',
            'category_display',
            'description',
            'subject',
            'preview_text',
            'html_content',
            'plain_text_content',
            'available_variables',
            'thumbnail',
            'is_active',
            'is_public',
            'usage_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields=['id','user','user_name','usage_count','created_at','updated_at']
class EmailTemplateListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view"""
    category_display=serializers.CharField(source='get_category_display',read_only=True)
    class Meta:
        model=EmailTemplate
        fields=[
            'id',
            'name',
            'category',
            'category_display',
            'description',
            'subject',
            'thumbnail',
            'usage_count',
            'is_public',
            'created_at',
        ]