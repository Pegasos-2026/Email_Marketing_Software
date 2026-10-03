from rest_framework import serializers
from .models import DripCampaign,DripCondition,DripStep,DripEmailLog,DripEnrollment,Contact,ContactList,Tag,OpenTracking,WebhookEventLog,StepFollowUpRule,CampaignEventRule,FollowUpTriggerLog
class DripConditionSerializer(serializers.ModelSerializer):

    class Meta:
        model = DripCondition
        fields = [
            'id',
            'condition_type',       # email_opened / clicked / tag_exists / webhook
            'reference_step',       # Kis step ka email check karna hai
            'webhook_event_name',   # Agar webhook condition hai
            'tag',                  # Agar tag_exists condition hai
            'yes_next_step',        # YES hone par kaun sa step
            'no_next_step',         # NO hone par kaun sa step
        ]

    def validate(self, data):
        """validation according to condition"""

        condition_type = data.get('condition_type')

        #  For Email open/click check  reference step needed
        if condition_type in ['email_opened', 'email_clicked']:
            if not data.get('reference_step'):
                raise serializers.ValidationError({
                    'reference_step': ' For Email open/click condition reference step needed.'
                })

        # Webhook condition ke liye event name zaruri hai
        if condition_type == 'webhook_event':
            if not data.get('webhook_event_name'):
                raise serializers.ValidationError({
                    'webhook_event_name': 'For Webhook condition ke liye event name needed.'
                })

        # Tag condition ke liye tag zaruri hai
        if condition_type == 'tag_exists':
            if not data.get('tag'):
                raise serializers.ValidationError({
                    'tag': 'For Tag condition tag  needed to select.'
                })

        # YES aur NO path dono zaruri hain
        yes_step=data.get('yes_next_step')
        no_step=data.get('no_next_step')
        reference_step=data.get('reference_step')
        if not yes_step:
            raise serializers.ValidationError({
                'yes_next_step': 'Condition ke YES path ka step zaruri hai.'
            })

        if not no_step:
            raise serializers.ValidationError({
                'no_next_step': 'Condition ke NO path ka step zaruri hai.'
            })
        if yes_step==no_step:
            raise serializers.ValidationError('YES and NO step cant be same')
        if reference_step:
            if yes_step.step_number <= reference_step.step_number:
                raise serializers.ValidationError('YES step should start after current step.')
            if no_step.step_number <= reference_step.step_number:
                raise serializers.ValidationError('NO step shoul start after current step ')

        return data


# -------------------------------------------------------
# 2. DRIP STEP SERIALIZER
#    (Pehle banaya kyunki DripCampaign mein nested use hoga)
# -------------------------------------------------------
class DripStepSerializer(serializers.ModelSerializer):

    # Condition nested aayegi agar action = 'condition'
    condition = DripConditionSerializer(required=False)

    class Meta:
        model = DripStep
        fields = [
            'id',
            'step_number',          # 1, 2, 3...
            'action',               # send_email / wait / condition / add_tag / end
            # Email fields
            'subject',
            'from_email',
            'from_name',
            'reply_to',
            'html_content',
            'plain_text_content',
            # Delay fields
            'delay_days',
            'delay_hours',
            # Tag field
            'tag',
            # Nested condition
            'condition',
        ]

    def validate(self, data):
        """Action ke hisaab se validation"""

        action = data.get('action')

        # Send email ke liye subject aur content zaruri hai
        if action == 'send_email':
            if not data.get('subject'):
                raise serializers.ValidationError({
                    'subject': 'Email bhejne ke liye subject zaruri hai.'
                })
            if not data.get('html_content'):
                raise serializers.ValidationError({
                    'html_content': 'Email bhejne ke liye content zaruri hai.'
                })
            if not data.get('from_email'):
                raise serializers.ValidationError({
                    'from_email': 'Email bhejne ke liye from_email zaruri hai.'
                })

        # Add/remove tag ke liye tag select karna zaruri hai
        if action in ['add_tag', 'remove_tag']:
            if not data.get('tag'):
                raise serializers.ValidationError({
                    'tag': 'Tag action ke liye tag select karna zaruri hai.'
                })

        # Condition step mein condition data zaruri hai
        if action == 'condition':
            if not data.get('condition'):
                raise serializers.ValidationError({
                    'condition': 'Condition action ke liye condition details zaruri hain.'
                })

        return data

    def create(self, validated_data):
        """Step banao aur agar condition hai toh woh bhi banao"""

        condition_data = validated_data.pop('condition', None)

        step = DripStep.objects.create(**validated_data)

        # Agar condition data hai toh DripCondition bhi banao
        if condition_data and step.action == 'condition':
            DripCondition.objects.create(step=step, **condition_data)

        return step

    def update(self, instance, validated_data):
        """Step update karo aur condition bhi update karo"""

        condition_data = validated_data.pop('condition', None)

        # Step update karo
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Condition update karo
        if instance.action=="condition":
            if condition_data:
                if hasattr(instance,'condition'):
                    # Existing condition update karo
                    condition = instance.condition
                    for attr, value in condition_data.items():
                        setattr(condition, attr, value)
                    condition.save()
                else:
                    # Naya condition banao
                    DripCondition.objects.create(step=instance, **condition_data)
            else:
                if hasattr(instance,'condition'):
                    instance.condition.delete()

        return instance


# -------------------------------------------------------
# 3. DRIP CAMPAIGN SERIALIZER — Main serializer
# -------------------------------------------------------
class DripCampaignSerializer(serializers.ModelSerializer):

    # Nested steps — campaign ke saath steps bhi ban jayenge
    steps = DripStepSerializer(many=True, required=False)

    # Read only fields
    user = serializers.StringRelatedField(read_only=True)
    total_enrollments = serializers.SerializerMethodField()
    total_steps = serializers.SerializerMethodField()
    active_enrollments = serializers.SerializerMethodField()

    # Write only IDs
    list_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="Kin lists ke contacts enroll honge"
    )
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="Kin tags ke contacts enroll honge"
    )

    class Meta:
        model = DripCampaign
        fields = [
            'id',
            'user',
            'name',
            'description',
            'status',
            # Trigger
            'trigger_type',
            'trigger_tag',
            'trigger_webhook_event',
            # Contacts
            'list_ids',
            'tag_ids',
            # Nested
            'steps',
            # Read only stats
            'total_enrollments',
            'total_steps',
            'active_enrollments',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def get_total_enrollments(self, obj):
        """Total kitne contacts enrolled hain"""
        return obj.enrollments.count()

    def get_total_steps(self, obj):
        """Campaign mein kitne steps hain"""
        return obj.steps.count()

    def get_active_enrollments(self, obj):
        """Abhi kitne contacts active hain"""
        return obj.enrollments.filter(status='active').count()

    def validate(self, data):
        """Campaign level validation"""

        trigger_type = data.get('trigger_type')

        # Tag trigger ke liye tag zaruri hai
        if trigger_type == 'tag_added':
            if not data.get('trigger_tag'):
                raise serializers.ValidationError({
                    'trigger_tag': 'Tag trigger ke liye trigger tag select karna zaruri hai.'
                })

        # Webhook trigger ke liye event name zaruri hai
        if trigger_type == 'webhook':
            if not data.get('trigger_webhook_event'):
                raise serializers.ValidationError({
                    'trigger_webhook_event': 'Webhook trigger ke liye event name likhna zaruri hai.'
                })

        return data

    def validate_steps(self, steps):
        """Steps validation"""

        if not steps:
            return steps

        # Step numbers duplicate check
        step_numbers = [step.get('step_number') for step in steps]
        if len(step_numbers) != len(set(step_numbers)):
            raise serializers.ValidationError(
                'Step numbers duplicate nahi ho sakte.'
            )

        # Step numbers sorted hone chahiye
        if sorted(step_numbers) != step_numbers:
            raise serializers.ValidationError(
                'Steps ka order sahi nahi hai — step numbers sequence mein hone chahiye.'
            )

        return steps

    def create(self, validated_data):
        """Campaign + Steps ek saath banao"""

        steps_data = validated_data.pop('steps', [])
        list_ids = validated_data.pop('list_ids', [])
        tag_ids = validated_data.pop('tag_ids', [])

        # Logged in user assign karo
        validated_data['user'] = self.context['request'].user

        # Campaign banao
        campaign = DripCampaign.objects.create(**validated_data)

        # Lists assign karo
        if list_ids:
            lists = ContactList.objects.filter(
                id__in=list_ids,
                user=campaign.user
            )
            campaign.lists.set(lists)

        # Tags assign karo
        if tag_ids:
            tags = Tag.objects.filter(
                id__in=tag_ids,
                user=campaign.user
            )
            campaign.tags.set(tags)

        # Steps banao
        for step_data in steps_data:
            condition_data = step_data.pop('condition', None)

            step = DripStep.objects.create(
                drip_campaign=campaign,
                **step_data
            )

            # Condition banao agar hai
            if condition_data and step.action == 'condition':
                DripCondition.objects.create(step=step, **condition_data)

        return campaign

    def update(self, instance, validated_data):
        """Campaign update karo"""

        steps_data = validated_data.pop('steps', None)
        list_ids = validated_data.pop('list_ids', None)
        tag_ids = validated_data.pop('tag_ids', None)

        # Campaign fields update karo
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Lists update karo
        if list_ids is not None:
            lists = ContactList.objects.filter(
                id__in=list_ids,
                user=instance.user
            )
            instance.lists.set(lists)

        # Tags update karo
        if tag_ids is not None:
            tags = Tag.objects.filter(
                id__in=tag_ids,
                user=instance.user
            )
            instance.tags.set(tags)

        # Steps update karo — purane hata ke naye banao
        if steps_data is not None:
            instance.steps.all().delete()
            for step_data in steps_data:
                condition_data = step_data.pop('condition', None)
                step = DripStep.objects.create(
                    drip_campaign=instance,
                    **step_data
                )
                if condition_data and step.action == 'condition':
                    DripCondition.objects.create(step=step, **condition_data)

        return instance


# -------------------------------------------------------
# 4. DRIP CAMPAIGN LIST SERIALIZER
#    (Sirf list view ke liye — chhota aur fast)
# -------------------------------------------------------
class DripCampaignListSerializer(serializers.ModelSerializer):

    total_enrollments = serializers.SerializerMethodField()
    total_steps = serializers.SerializerMethodField()
    active_enrollments = serializers.SerializerMethodField()

    class Meta:
        model = DripCampaign
        fields = [
            'id',
            'name',
            'status',
            'trigger_type',
            'total_steps',
            'total_enrollments',
            'active_enrollments',
            'created_at',
        ]

    def get_total_enrollments(self, obj):
        return obj.enrollments.count()

    def get_total_steps(self, obj):
        return obj.steps.count()

    def get_active_enrollments(self, obj):
        return obj.enrollments.filter(status='active').count()


# -------------------------------------------------------
# 5. DRIP ENROLLMENT SERIALIZER
# -------------------------------------------------------
class DripEnrollmentSerializer(serializers.ModelSerializer):

    # Read only details
    contact_email = serializers.CharField(
        source='contact.email',
        read_only=True
    )
    contact_name = serializers.CharField(
        source='contact.name',
        read_only=True
    )
    campaign_name = serializers.CharField(
        source='drip_campaign.name',
        read_only=True
    )
    current_step_number = serializers.IntegerField(
        source='current_step.step_number',
        read_only=True
    )
    current_step_action = serializers.CharField(
        source='current_step.action',
        read_only=True
    )

    class Meta:
        model = DripEnrollment
        fields = [
            'id',
            'contact_email',
            'contact_name',
            'campaign_name',
            'status',
            'current_step_number',
            'current_step_action',
            'next_send_at',
            'enrolled_at',
            'completed_at',
        ]
        read_only_fields = ['enrolled_at', 'completed_at']


# -------------------------------------------------------
# 6. MANUAL ENROLLMENT SERIALIZER
#    (Business owner manually contact enroll kare)
# -------------------------------------------------------
class ManualEnrollmentSerializer(serializers.Serializer):

    # Ek contact enroll karna
    contact_id = serializers.IntegerField(required=False)

    # Ya multiple contacts enroll karna
    contact_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False
    )

    # Ya poori list enroll karna
    list_id = serializers.IntegerField(required=False)

    def validate(self, data):
        """Kam se kam ek option zaruri hai"""

        if not any([
            data.get('contact_id'),
            data.get('contact_ids'),
            data.get('list_id'),
        ]):
            raise serializers.ValidationError(
                'contact_id, contact_ids, ya list_id mein se ek zaruri hai.'
            )

        return data


# -------------------------------------------------------
# 7. DRIP EMAIL LOG SERIALIZER
# -------------------------------------------------------
class DripEmailLogSerializer(serializers.ModelSerializer):

    contact_email = serializers.CharField(
        source='contact.email',
        read_only=True
    )
    step_number = serializers.IntegerField(
        source='step.step_number',
        read_only=True
    )
    step_action = serializers.CharField(
        source='step.action',
        read_only=True
    )
    # Open tracking info
    open_count = serializers.IntegerField(
        source='open_tracking.open_count',
        read_only=True,
        default=0
    )
    first_opened_at = serializers.DateTimeField(
        source='open_tracking.first_opened_at',
        read_only=True
    )

    class Meta:
        model = DripEmailLog
        fields = [
            'id',
            'contact_email',
            'step_number',
            'step_action',
            'status',
            'open_count',
            'first_opened_at',
            'error_message',
            'sent_at',
        ]


# -------------------------------------------------------
# 8. WEBHOOK EVENT SERIALIZER
#    (External systems se events receive karna)
# -------------------------------------------------------
class WebhookEventSerializer(serializers.ModelSerializer):

    # Contact email se contact dhundha jayega
    contact_email = serializers.EmailField(write_only=True)

    class Meta:
        model = WebhookEventLog
        fields = [
            'id',
            'contact_email',        # Write only — contact dhundhne ke liye
            'event_name',           # e.g. 'member_checkin'
            'event_data',           # Extra JSON data
            'is_processed',
            'received_at',
        ]
        read_only_fields = ['is_processed', 'received_at']

    def validate_event_name(self, value):
        """Event name empty nahi hona chahiye"""
        if not value.strip():
            raise serializers.ValidationError(
                'Event name required.'
            )
        return value.strip().lower()

    def create(self, validated_data):
        """Webhook event receive karo aur contact dhundho"""

        contact_email = validated_data.pop('contact_email')
        user = self.context['request'].user

        # Contact dhundho
        try:
            contact = Contact.objects.get(
                email=contact_email,
                user=user
            )
        except Contact.DoesNotExist:
            raise serializers.ValidationError({
                'contact_email': f'{contact_email} contact nahi mila.'
            })

        # Webhook event log banao
        webhook_log = WebhookEventLog.objects.create(
            user=user,
            contact=contact,
            **validated_data
        )

        return webhook_log


# -------------------------------------------------------
# 9. DRIP CAMPAIGN ANALYTICS SERIALIZER
#    (Campaign ki performance dekhne ke liye)
# -------------------------------------------------------
class DripCampaignAnalyticsSerializer(serializers.ModelSerializer):

    campaign_name = serializers.CharField(
        source='name',
        read_only=True
    )

    # Enrollment stats
    total_enrolled = serializers.SerializerMethodField()
    active_count = serializers.SerializerMethodField()
    completed_count = serializers.SerializerMethodField()
    stopped_count = serializers.SerializerMethodField()

    # Email stats
    total_emails_sent = serializers.SerializerMethodField()
    total_emails_opened = serializers.SerializerMethodField()

    class Meta:
        model = DripCampaign
        fields = [
            'id',
            'campaign_name',
            'status',
            'trigger_type',
            'total_enrolled',
            'active_count',
            'completed_count',
            'stopped_count',
            'total_emails_sent',
            'total_emails_opened',
            'created_at',
        ]

    def get_total_enrolled(self, obj):
        return obj.enrollments.count()

    def get_active_count(self, obj):
        return obj.enrollments.filter(status='active').count()

    def get_completed_count(self, obj):
        return obj.enrollments.filter(status='completed').count()

    def get_stopped_count(self, obj):
        return obj.enrollments.filter(status='stopped').count()

    def get_total_emails_sent(self, obj):
        return DripEmailLog.objects.filter(
            enrollment__drip_campaign=obj,
            status='sent'
        ).count()
    def get_total_emails_opened(self,obj):
        return DripEmailLog.objects.filter(enrollment__drip_campaign=obj,open_tracking__open_count__gt=0).count()
# 10. NEW — STEP FOLLOW-UP RULE SERIALIZER
#     Step level IF/THEN rule ke liye
#     IF email_opened on Step 2
#     THEN start "Offer Follow-up" campaign
# -------------------------------------------------------
class StepFollowUpRuleSerializer(serializers.ModelSerializer):

    # Read only info
    step_number = serializers.IntegerField(
        source='step.step_number',
        read_only=True
    )
    follow_up_campaign_name = serializers.CharField(
        source='follow_up_campaign.name',
        read_only=True
    )

    class Meta:
        model = StepFollowUpRule
        fields = [
            'id',
            'step_number',              # Read only — kis step pe hai
            'trigger',                  # IF: email_opened / clicked / not_opened / not_clicked
            'check_after_days',         # For not_opened/not_clicked — kitne din baad check
            'follow_up_campaign',       # THEN: kaun si campaign start karo (write)
            'follow_up_campaign_name',  # THEN: campaign name (read only)
            'stop_main_campaign',       # Main campaign band karo?
            'is_active',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def validate(self, data):
        trigger = data.get('trigger')

        # not_opened / not_clicked ke liye check_after_days zaruri hai
        if trigger in ['email_not_opened', 'email_not_clicked']:
            check_after_days = data.get('check_after_days', 0)
            if check_after_days <= 0:
                raise serializers.ValidationError({
                    'check_after_days': (
                        'For not_opened/not_clicked trigger, '
                        'check_after_days must be greater than 0.'
                    )
                })

        return data

    def validate_follow_up_campaign(self, value):
        """
        Follow-up campaign same user ki honi chahiye
        aur active honi chahiye.
        """
        user = self.context['request'].user

        if value.user != user:
            raise serializers.ValidationError(
                'You can only use your own campaigns as follow-up.'
            )

        if value.status not in ['active', 'draft']:
            raise serializers.ValidationError(
                'Follow-up campaign must be active or draft.'
            )

        return value


# -------------------------------------------------------
# 11. NEW — CAMPAIGN EVENT RULE SERIALIZER
#     Campaign level IF/THEN rule ke liye
#     IF webhook = "purchase_done" during campaign
#     THEN start "Thank You" campaign
# -------------------------------------------------------
class CampaignEventRuleSerializer(serializers.ModelSerializer):

    # Read only info
    campaign_name = serializers.CharField(
        source='campaign.name',
        read_only=True
    )
    follow_up_campaign_name = serializers.CharField(
        source='follow_up_campaign.name',
        read_only=True
    )
    tag_name = serializers.CharField(
        source='tag.name',
        read_only=True
    )

    class Meta:
        model = CampaignEventRule
        fields = [
            'id',
            'campaign_name',            # Read only
            'trigger',                  # IF: webhook_event / tag_added / tag_removed / inactive_days
            'webhook_event_name',       # IF trigger = webhook_event
            'tag',                      # IF trigger = tag_added / tag_removed (write)
            'tag_name',                 # Read only
            'inactive_days',            # IF trigger = inactive_days
            'follow_up_campaign',       # THEN: kaun si campaign (write)
            'follow_up_campaign_name',  # Read only
            'stop_current_campaign',    # Current campaign band karo?
            'is_active',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def validate(self, data):
        trigger = data.get('trigger')

        # Webhook trigger ke liye event name zaruri hai
        if trigger == 'webhook_event':
            if not data.get('webhook_event_name'):
                raise serializers.ValidationError({
                    'webhook_event_name': (
                        'For webhook_event trigger, '
                        'webhook_event_name is required. '
                        "e.g. 'purchase_done', 'member_checkin'"
                    )
                })

        # Tag trigger ke liye tag zaruri hai
        if trigger in ['tag_added', 'tag_removed']:
            if not data.get('tag'):
                raise serializers.ValidationError({
                    'tag': f'For {trigger} trigger, tag is required.'
                })

        # Inactive days trigger ke liye days zaruri hai
        if trigger == 'inactive_days':
            inactive_days = data.get('inactive_days')
            if not inactive_days or inactive_days <= 0:
                raise serializers.ValidationError({
                    'inactive_days': (
                        'For inactive_days trigger, '
                        'inactive_days must be greater than 0.'
                    )
                })

        return data

    def validate_follow_up_campaign(self, value):
        """
        Follow-up campaign same user ki honi chahiye.
        """
        user = self.context['request'].user

        if value.user != user:
            raise serializers.ValidationError(
                'You can only use your own campaigns as follow-up.'
            )

        return value

    def validate_tag(self, value):
        """
        Tag same user ka hona chahiye.
        """
        user = self.context['request'].user

        if value and value.user != user:
            raise serializers.ValidationError(
                'You can only use your own tags.'
            )

        return value


# -------------------------------------------------------
# 12. NEW — FOLLOW-UP TRIGGER LOG SERIALIZER
#     Dekhne ke liye ki kaun sa follow-up
#     kab trigger hua
# -------------------------------------------------------
class FollowUpTriggerLogSerializer(serializers.ModelSerializer):

    # Contact info
    contact_email = serializers.CharField(
        source='enrollment.contact.email',
        read_only=True
    )
    contact_name = serializers.CharField(
        source='enrollment.contact.name',
        read_only=True
    )

    # Main campaign info
    main_campaign_name = serializers.CharField(
        source='enrollment.drip_campaign.name',
        read_only=True
    )

    # Follow-up campaign info
    follow_up_campaign_name = serializers.CharField(
        source='follow_up_campaign.name',
        read_only=True
    )

    # Which rule triggered it
    triggered_by = serializers.SerializerMethodField()

    class Meta:
        model = FollowUpTriggerLog
        fields = [
            'id',
            'contact_email',
            'contact_name',
            'main_campaign_name',       # Main campaign jo chal rahi thi
            'follow_up_campaign_name',  # Follow-up jo trigger hui
            'triggered_by',             # Step rule ya campaign rule
            'triggered_at',
        ]

    def get_triggered_by(self, obj):
        """
        Batata hai ki follow-up kis rule se trigger hua:
        - Step rule (email_opened on Step 2)
        - Campaign rule (webhook = purchase_done)
        """

        if obj.step_rule:
            return {
                'type': 'step_rule',
                'trigger': obj.step_rule.trigger,
                'step_number': obj.step_rule.step.step_number,
            }

        elif obj.campaign_rule:
            return {
                'type': 'campaign_rule',
                'trigger': obj.campaign_rule.trigger,
                'webhook_event': obj.campaign_rule.webhook_event_name,
            }

        return None