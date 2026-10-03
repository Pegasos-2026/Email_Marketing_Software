from rest_framework import serializers
from .models import Campaign,CampaignContent,ContactList,Contact,CampaignAnalytics,EmailEvent,ClickTracking,EmailTemplate
class CampaignContentSerializer(serializers.ModelSerializer):
    class Meta:
        model=CampaignContent
        fields=['html_content','plain_text_content']
    
    def validate_html_content(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("HTML content cannot be empty")
        return value
class CampaignSerializer(serializers.ModelSerializer):
    content = CampaignContentSerializer(required=False)
    list_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    contact_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    total_recipients = serializers.SerializerMethodField()
    user = serializers.StringRelatedField(read_only=True)
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = Campaign
        fields = [
            'id', 'user', 'name', 'subject', 'preview_text', 'from_email',
            'from_name', 'reply_to', 'status', 'scheduled_at', 'sent_at', 'created_at', 'updated_at',
            'content', 'list_ids', 'contact_ids', 'total_recipients'
        ]

    def get_total_recipients(self, obj):
        return obj.recipients.count()

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Campaign name is required")
        return value

    def validate_subject(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Email subject is required")
        return value

    def validate_from_email(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("From email is required")
        return value

    def validate(self, data):
        """Validate that content is provided and recipients are selected"""
        content = data.get('content')
        list_ids = data.get('list_ids', [])
        contact_ids = data.get('contact_ids', [])
        
        # Content (with html_content) is required
        if not content:
            raise serializers.ValidationError(
                {"content": "Email content with html_content is required. Please provide email body content."}
            )
        
        # Check if content has html_content
        if isinstance(content, dict):
            html_content = content.get('html_content', '').strip() if isinstance(content.get('html_content'), str) else ''
            if not html_content:
                raise serializers.ValidationError(
                    {"content": "html_content is required - please add email body content"}
                )
        
        # Ensure recipients are selected
        if not list_ids and not contact_ids:
            raise serializers.ValidationError(
                {"recipients": "Please select at least one contact list or import contacts"}
            )
        
        return data

    def create(self, validated_data):
        from campaigns.services import CampaignService
        from django.utils import timezone

        content_data = validated_data.pop('content', None)
        list_ids = validated_data.pop('list_ids', [])
        contact_ids = validated_data.pop('contact_ids', [])
        template_id = validated_data.pop('template_id', None)
        scheduled_at = validated_data.get('scheduled_at')

        service_data = {
            'name': validated_data['name'],
            'template_id': template_id,
            'subject': validated_data.get('subject'),
            'preview_text': validated_data.get('preview_text'),
            'from_email': validated_data['from_email'],
            'from_name': validated_data.get('from_name'),
            'reply_to': validated_data.get('reply_to'),
            'scheduled_at': scheduled_at,
            'list_ids': list_ids,
            'contact_ids': contact_ids,
        }

        if content_data:
            service_data['html_content'] = content_data.get('html_content')
            service_data['plain_text_content'] = content_data.get('plain_text_content')

        service = CampaignService()
        campaign = service.create_campaign_with_recipients(
            user=self.context['request'].user,
            data=service_data
        )
        
        # If scheduled_at is set and in the future, update status to 'scheduled'
        if scheduled_at and scheduled_at > timezone.now():
            campaign.status = 'scheduled'
            campaign.save()
        
        return campaign

    def get_template_info(self, obj):
        """Return template infromation if campiagn uses templates"""
        if obj.template:
            return {
                'id': obj.template.id,
                'name': obj.template.name,
                'category': obj.template.category,
                'usage_count': obj.template.usage_count,
            }
        return None

class CampaignCreateWithTemplateSerializer(serializers.Serializer):
    """Simplified serailizer for creating campaign"""
    name = serializers.CharField(max_length=255)
    template_id = serializers.IntegerField()
    list_ids = serializers.ListField(child=serializers.IntegerField())
    from_email = serializers.EmailField()
    from_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    reply_to = serializers.EmailField(required=False, allow_blank=True)
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)

class SaveCampaignAsTemplateSerializer(serializers.Serializer):

    """Serializer for saving campaign as template"""
    name=serializers.CharField(max_length=255)
    category=serializers.ChoiceField(choices=EmailTemplate.CATEGORY_CHOICES)
    description=serializers.CharField(required=False,allow_blank=True)
    is_public=serializers.BooleanField(default=False)
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
        fields=['campaign_name','campaign_subject','total_recipients','total_sent','total_delivered','total_failed','unique_opens',
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