from rest_framework import serializers
from .models import ABTest, ABTestVariant, ABTestRecipient


# -------------------------------------------------------
# 1. AB TEST VARIANT SERIALIZER
# -------------------------------------------------------
class ABTestVariantSerializer(serializers.ModelSerializer):

    is_winner = serializers.SerializerMethodField()

    class Meta:
        model = ABTestVariant
        fields = [
            'id',
            'name',                  # Version A / Version B
            'subject',               # Different subject line
            'from_name',             # Different sender name (optional)
            'html_content',          # Different content (optional)
            'preview_text',          # Different preview text (optional)
            'recipient_percentage',  # What percentage of contacts get this variant
            # Stats — read only
            'sent_count',
            'open_count',
            'click_count',
            'open_rate',
            'click_rate',
            'is_winner',
            'created_at',
        ]
        read_only_fields = [
            'sent_count', 'open_count', 'click_count',
            'open_rate', 'click_rate', 'created_at',
        ]

    def get_is_winner(self, obj):
        """Returns True if this variant is the winner"""
        ab_test = obj.ab_test
        if ab_test.winner_variant:
            return ab_test.winner_variant.id == obj.id
        return False

    def validate_recipient_percentage(self, value):
        """Recipient percentage must be between 1 and 100"""
        if value <= 0 or value > 100:
            raise serializers.ValidationError(
                'Recipient percentage must be between 1 and 100.'
            )
        return value

    def validate_subject(self, value):
        """Subject line cannot be empty"""
        if not value.strip():
            raise serializers.ValidationError(
                'Subject line cannot be empty.'
            )
        return value


# -------------------------------------------------------
# 2. AB TEST SERIALIZER
# -------------------------------------------------------
class ABTestSerializer(serializers.ModelSerializer):

    # Nested variants — create test with variants together
    variants = ABTestVariantSerializer(many=True, required=True)

    # Read only fields
    winner_variant_name = serializers.CharField(
        source='winner_variant.name',
        read_only=True
    )
    campaign_name = serializers.CharField(
        source='campaign.name',
        read_only=True
    )

    class Meta:
        model = ABTest
        fields = [
            'id',
            'campaign',
            'campaign_name',
            'name',
            'status',
            'winner_criteria',       # open_rate / click_rate / manual
            'test_percentage',       # What % of contacts are in the test
            'test_duration_hours',   # How many hours before winner is decided
            'winner_variant',
            'winner_variant_name',
            'variants',
            'started_at',
            'completed_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'status', 'winner_variant',
            'started_at', 'completed_at',
            'created_at', 'updated_at',
        ]

    def validate_test_percentage(self, value):
        """Test percentage must be between 1 and 100"""
        if value <= 0 or value > 100:
            raise serializers.ValidationError(
                'Test percentage must be between 1 and 100.'
            )
        return value

    def validate_test_duration_hours(self, value):
        """Test duration must be at least 1 hour"""
        if value <= 0:
            raise serializers.ValidationError(
                'Test duration must be at least 1 hour.'
            )
        return value

    def validate_variants(self, variants):
        """Validate all variants together"""

        # Minimum 2 variants required
        if len(variants) < 2:
            raise serializers.ValidationError(
                'A/B test requires at least 2 variants.'
            )

        # Maximum 5 variants allowed
        if len(variants) > 5:
            raise serializers.ValidationError(
                'Maximum 5 variants are allowed.'
            )

        # Total percentage must equal 100
        total_percentage = sum(
            v.get('recipient_percentage', 0) for v in variants
        )
        if total_percentage != 100:
            raise serializers.ValidationError(
                f'Total percentage of all variants must equal 100 — '
                f'currently {total_percentage}.'
            )

        # Variant names must be unique
        names = [v.get('name', '') for v in variants]
        if len(names) != len(set(names)):
            raise serializers.ValidationError(
                'Variant names must be unique.'
            )

        return variants

    def validate(self, data):
        """Campaign level validation"""

        request = self.context.get('request')
        campaign = data.get('campaign')

        # Campaign must belong to the logged-in user
        if campaign and request and campaign.user != request.user:
            raise serializers.ValidationError({
                'campaign': 'You can only create an A/B test for your own campaigns.'
            })

        # Campaign must be in draft or scheduled status
        if campaign and campaign.status not in ['draft', 'scheduled']:
            raise serializers.ValidationError({
                'campaign': (
                    'A/B test can only be created for '
                    'draft or scheduled campaigns.'
                )
            })

        # Each campaign can only have one A/B test
        if campaign and ABTest.objects.filter(campaign=campaign).exists():
            if not self.instance:  # Only check on create
                raise serializers.ValidationError({
                    'campaign': 'An A/B test already exists for this campaign.'
                })

        return data

    def create(self, validated_data):
        """Create ABTest and all variants together"""

        variants_data = validated_data.pop('variants')

        # Create the main A/B test
        ab_test = ABTest.objects.create(**validated_data)

        # Create each variant
        for variant_data in variants_data:
            ABTestVariant.objects.create(
                ab_test=ab_test,
                **variant_data
            )

        return ab_test

    def update(self, instance, validated_data):
        """Update ABTest — only allowed in draft status"""

        variants_data = validated_data.pop('variants', None)

        # Cannot update a running or completed test
        if instance.status != 'draft':
            raise serializers.ValidationError(
                'Only draft tests can be updated.'
            )

        # Update test fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update variants — delete old ones and create new ones
        if variants_data is not None:
            instance.variants.all().delete()
            for variant_data in variants_data:
                ABTestVariant.objects.create(
                    ab_test=instance,
                    **variant_data
                )

        return instance


# -------------------------------------------------------
# 3. AB TEST LIST SERIALIZER
#    Lightweight serializer for list view
# -------------------------------------------------------
class ABTestListSerializer(serializers.ModelSerializer):

    campaign_name = serializers.CharField(
        source='campaign.name',
        read_only=True
    )
    winner_variant_name = serializers.CharField(
        source='winner_variant.name',
        read_only=True
    )
    variants_count = serializers.SerializerMethodField()

    class Meta:
        model = ABTest
        fields = [
            'id',
            'campaign_name',
            'name',
            'status',
            'winner_criteria',
            'test_percentage',
            'test_duration_hours',
            'winner_variant_name',
            'variants_count',
            'started_at',
            'completed_at',
            'created_at',
        ]

    def get_variants_count(self, obj):
        """Returns total number of variants in this test"""
        return obj.variants.count()


# -------------------------------------------------------
# 4. MANUAL WINNER SERIALIZER
#    Used when business owner manually selects the winner
# -------------------------------------------------------
class ManualWinnerSerializer(serializers.Serializer):

    variant_id = serializers.IntegerField()

    def validate_variant_id(self, value):
        """Variant must belong to this test"""
        ab_test = self.context.get('ab_test')
        if not ABTestVariant.objects.filter(
            id=value,
            ab_test=ab_test
        ).exists():
            raise serializers.ValidationError(
                'Invalid variant ID — this variant does not belong to this test.'
            )
        return value