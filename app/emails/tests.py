from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from app.emails.models import EmailSetting
from app.emails.services import send_email


class AuthSetupMixin:
    def setUp(self):
        self.user = User.objects.create_user(
            username='sender@example.com',
            email='sender@example.com',
            password='TestPass123!',
        )
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')


class SendEmailAPITests(AuthSetupMixin, APITestCase):
    def test_send_email_requires_saved_smtp_password(self):
        EmailSetting.objects.create(
            user=self.user,
            provider='SMTP',
            smtp_host='smtp.gmail.com',
            smtp_port=587,
            smtp_user='sender@example.com',
            from_email='sender@example.com',
        )
        response = self.client.post(
            reverse('send-email'),
            {
                'to_email': 'recipient@example.com',
                'subject': 'Test',
                'html_content': '<p>Hello</p>',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('password', response.data['error'].lower())

    def test_send_email_returns_specific_error_message(self):
        response = self.client.post(
            reverse('send-email'),
            {
                'to_email': 'recipient@example.com',
                'subject': 'Test',
                'html_content': '<p>Hello</p>',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotEqual(response.data['error'], 'Email sending failed')


class EmailSettingSerializerTests(AuthSetupMixin, APITestCase):
    def test_update_settings_preserves_password_when_blank(self):
        setting = EmailSetting.objects.create(
            user=self.user,
            provider='SMTP',
            smtp_host='smtp.gmail.com',
            smtp_port=587,
            smtp_user='sender@example.com',
            smtp_password='gAAAA-test-placeholder',
            from_email='sender@example.com',
        )
        original_password = setting.smtp_password

        response = self.client.put(
            '/api/emails/settings/',
            {
                'provider': 'SMTP',
                'smtp_host': 'smtp.mail.example.com',
                'smtp_port': 587,
                'smtp_user': 'sender@example.com',
                'from_email': 'sender@example.com',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        setting.refresh_from_db()
        self.assertEqual(setting.smtp_password, original_password)
        self.assertEqual(setting.smtp_host, 'smtp.mail.example.com')

    def test_settings_response_includes_password_configured_flag(self):
        EmailSetting.objects.create(
            user=self.user,
            provider='SMTP',
            smtp_host='smtp.gmail.com',
            smtp_user='sender@example.com',
            smtp_password='gAAAA-test-placeholder',
            from_email='sender@example.com',
        )
        response = self.client.get('/api/emails/settings/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['smtp_password_configured'])


class SendEmailServiceTests(APITestCase):
    def test_bypass_list_management_uses_sendgrid_helper(self):
        from sendgrid.helpers.mail import Mail

        from app.emails.services import _configure_sendgrid_mail_settings

        message = Mail(
            from_email='sender@example.com',
            to_emails='recipient@example.com',
            subject='Test',
        )
        _configure_sendgrid_mail_settings(message, bypass_list_management=True)
        payload = message.get()
        self.assertEqual(
            payload['mail_settings']['bypass_list_management']['enable'],
            True,
        )

    def test_sendgrid_test_email_skips_domain_verification(self):
        user = User.objects.create_user(
            username='sg@example.com',
            email='sg@example.com',
            password='TestPass123!',
        )
        EmailSetting.objects.create(
            user=user,
            provider='SendGrid',
            api_key='gAAAA-test-placeholder',
            from_email='sg@example.com',
            domain_verified=False,
        )
        result = send_email(
            user=user,
            to_email='recipient@example.com',
            subject='Test',
            html_content='<p>Hello</p>',
            is_test=True,
        )
        self.assertFalse(result['success'])
        self.assertNotEqual(result.get('error'), 'Domain not verified')
