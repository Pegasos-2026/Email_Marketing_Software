from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from app.campaigns.models import Campaign, CampaignContent, CampaignRecipient, Contact
from app.emails.models import EmailSetting
from app.emails.warmup import apply_warmup_batch
from app.campaigns.services import CampaignService


class WarmupBatchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='warmup@example.com',
            email='warmup@example.com',
            password='TestPass123!',
        )
        EmailSetting.objects.create(
            user=self.user,
            provider='SendGrid',
            api_key='gAAAA-test-placeholder',
            from_email='warmup@example.com',
            domain_verified=True,
        )
        self.contacts = [
            Contact.objects.create(user=self.user, email=f'user{i}@example.com', name=f'User {i}')
            for i in range(5)
        ]

    def test_apply_warmup_batch_limits_recipients(self):
        with self.settings(DAILY_CAMPAIGN_SEND_LIMIT=2, CAMPAIGN_WARMUP_ENABLED=True):
            batch, meta = apply_warmup_batch(self.contacts, self.user, inbox_priority=True)
            self.assertEqual(len(batch), 2)
            self.assertEqual(meta['deferred'], 3)

    def test_apply_warmup_batch_disabled_for_marketing_mode(self):
        with self.settings(DAILY_CAMPAIGN_SEND_LIMIT=2, CAMPAIGN_WARMUP_ENABLED=True):
            batch, meta = apply_warmup_batch(self.contacts, self.user, inbox_priority=False)
            self.assertEqual(len(batch), 5)
            self.assertIsNone(meta)

    def test_send_campaign_leaves_pending_when_over_daily_limit(self):
        campaign = Campaign.objects.create(
            user=self.user,
            name='Warmup test',
            subject='Hello',
            from_email='warmup@example.com',
            inbox_priority=True,
        )
        CampaignContent.objects.create(
            campaign=campaign,
            html_content='<p>Hello</p>',
            plain_text_content='Dear Sir/Madam,\n\nHello.',
        )
        for contact in self.contacts:
            CampaignRecipient.objects.create(campaign=campaign, contact=contact, status='pending')

        with self.settings(DAILY_CAMPAIGN_SEND_LIMIT=2, CAMPAIGN_WARMUP_ENABLED=True):
            from app.emails import services as email_services

            service = CampaignService()
            original = service._send_email_with_tracking
            original_validate = email_services.validate_user_email_settings
            try:
                email_services.validate_user_email_settings = lambda *args, **kwargs: None
                service._send_email_with_tracking = lambda *args, **kwargs: True
                result = service.send_campaign(campaign.id)
            finally:
                service._send_email_with_tracking = original
                email_services.validate_user_email_settings = original_validate

        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'sending')
        self.assertEqual(result['success'], 2)
        self.assertEqual(result['pending_remaining'], 3)
        self.assertEqual(CampaignRecipient.objects.filter(campaign=campaign, status='sent').count(), 2)
