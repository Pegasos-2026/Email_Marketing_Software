from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from campaigns.analytics_service import AnalyticsService
from campaigns.contact_service import ContactImportService
from campaigns.models import Campaign, CampaignRecipient, CampaignAnalytics, Contact, EmailEvent


class AnalyticsServiceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.campaign = Campaign.objects.create(
            user=self.user,
            name='Test Campaign',
            subject='Hello',
            from_email='sender@example.com',
            status='sent',
            sent_at=timezone.now(),
        )
        self.contact_a = Contact.objects.create(user=self.user, email='a@example.com', name='Contact A')
        self.contact_b = Contact.objects.create(user=self.user, email='b@example.com', name='Contact B')
        self.recipient_a = CampaignRecipient.objects.create(
            campaign=self.campaign,
            contact=self.contact_a,
            status='sent',
            sent_at=timezone.now(),
        )
        self.recipient_b = CampaignRecipient.objects.create(
            campaign=self.campaign,
            contact=self.contact_b,
            status='failed',
        )
        self.service = AnalyticsService()

    def test_update_campaign_analytics_computes_expected_metrics(self):
        EmailEvent.objects.create(campaign_recipient=self.recipient_a, event_type='delivered')
        EmailEvent.objects.create(campaign_recipient=self.recipient_a, event_type='opened')
        EmailEvent.objects.create(
            campaign_recipient=self.recipient_a,
            event_type='clicked',
            clicked_url='https://example.com',
        )
        EmailEvent.objects.create(campaign_recipient=self.recipient_b, event_type='failed')

        analytics = self.service.update_campaign_analytics(self.campaign.id)

        self.assertEqual(analytics.total_recipients, 2)
        self.assertEqual(analytics.total_sent, 1)
        self.assertEqual(analytics.total_failed, 1)
        self.assertEqual(analytics.total_delivered, 1)
        self.assertEqual(analytics.unique_opens, 1)
        self.assertEqual(analytics.total_opened, 1)
        self.assertEqual(analytics.unique_clicks, 1)
        self.assertEqual(analytics.total_clicked, 1)
        self.assertEqual(analytics.bounce_rate, 0.0)
        self.assertEqual(analytics.delivery_rate, 100.0)
        self.assertEqual(analytics.open_rate, 100.0)
        self.assertEqual(analytics.click_rate, 100.0)
        self.assertEqual(analytics.click_to_open_rate, 100.0)

    def test_calculate_rates_saves_zero_values(self):
        analytics = CampaignAnalytics.objects.create(
            campaign=self.campaign,
            total_recipients=2,
            total_sent=0,
            total_delivered=0,
            total_failed=0,
            total_opened=0,
            unique_opens=0,
            total_clicked=0,
            unique_clicks=0,
            total_bounced=0,
            total_spam_reports=0,
            total_unsubscribes=0,
        )

        analytics.calculate_rates()
        refreshed = CampaignAnalytics.objects.get(pk=analytics.pk)

        self.assertEqual(refreshed.delivery_rate, 0.0)
        self.assertEqual(refreshed.open_rate, 0.0)
        self.assertEqual(refreshed.click_rate, 0.0)
        self.assertEqual(refreshed.click_to_open_rate, 0.0)
        self.assertEqual(refreshed.bounce_rate, 0.0)


class ContactIsolationTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass1')
        self.user2 = User.objects.create_user(username='user2', password='pass2')
        self.import_service_user1 = ContactImportService(self.user1)
        self.import_service_user2 = ContactImportService(self.user2)

    def test_import_same_email_for_different_users_creates_separate_contacts(self):
        row = {'email': 'shared@example.com', 'name': 'Shared Contact', 'is_subscribed': 'true'}
        result1, contact1 = self.import_service_user1._import_single_contact(row)
        result2, contact2 = self.import_service_user2._import_single_contact(row)

        self.assertEqual(result1, 'created')
        self.assertEqual(result2, 'created')
        self.assertEqual(contact1.email, contact2.email)
        self.assertNotEqual(contact1.user, contact2.user)
        self.assertEqual(Contact.objects.filter(email='shared@example.com').count(), 2)
