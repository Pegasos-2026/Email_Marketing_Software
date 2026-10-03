from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from app.campaigns.email_validation import validate_contact_email, validate_email_batch
from app.campaigns.models import Campaign, Contact, ContactImportLog, ContactList


class AuthSetupMixin:
    def setUp(self):
        self.user = User.objects.create_user(
            username='test@example.com',
            email='test@example.com',
            password='TestPass123!',
            first_name='Test',
            last_name='User',
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')


class ContactAPITests(AuthSetupMixin, APITestCase):
    def test_create_and_list_contacts(self):
        create_url = reverse('contact-create')
        response = self.client.post(create_url, {
            'email': 'john@example.com',
            'name': 'John Doe',
            'is_subscribed': True,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        list_url = reverse('contact-list')
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['email'], 'john@example.com')

    def test_contact_list_crud(self):
        contact_list = ContactList.objects.create(
            user=self.user,
            name='Newsletter',
            description='Main list',
        )
        url = reverse('contact-list-detail', kwargs={'list_id': contact_list.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Newsletter')

    def test_export_contacts_csv(self):
        Contact.objects.create(
            user=self.user,
            email='export@example.com',
            name='Export User',
        )
        url = reverse('contact-export')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('text/csv', response['Content-Type'])


class CampaignAPITests(AuthSetupMixin, APITestCase):
    def test_create_campaign(self):
        url = '/api/campaigns/campaigns/'
        response = self.client.post(url, {
            'name': 'Launch',
            'subject': 'Hello world',
            'from_email': 'sender@example.com',
            'status': 'draft',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Campaign.objects.filter(user=self.user, name='Launch').exists())

    def test_delete_draft_campaign(self):
        campaign = Campaign.objects.create(
            user=self.user,
            name='Draft to delete',
            subject='Hello',
            from_email='sender@example.com',
            status='draft',
        )
        response = self.client.delete(f'/api/campaigns/campaigns/{campaign.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Campaign.objects.filter(id=campaign.id).exists())

    def test_cannot_delete_sent_campaign(self):
        campaign = Campaign.objects.create(
            user=self.user,
            name='Sent campaign',
            subject='Hello',
            from_email='sender@example.com',
            status='sent',
        )
        response = self.client.delete(f'/api/campaigns/campaigns/{campaign.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_update_email_template(self):
        from app.campaigns.models import EmailTemplate

        template = EmailTemplate.objects.create(
            user=self.user,
            name='Original',
            subject='Subject',
            html_content='<p>Hello</p>',
            category='newsletter',
        )
        response = self.client.put(
            f'/api/campaigns/templates/{template.id}/update',
            {
                'name': 'Updated name',
                'subject': 'Updated subject',
                'html_content': '<p>Updated</p>',
                'category': 'newsletter',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['name'], 'Updated name')
        template.refresh_from_db()
        self.assertEqual(template.name, 'Updated name')

    def test_send_campaign_fails_without_email_settings(self):
        campaign = Campaign.objects.create(
            user=self.user,
            name='Testing',
            subject='Hello',
            from_email='sender@example.com',
            status='draft',
        )
        from app.campaigns.models import CampaignContent, CampaignRecipient
        CampaignContent.objects.create(campaign=campaign, html_content='<p>Hello</p>')
        contact = Contact.objects.create(user=self.user, email='recipient@example.com')
        CampaignRecipient.objects.create(campaign=campaign, contact=contact, status='pending')

        response = self.client.post(f'/api/campaigns/campaigns/{campaign.id}/send/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('SMTP', response.data['error'])

        campaign.refresh_from_db()
        self.assertEqual(campaign.status, 'draft')
        self.assertIsNone(campaign.sent_at)

    def test_send_campaign_starts_async_for_large_batch(self):
        from unittest.mock import patch

        from app.campaigns.models import CampaignContent, CampaignRecipient
        from app.emails.models import EmailSetting

        EmailSetting.objects.create(
            user=self.user,
            provider='SendGrid',
            api_key='gAAAA-test-placeholder',
            from_email='sender@example.com',
            domain_verified=True,
        )
        campaign = Campaign.objects.create(
            user=self.user,
            name='Bulk send',
            subject='Hello',
            from_email='sender@example.com',
            status='draft',
        )
        CampaignContent.objects.create(campaign=campaign, html_content='<p>Hello</p>')
        contact = Contact.objects.create(user=self.user, email='recipient@example.com')
        CampaignRecipient.objects.create(campaign=campaign, contact=contact, status='pending')

        with patch('app.campaigns.send_worker.start_campaign_send_async', return_value=True) as mock_start:
            response = self.client.post(
                f'/api/campaigns/campaigns/{campaign.id}/send/',
                {'async': True},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertTrue(response.data.get('async'))
        mock_start.assert_called_once_with(campaign.id)

    def test_create_drip_campaign(self):
        url = '/api/campaigns/drip/campaigns/'
        response = self.client.post(url, {
            'name': 'Welcome Series',
            'description': 'Onboarding drip',
            'trigger_type': 'manual',
            'status': 'draft',
            'steps': [
                {
                    'step_number': 1,
                    'action': 'send_email',
                    'subject': 'Welcome',
                    'from_email': 'sender@example.com',
                    'html_content': '<p>Hello</p>',
                    'delay_days': 0,
                    'delay_hours': 0,
                },
            ],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['name'], 'Welcome Series')

    def test_create_drip_campaign_rejects_invalid_trigger(self):
        url = '/api/campaigns/drip/campaigns/'
        response = self.client.post(url, {
            'name': 'Bad Trigger',
            'trigger_type': 'user clicks',
            'steps': [],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('trigger_type', response.data)

    def test_create_drip_campaign_tag_trigger(self):
        from app.campaigns.models import Tag
        url = '/api/campaigns/drip/campaigns/'
        response = self.client.post(url, {
            'name': 'Tag Series',
            'trigger_type': 'tag_added',
            'trigger_tag_name': 'vip',
            'steps': [],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertTrue(Tag.objects.filter(user=self.user, name='vip').exists())

    def test_update_drip_campaign_steps_keeps_existing_tag_trigger(self):
        from app.campaigns.models import DripCampaign, Tag
        tag = Tag.objects.create(user=self.user, name='vip', category='general')
        campaign = DripCampaign.objects.create(
            user=self.user,
            name='Tag Series',
            trigger_type='tag_added',
            trigger_tag=tag,
        )
        url = f'/api/campaigns/drip/campaigns/{campaign.id}/'
        response = self.client.put(url, {
            'name': 'Tag Series',
            'trigger_type': 'tag_added',
            'steps': [{
                'step_number': 1,
                'action': 'send_email',
                'subject': 'Hello',
                'from_email': 'sender@example.com',
                'html_content': '<p>Hi</p>',
                'delay_days': 0,
                'delay_hours': 0,
            }],
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_enroll_by_email(self):
        from app.campaigns.models import DripCampaign, DripStep
        campaign = DripCampaign.objects.create(
            user=self.user,
            name='Welcome',
            trigger_type='manual',
            status='active',
        )
        DripStep.objects.create(
            drip_campaign=campaign,
            step_number=1,
            action='send_email',
            subject='Hi',
            from_email='sender@example.com',
            html_content='<p>Hello</p>',
        )
        url = f'/api/campaigns/drip/campaigns/{campaign.id}/enroll/'
        response = self.client.post(url, {'email': 'newuser@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['enrolled_count'], 1)


class AnalyticsAPITests(AuthSetupMixin, APITestCase):
    def test_dashboard_analytics_includes_charts(self):
        url = '/api/campaigns/analytics/dashboard/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('charts', response.data)
        self.assertIn('funnel', response.data['charts'])
        self.assertIn('engagement_breakdown', response.data['charts'])


class EmailValidationTests(APITestCase):
    """Domain-independent email validation for contact import."""

    VALID_DOMAINS = [
        'user@gmail.com',
        'contact@yahoo.com',
        'person@outlook.com',
        'legacy@hotmail.com',
        'apple@icloud.com',
        'secure@protonmail.com',
        'reader@rediffmail.com',
        'team@company.co.in',
        'sales@business.org.in',
        'info@startup.net.in',
        'hello@example.in',
        'dev@sub.domain.example.com',
        'contact@pegasos.in',
        'sales@microsoft.com',
        'info@business.org',
        'admin@gov.in',
        'team@startup.io',
        'hello@company.com',
    ]

    def test_valid_emails_from_all_providers(self):
        for email in self.VALID_DOMAINS:
            result = validate_contact_email(email)
            self.assertTrue(result['is_valid'], f'{email} should be valid: {result.get("error")}')

    def test_invalid_emails_rejected(self):
        invalid = ['not-an-email', 'missing@', '@nodomain.com', 'double@@at.com', 'spaces in@email.com']
        for email in invalid:
            result = validate_contact_email(email)
            self.assertFalse(result['is_valid'], f'{email} should be invalid')

    def test_domain_typo_suggests_correction(self):
        result = validate_contact_email('user@gmai.com')
        self.assertFalse(result['is_valid'])
        self.assertEqual(result['suggestion'], 'user@gmail.com')

    def test_duplicate_detection_in_batch(self):
        rows = [
            {'email': 'a@yahoo.com', 'name': 'A'},
            {'email': 'a@yahoo.com', 'name': 'A dup'},
            {'email': 'b@outlook.com', 'name': 'B'},
        ]
        summary = validate_email_batch(rows)
        self.assertEqual(summary['valid_count'], 2)
        self.assertEqual(summary['duplicate_count'], 1)


class ContactImportAPITests(AuthSetupMixin, APITestCase):
    def _upload_csv(self, content, url_name='contact-import'):
        upload = SimpleUploadedFile('contacts.csv', content.encode('utf-8'), content_type='text/csv')
        return self.client.post(reverse(url_name), {'file': upload}, format='multipart')

    def test_import_preview_accepts_multiple_domains(self):
        csv_content = (
            'email,name,is_subscribed\n'
            'one@gmail.com,One,true\n'
            'two@yahoo.com,Two,true\n'
            'three@company.co.in,Three,true\n'
        )
        upload = SimpleUploadedFile('preview.csv', csv_content.encode('utf-8'), content_type='text/csv')
        response = self.client.post(reverse('contact-import-preview'), {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        preview = response.data['preview']
        self.assertEqual(preview['valid_count'], 3)
        self.assertEqual(preview['invalid_count'], 0)

    def test_import_csv_creates_contacts(self):
        csv_content = (
            'email,name,is_subscribed\n'
            'import1@hotmail.com,User One,true\n'
            'import2@protonmail.com,User Two,true\n'
        )
        response = self._upload_csv(csv_content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        summary = response.data['summary']
        self.assertEqual(summary['created'], 2)
        self.assertTrue(Contact.objects.filter(user=self.user, email='import1@hotmail.com').exists())
        self.assertTrue(ContactImportLog.objects.filter(user=self.user).exists())

    def test_import_txt_file(self):
        txt_content = 'txt1@icloud.com\ntxt2@rediffmail.com\n'
        upload = SimpleUploadedFile('contacts.txt', txt_content.encode('utf-8'), content_type='text/plain')
        response = self.client.post(reverse('contact-import'), {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['summary']['created'], 2)

    def test_import_excel_xlsx_creates_contacts(self):
        import io

        openpyxl = __import__('openpyxl')
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(['email', 'name', 'is_subscribed'])
        sheet.append(['excel1@example.com', 'Excel One', 'true'])
        sheet.append(['excel2@example.com', 'Excel Two', 'true'])
        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)

        upload = SimpleUploadedFile(
            'contacts.xlsx',
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response = self.client.post(reverse('contact-import'), {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        summary = response.data['summary']
        self.assertEqual(summary['created'], 2)
        self.assertTrue(Contact.objects.filter(user=self.user, email='excel1@example.com').exists())

    def test_import_preview_accepts_excel(self):
        import io

        openpyxl = __import__('openpyxl')
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(['email', 'name'])
        sheet.append(['preview-excel@example.com', 'Preview User'])
        buffer = io.BytesIO()
        workbook.save(buffer)
        buffer.seek(0)

        upload = SimpleUploadedFile(
            'preview.xlsx',
            buffer.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response = self.client.post(reverse('contact-import-preview'), {'file': upload}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['preview']['valid_count'], 1)

    def test_import_skips_invalid_and_duplicates(self):
        csv_content = (
            'email,name\n'
            'valid@outlook.com,OK\n'
            'invalid-email,Bad\n'
            'valid@outlook.com,Dup\n'
        )
        response = self._upload_csv(csv_content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        summary = response.data['summary']
        self.assertEqual(summary['created'], 1)
        self.assertGreaterEqual(summary['skipped'], 2)

    def test_import_history_endpoint(self):
        csv_content = 'email,name\nhistory@test.in,History\n'
        self._upload_csv(csv_content)
        response = self.client.get(reverse('contact-import-history'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['history']), 1)
        self.assertEqual(response.data['history'][0]['filename'], 'contacts.csv')

    def test_import_allows_same_email_for_different_users(self):
        other_user = User.objects.create_user(
            username='other@example.com',
            email='other@example.com',
            password='TestPass123!',
        )
        Contact.objects.create(user=other_user, email='shared@example.com', name='Other User')

        csv_content = 'email,name\nshared@example.com,My Copy\nnew@example.com,New Person\n'
        response = self._upload_csv(csv_content)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        summary = response.data['summary']
        self.assertEqual(summary['created'], 2)
        self.assertTrue(Contact.objects.filter(user=self.user, email='shared@example.com').exists())
        self.assertTrue(Contact.objects.filter(user=other_user, email='shared@example.com').exists())


class CampaignDeliverabilityTests(APITestCase):
    @override_settings(SITE_URL='http://localhost:8000')
    def test_campaign_send_omits_localhost_tracking_links(self):
        from unittest.mock import patch

        from app.campaigns.models import CampaignContent, CampaignRecipient, OpenTracking
        from app.campaigns.services import CampaignService
        from app.emails.models import EmailSetting

        user = User.objects.create_user(
            username='campaign@example.com',
            email='campaign@example.com',
            password='TestPass123!',
        )
        EmailSetting.objects.create(
            user=user,
            provider='SendGrid',
            api_key='gAAAA-test-placeholder',
            from_email='campaign@example.com',
            domain_verified=True,
        )
        campaign = Campaign.objects.create(
            user=user,
            name='Spam test',
            subject='Hello',
            from_email='campaign@example.com',
            status='draft',
            inbox_priority=False,
        )
        CampaignContent.objects.create(
            campaign=campaign,
            html_content='<p>Hello <a href="https://pegasos.in">Visit</a></p>',
        )
        contact = Contact.objects.create(user=user, email='recipient@example.com')
        recipient = CampaignRecipient.objects.create(campaign=campaign, contact=contact, status='pending')
        open_tracking = OpenTracking.objects.create(campaign_recipient=recipient)

        captured = {}

        def fake_send_email(user, to_email, subject, html_content, **kwargs):
            captured['html_content'] = html_content
            captured['unsubscribe_url'] = kwargs.get('unsubscribe_url')
            return {'success': True}

        service = CampaignService()
        with patch('app.campaigns.services.send_email', side_effect=fake_send_email):
            result = service._send_email_with_tracking(campaign, recipient, open_tracking)

        self.assertTrue(result)
        self.assertNotIn('localhost', captured['html_content'])
        self.assertIn('https://pegasos.in', captured['html_content'])
        self.assertIsNone(captured['unsubscribe_url'])

    @override_settings(SITE_URL='https://emailmarketing.pegasos.in')
    def test_campaign_send_includes_public_site_url_tracking_and_analytics(self):
        from unittest.mock import patch
        from app.campaigns.models import CampaignContent, CampaignRecipient, OpenTracking
        from app.campaigns.services import CampaignService
        from app.emails.models import EmailSetting
        from app.campaigns.view.tracking_views import track_open

        user = User.objects.create_user(
            username='public_tracking@example.com',
            email='public_tracking@example.com',
            password='TestPass123!',
        )
        EmailSetting.objects.create(
            user=user,
            provider='SendGrid',
            api_key='gAAAA-test-placeholder',
            from_email='public_tracking@example.com',
            domain_verified=True,
        )
        campaign = Campaign.objects.create(
            user=user,
            name='Public tracking test',
            subject='Welcome',
            from_email='public_tracking@example.com',
            status='draft',
            inbox_priority=True,
        )
        CampaignContent.objects.create(
            campaign=campaign,
            html_content='<p>Hello <a href="https://pegasos.in">Visit</a></p>',
        )
        contact = Contact.objects.create(user=user, email='recipient@example.com')
        recipient = CampaignRecipient.objects.create(campaign=campaign, contact=contact, status='pending')
        open_tracking = OpenTracking.objects.create(campaign_recipient=recipient)

        captured = {}

        def fake_send_email(user, to_email, subject, html_content, **kwargs):
            captured['html_content'] = html_content
            captured['unsubscribe_url'] = kwargs.get('unsubscribe_url')
            return {'success': True}

        service = CampaignService()
        with patch('app.campaigns.services.send_email', side_effect=fake_send_email):
            result = service._send_email_with_tracking(campaign, recipient, open_tracking)

        self.assertTrue(result)
        self.assertIn('https://emailmarketing.pegasos.in/track/open/', captured['html_content'])
        self.assertIn('https://emailmarketing.pegasos.in/track/click/', captured['html_content'])
        self.assertIsNotNone(captured['unsubscribe_url'])

        # Simulate receiving open tracking GET request from recipient mail client
        response = self.client.get(f'/track/open/{open_tracking.tracking_id}/')
        self.assertEqual(response.status_code, 200)

        open_tracking.refresh_from_db()
        self.assertEqual(open_tracking.open_count, 1)

        from app.campaigns.analytics_service import AnalyticsService
        stats = AnalyticsService().get_campaign_stats(campaign.id)
        self.assertEqual(stats['engagement']['total_opened'], 1)
        self.assertEqual(stats['engagement']['unique_opens'], 1)

