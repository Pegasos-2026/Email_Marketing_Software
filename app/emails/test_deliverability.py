from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from app.emails.deliverability import is_public_site_url


class PublicSiteUrlTests(SimpleTestCase):
    def test_localhost_is_not_public(self):
        self.assertFalse(is_public_site_url('http://localhost:8000'))
        self.assertFalse(is_public_site_url('http://127.0.0.1:8000'))

    def test_private_ip_is_not_public(self):
        self.assertFalse(is_public_site_url('http://192.168.1.10'))
        self.assertFalse(is_public_site_url('http://10.0.0.5'))

    def test_public_https_url_is_public(self):
        self.assertTrue(is_public_site_url('https://app.pegasos.in'))
        self.assertTrue(is_public_site_url('https://marketing.example.com/'))

    def test_format_list_unsubscribe_includes_mailto(self):
        from app.emails.deliverability import format_list_unsubscribe

        value = format_list_unsubscribe(mailto_email='sender@example.com')
        self.assertIn('mailto:sender@example.com', value)

    def test_normalize_email_html_wraps_fragment(self):
        from app.emails.deliverability import normalize_email_html

        wrapped = normalize_email_html('<p>Hello</p>')
        self.assertIn('<html>', wrapped.lower())
        self.assertIn('<body', wrapped.lower())
        self.assertIn('<p>Hello</p>', wrapped)


    def test_prepare_inbox_priority_message_personalizes_greeting(self):
        from app.emails.deliverability import prepare_inbox_priority_message

        subject, plain, html = prepare_inbox_priority_message(
            '<p>Hi {{name}},</p><p>Hello from Pegasos.</p>',
            '',
            'Rahul',
            'rahul@example.com',
            'Gunaseelan',
            'Update for {{name}}',
            recipient_id=7,
        )
        self.assertIn('Hi Rahul', plain)
        self.assertIn('Rahul', subject)

    def test_prepare_inbox_priority_message_keeps_common_body(self):
        from app.emails.deliverability import prepare_inbox_priority_message

        subject, plain, _html = prepare_inbox_priority_message(
            '',
            'Dear Sir/Madam,\n\nHello from Pegasos.',
            'Rahul',
            'rahul@example.com',
            'Gunaseelan',
            'Pegasos update',
            recipient_id=7,
        )
        self.assertEqual(subject[:14], 'Pegasos update')
        self.assertIn('Pegasos', plain)
        self.assertNotIn('Hi Rahul', plain)

    def test_resolve_inbox_priority_plain_prefers_html_signature(self):
        from app.emails.deliverability import resolve_inbox_priority_plain

        html = (
            '<p>Dear Sir/Madam,</p><p>Hello from Pegasos.</p>'
            '<p>Best Regards,<br>Anna<br>+91 6381464027<br>Website: www.pegasos.in</p>'
        )
        plain_field = 'Dear Sir/Madam,\n\nHello from Pegasos.\n\nRegards,\nGunaseelan'
        resolved = resolve_inbox_priority_plain(html, plain_field)
        self.assertIn('+91 6381464027', resolved)
        self.assertIn('www.pegasos.in', resolved)

    def test_rich_html_converts_to_plain_for_inbox_priority(self):
        from app.emails.deliverability import prepare_inbox_priority_message

        html = (
            '<table><tr><td><p>Dear Sir/Madam</p></td></tr></table>'
            + ('x' * 1600)
            + '<p>+91 6381464027<br>www.pegasos.in</p>'
        )
        subject, plain, rendered_html = prepare_inbox_priority_message(
            html,
            'short plain',
            'Rahul',
            'rahul@example.com',
            'Anna',
            'Pegasos update',
            recipient_id=3,
        )
        self.assertNotIn('<table', rendered_html.lower())
        self.assertIn('6381464027', plain)
        self.assertIn('Sir/Madam', plain)
        self.assertEqual(subject[:14], 'Pegasos update')


    def test_differentiate_plain_for_recipient(self):
        from app.emails.deliverability import differentiate_plain_for_recipient

        plain = 'Dear Sir/Madam,\n\nHello from Pegasos.\n\nRegards,\nAnna'
        a = differentiate_plain_for_recipient(plain, recipient_id=1, contact_email='a@gmail.com')
        b = differentiate_plain_for_recipient(plain, recipient_id=2, contact_email='b@gmail.com')
        self.assertNotEqual(a, b)
        self.assertIn('Sir/Madam', a)

    def test_resolve_campaign_reply_to_uses_from_on_personal_gmail(self):
        from app.emails.deliverability import resolve_campaign_reply_to

        resolved = resolve_campaign_reply_to(
            'gunaseelan@pegasos.in',
            'varshinii1407@gmail.com',
        )
        self.assertEqual(resolved, 'gunaseelan@pegasos.in')

    def test_resolve_campaign_reply_to_keeps_same_domain(self):
        from app.emails.deliverability import resolve_campaign_reply_to

        resolved = resolve_campaign_reply_to(
            'gunaseelan@pegasos.in',
            'sales@pegasos.in',
        )
        self.assertEqual(resolved, 'sales@pegasos.in')

    def test_single_recipient_skips_invisible_differentiation(self):
        from app.emails.deliverability import prepare_inbox_priority_message

        subject, plain, _html = prepare_inbox_priority_message(
            '<p>Hello from Pegasos.</p>',
            '',
            'Rahul',
            'rahul@example.com',
            'Guna',
            'Quick update',
            recipient_id=1,
            differentiate_recipients=False,
        )
        self.assertEqual(subject, 'Quick update')
        self.assertEqual(plain, 'Hello from Pegasos.')

    def test_unique_subject_for_recipient(self):
        from app.emails.deliverability import unique_subject_for_recipient

        self.assertNotEqual(
            unique_subject_for_recipient('Hello', 1),
            unique_subject_for_recipient('Hello', 2),
        )


    def test_apply_inbox_friendly_format_linkifies_urls(self):
        from app.emails.deliverability import apply_inbox_friendly_format

        _html, plain = apply_inbox_friendly_format(
            '',
            'Best Regards,\n\nGuna\n\nhttps://pegasos.in/',
            from_name='Guna',
        )
        html, _plain = apply_inbox_friendly_format(
            '',
            'Best Regards,\n\nGuna\n\nhttps://pegasos.in/',
            from_name='Guna',
        )
        self.assertIn('https://pegasos.in/', plain)
        self.assertIn('<a href="https://pegasos.in/"', html)
        self.assertNotIn('(https://pegasos.in/)', plain)

    def test_html_to_plain_text_uses_href_for_links(self):
        from app.emails.deliverability import html_to_plain_text

        plain = html_to_plain_text('<a href="https://pegasos.in/">www.pegasos.in</a>')
        self.assertIn('https://pegasos.in/', plain)
        self.assertNotIn('www.pegasos.in (', plain)

    def test_html_to_plain_text_preserves_signature_line_breaks(self):
        from app.emails.deliverability import html_to_plain_text

        html = (
            '<div style="margin:0;padding:0;line-height:1;">'
            'Best Regards,<br>Guna<br><a href="https://pegasos.in/">https://pegasos.in/</a>'
            '</div>'
        )
        plain = html_to_plain_text(html)
        self.assertIn('Best Regards,\nGuna\nhttps://pegasos.in/', plain)

    def test_sanitize_simple_inbox_html_preserves_inline_styles(self):
        from app.emails.deliverability import sanitize_simple_inbox_html

        html = (
            '<div style="margin:0;padding:0;line-height:1;">'
            'Best Regards,<br>Guna<br><a href="https://pegasos.in/">https://pegasos.in/</a>'
            '</div>'
        )
        sanitized = sanitize_simple_inbox_html(html)
        self.assertIn('style="margin:0;padding:0;line-height:1;"', sanitized)
        self.assertIn('<br>', sanitized)
        self.assertIn('href="https://pegasos.in/"', sanitized)

    def test_prepare_inbox_priority_message_preserves_inline_styles(self):
        from app.emails.deliverability import prepare_inbox_priority_message

        html = (
            '<p>Dear Sir/Madam,</p>'
            '<div style="margin:0;padding:0;line-height:1;">'
            'Best Regards,<br>Guna<br><a href="https://pegasos.in/">https://pegasos.in/</a>'
            '</div>'
        )
        _subject, plain, rendered_html = prepare_inbox_priority_message(
            html,
            '',
            'Rahul',
            'rahul@example.com',
            'Guna',
            'Hello',
            recipient_id=1,
        )
        self.assertIn('Best Regards', plain)
        self.assertIn('Guna', plain)
        self.assertIn('https://pegasos.in/', plain)
        self.assertIn('line-height:1', rendered_html)

    def test_sanitize_preserves_justify_alignment(self):
        from app.emails.deliverability import sanitize_simple_inbox_html

        sanitized = sanitize_simple_inbox_html('<p align="justify">Hello world</p>')
        self.assertIn('text-align:justify', sanitized)

    def test_is_prepared_campaign_html(self):
        from app.emails.deliverability import is_prepared_campaign_html, prepare_inbox_priority_message

        self.assertFalse(is_prepared_campaign_html('<p>Hello</p>'))
        _subject, _plain, html = prepare_inbox_priority_message(
            '<p>Dear Sir/Madam,</p>',
            '',
            'Rahul',
            'rahul@example.com',
            'Guna',
            'Hello',
            recipient_id=1,
        )
        self.assertTrue(is_prepared_campaign_html(html))

    def test_campaign_html_preserves_benefits_block_layout(self):
        from app.emails.deliverability import prepare_inbox_priority_message

        html = (
            '<p>Dear Sir/Madam,</p>'
            '<p align="justify">Intro paragraph.</p>'
            '<div style="margin:0;padding:0;line-height:1;">'
            '<b>Benefits:</b><br>'
            'High-Quality Data<br>'
            'Customized Solutions<br>'
            'Increased Efficiency<br>'
            'Enhanced ROI'
            '</div>'
            '<p align="justify">Closing paragraph.</p>'
        )
        _subject, _plain, rendered_html = prepare_inbox_priority_message(
            html,
            '',
            'Rahul',
            'rahul@example.com',
            'Guna',
            'Database services',
            recipient_id=1,
        )
        self.assertIn('line-height:1', rendered_html)
        self.assertIn('<b>Benefits:</b><br>', rendered_html)
        self.assertIn('High-Quality Data<br>', rendered_html)
        self.assertNotIn('High-Quality Data</p>', rendered_html)

    def test_sendgrid_inbox_send_preserves_prepared_html(self):
        from unittest.mock import MagicMock, patch

        from app.emails.services import _send_email_sendgrid

        prepared_html = (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
            '<body style="margin:0;padding:0;background:#fff;">'
            '<div style="margin:0;padding:0;line-height:1;">'
            '<b>Benefits:</b><br>High-Quality Data<br>Customized Solutions'
            '</div></body></html>'
        )
        plain = 'Benefits:\nHigh-Quality Data\nCustomized Solutions'
        setting = MagicMock()
        setting.get_api_key.return_value = 'test-key'
        setting.from_email = 'gunaseelan@pegasos.in'
        setting.from_name = 'Guna'
        setting.smtp_user = 'gunaseelan@pegasos.in'
        setting.domain_verified = True

        captured = {}

        def fake_send(message):
            captured['html'] = message.contents[1].content
            response = MagicMock()
            response.status_code = 202
            response.headers = {}
            return response

        with patch('app.emails.services.SendGridAPIClient') as mock_client, patch(
            'app.emails.services.sendgrid_is_ready_to_send', return_value=True
        ):
            mock_client.return_value.send.side_effect = fake_send
            result = _send_email_sendgrid(
                setting,
                'recipient@gmail.com',
                'Database services',
                prepared_html,
                plain_text_content=plain,
                from_email='gunaseelan@pegasos.in',
                from_name='Guna',
                reply_to='gunaseelan@pegasos.in',
                inbox_friendly=True,
            )

        self.assertTrue(result['success'])
        self.assertIn('line-height:1', captured['html'])
        self.assertIn('High-Quality Data<br>', captured['html'])
        self.assertNotIn('margin:0 0 14px', captured['html'])

    def test_inbox_plain_text_only_skips_html_part(self):
        from unittest.mock import MagicMock, patch

        from app.emails.services import _send_email_sendgrid

        setting = MagicMock()
        setting.get_api_key.return_value = 'test-key'
        setting.from_email = 'gunaseelan@pegasos.in'
        setting.from_name = 'Guna'
        setting.smtp_user = 'gunaseelan@pegasos.in'
        setting.domain_verified = True

        captured = {}

        def fake_send(message):
            captured['content_types'] = [part.mime_type for part in message.contents]
            response = MagicMock()
            response.status_code = 202
            response.headers = {}
            return response

        with patch('app.emails.services.SendGridAPIClient') as mock_client, patch(
            'app.emails.services.sendgrid_is_ready_to_send', return_value=True
        ):
            mock_client.return_value.send.side_effect = fake_send
            result = _send_email_sendgrid(
                setting,
                'recipient@gmail.com',
                'Quick update',
                '<p>Should not be sent</p>',
                plain_text_content='Hello from Guna.',
                from_email='gunaseelan@pegasos.in',
                from_name='Guna',
                reply_to='gunaseelan@pegasos.in',
                inbox_friendly=True,
                plain_text_only=True,
            )

        self.assertTrue(result['success'])
        self.assertEqual(captured['content_types'], ['text/plain'])


class EmailSettingsSiteUrlTests(TestCase):
    @override_settings(SITE_URL='http://localhost:8000')
    def test_settings_api_reports_localhost_site_url(self):
        user = User.objects.create_user(
            username='settings@example.com',
            email='settings@example.com',
            password='TestPass123!',
        )
        client = APIClient()
        refresh = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

        response = client.get('/api/emails/settings/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['site_url'], 'http://localhost:8000')
        self.assertFalse(response.data['site_url_public'])
