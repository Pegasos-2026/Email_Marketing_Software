from django.utils import timezone
from django.conf import settings
from django.db.models import F
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from .models import (
    Campaign, CampaignRecipient, EmailEvent,
    OpenTracking, ClickTracking, Contact,
)
from .models import ABTest, ABTestVariant, ABTestRecipient
from .services import CampaignService
import random
import hashlib
import re
import logging

logger = logging.getLogger(__name__)


class ABTestService:
    """
    Handles all A/B testing logic for normal campaigns.

    Flow:
    1. Business owner A/B test setup karta hai
    2. run_test() — contacts split hote hain, variants bheje jaate hain
    3. Scheduler check_winner() call karta hai after test_duration_hours
    4. Winner decide hota hai
    5. send_winner_to_remaining() — baaki contacts ko winner milta hai
    """

    def __init__(self):
        self.sg = SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)

    # ---------------------------------------------------
    # STEP 1 — Test Run Karo
    # ---------------------------------------------------

    def run_test(self, ab_test_id):
        """
        A/B test start karo.

        Steps:
        1. Campaign ke recipients lo
        2. Test percentage ke hisaab se contacts split karo
        3. Har variant ko uske contacts bhejo
        4. Test status = running karo
        """

        ab_test = ABTest.objects.get(id=ab_test_id)
        campaign = ab_test.campaign

        # Validation
        if ab_test.status != 'draft':
            raise ValueError(f"Test is already {ab_test.status}")

        variants = ab_test.variants.all()
        if not variants.exists():
            raise ValueError("Test mein kam se kam 2 variants hone chahiye")

        if variants.count() < 2:
            raise ValueError("A/B test ke liye minimum 2 variants chahiye")

        # Variant percentage check — total 100 hona chahiye
        total_percentage = sum(v.recipient_percentage for v in variants)
        if total_percentage != 100:
            raise ValueError(
                f"Variants ka total percentage 100 hona chahiye — "
                f"abhi {total_percentage} hai"
            )

        # Saare pending recipients lo
        all_recipients = list(
            CampaignRecipient.objects.filter(
                campaign=campaign,
                status='pending'
            ).select_related('contact')
        )

        if not all_recipients:
            raise ValueError("No pending recipients found")

        # Test mein kitne contacts jayenge
        test_count = int(
            len(all_recipients) * (ab_test.test_percentage / 100)
        )

        # Random shuffle karo — fair split ke liye
        random.shuffle(all_recipients)

        # Test contacts aur remaining contacts alag karo
        test_recipients = all_recipients[:test_count]
        remaining_recipients = all_recipients[test_count:]

        # Variants mein contacts split karo
        self._split_and_send_variants(ab_test, variants, test_recipients)

        # Remaining contacts ko hold karo — winner aane par milega
        # Unka status 'pending' hi rahega for now
        logger.info(
            f"A/B test started: {len(test_recipients)} test contacts, "
            f"{len(remaining_recipients)} waiting for winner"
        )

        # Test status update karo
        ab_test.status = 'running'
        ab_test.started_at = timezone.now()
        ab_test.save()

        return {
            'test_recipients': len(test_recipients),
            'remaining_recipients': len(remaining_recipients),
            'variants': variants.count(),
        }

    def _split_and_send_variants(self, ab_test, variants, test_recipients):
        """
        Test recipients ko variants mein split karo
        aur har variant ka email bhejo.
        """

        campaign = ab_test.campaign
        total = len(test_recipients)
        start_index = 0

        for variant in variants:

            # Is variant ko kitne contacts milenge
            variant_count = int(total * (variant.recipient_percentage / 100))
            end_index = start_index + variant_count

            # Last variant ko baaki sab contacts
            if variant == list(variants)[-1]:
                end_index = total

            variant_recipients = test_recipients[start_index:end_index]
            start_index = end_index

            # Har contact ko yeh variant bhejo
            sent_count = 0
            for campaign_recipient in variant_recipients:
                success = self._send_variant_email(
                    campaign=campaign,
                    campaign_recipient=campaign_recipient,
                    variant=variant,
                    ab_test=ab_test,
                )
                if success:
                    sent_count += 1

            # Variant ka sent count update karo
            variant.sent_count = sent_count
            variant.save(update_fields=['sent_count'])

            logger.info(
                f"Variant '{variant.name}': "
                f"{sent_count}/{len(variant_recipients)} sent"
            )

    def _send_variant_email(self, campaign, campaign_recipient, variant, ab_test):
        """
        Ek contact ko variant email bhejo.
        Reuses aapki existing tracking setup.
        """

        contact = campaign_recipient.contact

        try:
            # Content decide karo
            # Variant ka content hai toh use karo, warna campaign ka
            if variant.html_content:
                html_content = variant.html_content
            else:
                html_content = campaign.content.html_content

            # Personalize karo
            html_content = html_content.replace(
                '{{name}}', contact.name or 'there'
            )
            html_content = html_content.replace('{{email}}', contact.email)

            # Open tracking — aapka existing model use karo
            open_tracking = OpenTracking.objects.create(
                campaign_recipient=campaign_recipient
            )

            # Tracking pixel add karo
            tracking_pixel_url = (
                f"{settings.SITE_URL}/track/open/"
                f"{open_tracking.tracking_id}/"
            )
            tracking_pixel = (
                f'<img src="{tracking_pixel_url}" '
                f'width="1" height="1" alt=""/>'
            )

            if '</body>' in html_content:
                html_content = html_content.replace(
                    '</body>', f'{tracking_pixel}</body>'
                )
            else:
                html_content += tracking_pixel

            # Click tracking add karo
            html_content = self._add_click_tracking(
                html_content, campaign, campaign_recipient
            )

            # Subject — variant ka subject use karo
            subject = variant.subject

            # From name — variant ka hai toh use karo, warna campaign ka
            from_name = variant.from_name or campaign.from_name or ''

            # Email bhejo
            message = Mail(
                from_email=Email(campaign.from_email, from_name),
                to_emails=To(contact.email),
                subject=subject,
                html_content=Content("text/html", html_content),
            )

            if campaign.reply_to:
                message.reply_to = Email(campaign.reply_to)

            response = self.sg.send(message)

            if response.status_code in [200, 202]:

                # Recipient status update karo
                campaign_recipient.status = 'sent'
                campaign_recipient.sent_at = timezone.now()
                campaign_recipient.save()

                # ABTestRecipient record banao
                ABTestRecipient.objects.create(
                    ab_test=ab_test,
                    variant=variant,
                    campaign_recipient=campaign_recipient,
                    contact=contact,
                )

                # Email event log karo
                EmailEvent.objects.create(
                    campaign_recipient=campaign_recipient,
                    event_type='sent',
                )

                return True

            else:
                raise Exception(f"SendGrid error: {response.status_code}")

        except Exception as e:
            campaign_recipient.status = 'failed'
            campaign_recipient.error_message = str(e)
            campaign_recipient.save()
            logger.error(f"Variant email failed for {contact.email}: {str(e)}")
            return False

    def _add_click_tracking(self, html_content, campaign, recipient):
        """
        Aapki existing click tracking logic — same approach.
        """

        url_pattern = r'href=["\']([^"\']+)["\']'
        urls = re.findall(url_pattern, html_content)

        for url in urls:
            if url.startswith('http'):
                short_code = hashlib.md5(
                    f"{campaign.id}-{url}".encode()
                ).hexdigest()[:10]

                click_tracking, created = ClickTracking.objects.get_or_create(
                    campaign=campaign,
                    original_url=url,
                    defaults={'short_code': short_code}
                )

                tracking_url = (
                    f"{settings.SITE_URL}/track/click/"
                    f"{click_tracking.short_code}/{recipient.id}/"
                )

                html_content = html_content.replace(
                    f'href="{url}"',
                    f'href="{tracking_url}"'
                )

        return html_content

    # ---------------------------------------------------
    # STEP 2 — Winner Check Karo
    # ---------------------------------------------------

    def check_winner(self, ab_test_id):
        """
        Check karo ki test duration complete hua?
        Agar hua toh winner decide karo.

        Called by scheduler every hour.
        """

        ab_test = ABTest.objects.get(id=ab_test_id)

        # Sirf running tests check karo
        if ab_test.status != 'running':
            return None

        # Test duration complete hua?
        if not ab_test.started_at:
            return None

        from datetime import timedelta
        test_end_time = ab_test.started_at + timedelta(
            hours=ab_test.test_duration_hours
        )

        if timezone.now() < test_end_time:
            hours_remaining = (test_end_time - timezone.now()).seconds // 3600
            logger.info(
                f"Test '{ab_test.name}' — "
                f"{hours_remaining} hours remaining"
            )
            return None

        # Test duration complete — winner decide karo
        winner = self._decide_winner(ab_test)

        if winner:
            ab_test.winner_variant = winner
            ab_test.status = 'completed'
            ab_test.completed_at = timezone.now()
            ab_test.save()

            logger.info(
                f"Winner decided: '{winner.name}' "
                f"for test '{ab_test.name}'"
            )

            # Winner ko remaining contacts ko bhejo
            self.send_winner_to_remaining(ab_test)

        return winner

    def _decide_winner(self, ab_test):
        """
        Winner criteria ke hisaab se winner decide karo.
        """

        variants = ab_test.variants.all()

        # Pehle stats update karo
        for variant in variants:
            self._update_variant_stats(variant)

        winner_criteria = ab_test.winner_criteria

        if winner_criteria == 'open_rate':
            winner = max(variants, key=lambda v: v.open_rate)

        elif winner_criteria == 'click_rate':
            winner = max(variants, key=lambda v: v.click_rate)

        elif winner_criteria == 'manual':
            # Manual selection — winner decide nahi hoga automatically
            logger.info(
                f"Test '{ab_test.name}' is manual — "
                f"business owner will decide winner"
            )
            return None

        else:
            winner = max(variants, key=lambda v: v.open_rate)

        logger.info(
            f"Winner: '{winner.name}' — "
            f"Open Rate: {winner.open_rate}% | "
            f"Click Rate: {winner.click_rate}%"
        )

        return winner

    def _update_variant_stats(self, variant):
        """
        Variant ke open/click stats update karo
        using existing OpenTracking and ClickTracking models.
        """

        from .models import OpenTracking, ClickEvent

        # Open count — ABTestRecipient se connected OpenTracking check karo
        open_count = OpenTracking.objects.filter(
            campaign_recipient_ab_test_recipient_variant=variant,
            open_count__gt=0
        ).count()

        # Click count
        click_count = ClickEvent.objects.filter(
            campaign_recipient_ab_test_recipient_variant=variant
        ).values('campaign_recipient').distinct().count()

        variant.open_count = open_count
        variant.click_count = click_count
        variant.save(update_fields=['open_count', 'click_count'])

        variant.update_stats()

    # ---------------------------------------------------
    # STEP 3 — Winner Remaining Contacts Ko Bhejo
    # ---------------------------------------------------

    def send_winner_to_remaining(self, ab_test):
        """
        Winner decide hone ke baad baaki contacts ko
        winner variant ka email bhejo.

        Remaining contacts = jo test mein nahi the
        (test_percentage < 100 tha toh)
        """

        campaign = ab_test.campaign
        winner_variant = ab_test.winner_variant

        if not winner_variant:
            logger.warning(f"No winner variant for test '{ab_test.name}'")
            return 0

        # Jo contacts abhi bhi pending hain
        # (test mein nahi the)
        already_tested_contact_ids = ABTestRecipient.objects.filter(
            ab_test=ab_test
        ).values_list('contact_id', flat=True)

        remaining_recipients = CampaignRecipient.objects.filter(
            campaign=campaign,
            status='pending'
        ).exclude(
            contact_id__in=already_tested_contact_ids
        ).select_related('contact')

        sent_count = 0
        for recipient in remaining_recipients:
            success = self._send_variant_email(
                campaign=campaign,
                campaign_recipient=recipient,
                variant=winner_variant,
                ab_test=ab_test,
            )
            if success:
                sent_count += 1

                # Mark karo ki is contact ko winner mila
                ABTestRecipient.objects.filter(
                    ab_test=ab_test,
                    contact=recipient.contact
                ).update(received_winner=True)

        logger.info(
            f"Winner '{winner_variant.name}' sent to "
            f"{sent_count} remaining contacts"
        )

        # Campaign status update karo
        campaign.status = 'sent'
        campaign.sent_at = timezone.now()
        campaign.save()

        return sent_count

    # ---------------------------------------------------
    # MANUAL WINNER SELECTION
    # ---------------------------------------------------

    def set_manual_winner(self, ab_test_id, variant_id):
        """
        Business owner manually winner select kare.
        Winner criteria = 'manual' hone par use hota hai.
        """

        ab_test = ABTest.objects.get(id=ab_test_id)
        winner_variant = ABTestVariant.objects.get(
            id=variant_id,
            ab_test=ab_test
        )

        if ab_test.status != 'running':
            raise ValueError(
                f"Test is {ab_test.status} — "
                f"only running tests can have winner set"
            )

        ab_test.winner_variant = winner_variant
        ab_test.status = 'completed'
        ab_test.completed_at = timezone.now()
        ab_test.save()

        # Winner ko remaining contacts ko bhejo
        self.send_winner_to_remaining(ab_test)

        logger.info(
            f"Manual winner set: '{winner_variant.name}' "
            f"for test '{ab_test.name}'"
        )

        return winner_variant

    # ---------------------------------------------------
    # STATS HELPER
    # ---------------------------------------------------

    def get_test_results(self, ab_test_id):
        """
        Test ke current results return karo.
        Dashboard pe dikhane ke liye.
        """

        ab_test = ABTest.objects.get(id=ab_test_id)
        variants = ab_test.variants.all()

        # Stats update karo
        for variant in variants:
            self._update_variant_stats(variant)

        results = []
        for variant in variants:
            results.append({
                'variant_id': variant.id,
                'name': variant.name,
                'subject': variant.subject,
                'sent_count': variant.sent_count,
                'open_count': variant.open_count,
                'click_count': variant.click_count,
                'open_rate': variant.open_rate,
                'click_rate': variant.click_rate,
                'is_winner': (
                    ab_test.winner_variant and
                    ab_test.winner_variant.id == variant.id
                ),
            })

        return {
            'test_name': ab_test.name,
            'status': ab_test.status,
            'winner_criteria': ab_test.winner_criteria,
            'started_at': ab_test.started_at,
            'completed_at': ab_test.completed_at,
            'variants': results,
        }