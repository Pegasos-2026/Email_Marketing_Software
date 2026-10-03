from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from .models import DripCampaign,DripStep,DripCondition,DripEnrollment,DripEmailLog,WebhookEventLog ,Contact,ContactList,OpenTracking,ClickTracking,StepFollowUpRule,CampaignEventRule,FollowUpTriggerLog

import hashlib
import re
import logging

logger = logging.getLogger(__name__)


class DripEnrollmentService:
    """
    Handles enrolling contacts into drip campaigns.
    This service decides WHO gets enrolled and WHEN.
    """

    def enroll_contact(self, contact, drip_campaign):
        """
        Enroll a single contact into a drip campaign.
        Skips if contact is already enrolled.
        """

        # Check if contact is already enrolled in this campaign
        existing = DripEnrollment.objects.filter(
            contact=contact,
            drip_campaign=drip_campaign,
        ).first()

        if existing:
            if existing.status == 'active':
                logger.info(f"{contact.email} is already enrolled in {drip_campaign.name}")
                return None
            if existing.status in ('completed', 'stopped'):
                logger.info(f"{contact.email} already finished {drip_campaign.name}")
                return None

        # Check if contact is subscribed
        if not contact.is_subscribed:
            logger.info(f"{contact.email} is unsubscribed — skipping enrollment")
            return None

        # Get the first step of the campaign
        first_step = DripStep.objects.filter(
            drip_campaign=drip_campaign
        ).order_by('step_number').first()

        if not first_step:
            logger.warning(f"Campaign {drip_campaign.name} has no steps — cannot enroll")
            return None

        # Calculate when to send the first email
        next_send_at = self._calculate_send_time(first_step)

        # Create the enrollment
        enrollment = DripEnrollment.objects.create(
            contact=contact,
            drip_campaign=drip_campaign,
            status='active',
            current_step=first_step,
            next_send_at=next_send_at,
        )

        logger.info(f"Enrolled {contact.email} into {drip_campaign.name}")
        return enrollment

    def enroll_list(self, contact_list, drip_campaign):
        """
        Enroll all contacts from a contact list into a drip campaign.
        """

        contacts = Contact.objects.filter(
            lists=contact_list,
            is_subscribed=True,
            user=drip_campaign.user
        )

        enrolled_count = 0
        for contact in contacts:
            result = self.enroll_contact(contact, drip_campaign)
            if result:
                enrolled_count += 1

        logger.info(f"Enrolled {enrolled_count} contacts from list '{contact_list.name}'")
        return enrolled_count

    def enroll_by_tag(self, tag, drip_campaign):
        """
        Enroll all contacts that have a specific tag.
        """

        contacts = Contact.objects.filter(
            tags=tag,
            is_subscribed=True,
            user=drip_campaign.user
        )

        enrolled_count = 0
        for contact in contacts:
            result = self.enroll_contact(contact, drip_campaign)
            if result:
                enrolled_count += 1

        logger.info(f"Enrolled {enrolled_count} contacts with tag '{tag.name}'")
        return enrolled_count

    def _calculate_send_time(self, step):
        """
        Calculate when this step's email should be sent.
        Adds delay_days and delay_hours to current time.
        """

        send_time = timezone.now()
        send_time += timedelta(days=step.delay_days, hours=step.delay_hours)
        return send_time


class DripConditionChecker:
    """
    Checks behavior-based conditions for drip campaigns.
    Decides YES or NO path based on contact's actions.
    """

    def check_condition(self, condition, enrollment):
        """
        Check if a condition is met for a contact.
        Returns True (YES path) or False (NO path).
        """

        condition_type = condition.condition_type

        if condition_type == 'email_opened':
            return self._check_email_opened(condition, enrollment)

        elif condition_type == 'email_clicked':
            return self._check_email_clicked(condition, enrollment)

        elif condition_type == 'tag_exists':
            return self._check_tag_exists(condition, enrollment)

        elif condition_type == 'webhook_event':
            return self._check_webhook_event(condition, enrollment)

        # Unknown condition type — default to NO path
        logger.warning(f"Unknown condition type: {condition_type}")
        return False

    def _check_email_opened(self, condition, enrollment):
        """
        Check if contact opened the email from a reference step.
        Uses OpenTracking model from existing code.
        """

        if not condition.reference_step:
            return False

        # Find the email log for the reference step
        email_log = DripEmailLog.objects.filter(
            enrollment=enrollment,
            step=condition.reference_step,
            status='sent'
        ).first()

        if not email_log or not email_log.open_tracking:
            return False

        # Check if open count is greater than 0
        return email_log.open_tracking.open_count > 0

    def _check_email_clicked(self, condition, enrollment):
        """
        Check if contact clicked any link in the reference step email.
        Uses existing ClickTracking model.
        """

        if not condition.reference_step:
            return False

        # Find the email log for the reference step
        email_log = DripEmailLog.objects.filter(
            enrollment=enrollment,
            step=condition.reference_step,
            status='sent'
        ).first()

        if not email_log:
            return False

        # Check click events using existing ClickTracking
        clicked = ClickTracking.objects.filter(
            campaign__isnull=True,  # Drip emails have no campaign
        ).exists()

        # Check via contact's click events on this step's email
        from .models import ClickEvent
        clicked = ClickEvent.objects.filter(
            campaign_recipient__contact=enrollment.contact,
        ).exists()

        return clicked

    def _check_tag_exists(self, condition, enrollment):
        """
        Check if the contact currently has a specific tag.
        """

        if not condition.tag:
            return False

        return enrollment.contact.tags.filter(
            id=condition.tag.id
        ).exists()

    def _check_webhook_event(self, condition, enrollment):
        """
        Check if a specific webhook event was received for this contact.
        Uses WebhookEventLog model.
        """

        if not condition.webhook_event_name:
            return False

        return WebhookEventLog.objects.filter(
            contact=enrollment.contact,
            event_name=condition.webhook_event_name,
            user=enrollment.drip_campaign.user
        ).exists()


class DripEmailSender:
    """Send drip step emails using the account email settings (SMTP or SendGrid)."""

    def send_step_email(self, enrollment, step):
        contact = enrollment.contact
        user = enrollment.drip_campaign.user

        try:
            from app.emails.services import send_email

            html_content = self._personalize_content(step.html_content, contact)
            subject = self._personalize_content(step.subject, contact)

            open_tracking = self._create_open_tracking_pixel(enrollment, step)
            from app.emails.deliverability import is_public_site_url

            site_url = settings.SITE_URL.rstrip('/')
            if is_public_site_url(site_url):
                tracking_pixel_url = f"{site_url}/track/open/{open_tracking.tracking_id}/"
                tracking_pixel = f'<img src="{tracking_pixel_url}" width="1" height="1" alt=""/>'
                if '</body>' in html_content:
                    html_content = html_content.replace('</body>', f'{tracking_pixel}</body>')
                else:
                    html_content += tracking_pixel

            result = send_email(user, contact.email, subject, html_content)
            if result.get('success'):
                email_log = DripEmailLog.objects.create(
                    enrollment=enrollment,
                    step=step,
                    contact=contact,
                    status='sent',
                    open_tracking=open_tracking,
                )
                logger.info(f"Email sent to {contact.email} for step {step.step_number}")
                return email_log

            raise Exception(result.get('error', 'Email delivery failed'))

        except Exception as e:
            DripEmailLog.objects.create(
                enrollment=enrollment,
                step=step,
                contact=contact,
                status='failed',
                error_message=str(e),
            )
            logger.error(f"Failed to send email to {contact.email}: {str(e)}")
            return None

    def _personalize_content(self, content, contact):
        """
        Replace placeholder variables with contact's actual data.
        e.g. {{name}} becomes 'Rahul'
        """

        if not content:
            return content

        content = content.replace('{{name}}', contact.name or 'there')
        content = content.replace('{{email}}', contact.email)

        return content

    def _create_open_tracking_pixel(self, enrollment, step):
        """
        Create a unique tracking ID for this email send.
        Returns the tracking UUID.
        """

        import uuid
        tracking = OpenTracking.objects.create(
            tracking_id=uuid.uuid4(),
            drip_enrollment=enrollment,
            drip_step=step,
        )
        return tracking

    def _add_click_tracking(self, html_content, enrollment):
        """
        Replace all URLs in email with tracked URLs.
        Reuses the same approach as your existing _add_click_tracking.
        """

        url_pattern = r'href=["\']([^"\']+)["\']'
        urls = re.findall(url_pattern, html_content)

        for url in urls:
            if url.startswith('http'):
                short_code = hashlib.md5(
                    f"drip-{enrollment.id}-{url}".encode()
                ).hexdigest()[:10]

                tracking_url = (
                    f"{settings.SITE_URL}/track/drip/click/"
                    f"{short_code}/{enrollment.contact.id}/"
                )

                html_content = html_content.replace(
                    f'href="{url}"',
                    f'href="{tracking_url}"'
                )

        return html_content
class FollowUpService:

    def __init__(self):
        self.enrollment_service = DripEnrollmentService()

    # ---------------------------------------------------
    # STEP LEVEL — Check after every email send
    # ---------------------------------------------------

    def check_step_follow_up_rules(self, enrollment, step):
        """
        Check all step-level follow-up rules after an email is sent.
        Called by DripEngine after every send_email step.

        Checks:
        - email_opened     → after check_after_days
        - email_clicked    → after check_after_days
        - email_not_opened → after check_after_days
        - email_not_clicked → after check_after_days
        """

        # Get all active follow-up rules for this step
        rules = StepFollowUpRule.objects.filter(
            step=step,
            is_active=True
        )

        for rule in rules:
            self._evaluate_step_rule(rule, enrollment, step)

    def _evaluate_step_rule(self, rule, enrollment, step):
        """
        Evaluate a single step-level IF/THEN rule.
        """

        # Check if this rule already triggered for this enrollment
        already_triggered = FollowUpTriggerLog.objects.filter(
            enrollment=enrollment,
            step_rule=rule
        ).exists()

        if already_triggered:
            logger.info(
                f"Step rule already triggered for {enrollment.contact.email} "
                f"— skipping"
            )
            return

        # Get the email log for this step
        email_log = DripEmailLog.objects.filter(
            enrollment=enrollment,
            step=step,
            status='sent'
        ).first()

        if not email_log:
            return

        # Check how many days since email was sent
        days_since_sent = (timezone.now() - email_log.sent_at).days

        trigger = rule.trigger
        condition_met = False

        # IF email_opened
        if trigger == 'email_opened':
            if email_log.open_tracking:
                condition_met = email_log.open_tracking.open_count > 0

        # IF email_clicked
        elif trigger == 'email_clicked':
            from .models import ClickEvent
            condition_met = ClickEvent.objects.filter(
                campaign_recipient__contact=enrollment.contact
            ).exists()

        # IF email_not_opened — check after X days
        elif trigger == 'email_not_opened':
            if days_since_sent >= rule.check_after_days:
                if email_log.open_tracking:
                    condition_met = email_log.open_tracking.open_count == 0
                else:
                    condition_met = True

        # IF email_not_clicked — check after X days
        elif trigger == 'email_not_clicked':
            if days_since_sent >= rule.check_after_days:
                from .models import ClickEvent
                clicked = ClickEvent.objects.filter(
                    campaign_recipient__contact=enrollment.contact
                ).exists()
                condition_met = not clicked

        # Condition met — trigger follow-up
        if condition_met:
            self._trigger_follow_up(
                enrollment=enrollment,
                follow_up_campaign=rule.follow_up_campaign,
                step_rule=rule,
                campaign_rule=None,
                stop_current=rule.stop_main_campaign
            )

    # ---------------------------------------------------
    # CAMPAIGN LEVEL — Check on events
    # ---------------------------------------------------

    def check_campaign_event_rules(self, enrollment, event_type, extra_data=None):
        """
        Check all campaign-level event rules when an event happens.

        Called when:
        - Webhook event received
        - Tag added to contact
        - Tag removed from contact
        - Contact inactive for X days

        event_type options:
        - 'webhook_event'  → extra_data = event_name string
        - 'tag_added'      → extra_data = tag object
        - 'tag_removed'    → extra_data = tag object
        - 'inactive_days'  → extra_data = days count
        """

        # Get all active event rules for this campaign
        rules = CampaignEventRule.objects.filter(
            campaign=enrollment.drip_campaign,
            trigger=event_type,
            is_active=True
        )

        for rule in rules:
            self._evaluate_campaign_rule(
                rule, enrollment, event_type, extra_data
            )

    def _evaluate_campaign_rule(self, rule, enrollment, event_type, extra_data):
        """
        Evaluate a single campaign-level IF/THEN rule.
        """

        # Duplicate trigger check
        already_triggered = FollowUpTriggerLog.objects.filter(
            enrollment=enrollment,
            campaign_rule=rule
        ).exists()

        if already_triggered:
            logger.info(
                f"Campaign rule already triggered for "
                f"{enrollment.contact.email} — skipping"
            )
            return

        condition_met = False

        # IF webhook_event
        if event_type == 'webhook_event':
            condition_met = (
                rule.webhook_event_name and
                extra_data == rule.webhook_event_name
            )

        # IF tag_added
        elif event_type == 'tag_added':
            condition_met = (
                rule.tag and
                extra_data and
                rule.tag.id == extra_data.id
            )

        # IF tag_removed
        elif event_type == 'tag_removed':
            condition_met = (
                rule.tag and
                extra_data and
                rule.tag.id == extra_data.id
            )

        # IF inactive_days
        elif event_type == 'inactive_days':
            condition_met = (
                rule.inactive_days and
                extra_data >= rule.inactive_days
            )

        # Condition met — trigger follow-up
        if condition_met:
            self._trigger_follow_up(
                enrollment=enrollment,
                follow_up_campaign=rule.follow_up_campaign,
                step_rule=None,
                campaign_rule=rule,
                stop_current=rule.stop_current_campaign
            )

    # ---------------------------------------------------
    # CORE — Trigger the actual follow-up
    # ---------------------------------------------------

    def _trigger_follow_up(
        self,
        enrollment,
        follow_up_campaign,
        step_rule,
        campaign_rule,
        stop_current
    ):
        """
        Actually trigger a follow-up campaign for a contact.

        Steps:
        1. Enroll contact in follow-up campaign
        2. Log the trigger
        3. Stop main campaign if needed
        """

        contact = enrollment.contact

        logger.info(
            f"Triggering follow-up '{follow_up_campaign.name}' "
            f"for {contact.email}"
        )

        # Step 1 — Enroll contact in follow-up campaign
        follow_up_enrollment = self.enrollment_service.enroll_contact(
            contact=contact,
            drip_campaign=follow_up_campaign
        )

        if not follow_up_enrollment:
            logger.info(
                f"{contact.email} already enrolled in "
                f"'{follow_up_campaign.name}' — skipping"
            )
            return

        # Step 2 — Log this trigger (for duplicate prevention)
        FollowUpTriggerLog.objects.create(
            enrollment=enrollment,
            step_rule=step_rule,
            campaign_rule=campaign_rule,
            follow_up_campaign=follow_up_campaign,
            follow_up_enrollment=follow_up_enrollment,
        )

        # Step 3 — Stop main campaign if rule says so
        if stop_current:
            enrollment.status = 'stopped'
            enrollment.save()
            logger.info(
                f"Main campaign stopped for {contact.email} "
                f"— follow-up started"
            )

        logger.info(
            f"Follow-up '{follow_up_campaign.name}' "
            f"successfully triggered for {contact.email}"
        )

    def check_inactive_contacts(self):
        """
        Find contacts who have been inactive for X days
        and trigger matching campaign rules.

        Called by scheduler every day.
        """

        # Get all active enrollments
        active_enrollments = DripEnrollment.objects.filter(
            status='active'
        ).select_related('contact', 'drip_campaign')

        for enrollment in active_enrollments:

            # Find campaign-level inactive_days rules
            inactive_rules = CampaignEventRule.objects.filter(
                campaign=enrollment.drip_campaign,
                trigger='inactive_days',
                is_active=True
            )

            if not inactive_rules.exists():
                continue

            # Calculate how many days since last email
            last_log = DripEmailLog.objects.filter(
                enrollment=enrollment
            ).order_by('-sent_at').first()

            if not last_log:
                continue

            days_inactive = (timezone.now() - last_log.sent_at).days

            # Check each inactive rule
            self.check_campaign_event_rules(
                enrollment=enrollment,
                event_type='inactive_days',
                extra_data=days_inactive
            )

class DripEngine:
    """
    Main engine that processes drip campaign enrollments.
    This is the brain of the drip system.
    Called by the scheduler every minute.
    """

    def __init__(self):
        self.condition_checker = DripConditionChecker()
        self.email_sender = DripEmailSender()
        self.enrollment_service = DripEnrollmentService()
        self.follow_up_service=FollowUpService()

    def process_all_pending(self):
        """
        Find all enrollments that need to be processed right now.
        Called by the scheduler every minute.
        """

        # Find all active enrollments where next_send_at has passed
        pending_enrollments = DripEnrollment.objects.filter(
            status='active',
            next_send_at__lte=timezone.now()
        ).select_related(
            'contact',
            'drip_campaign',
            'current_step',
        )

        processed_count = 0
        for enrollment in pending_enrollments:
            try:
                self.process_enrollment(enrollment)
                processed_count += 1
            except Exception as e:
                logger.error(
                    f"Error processing enrollment {enrollment.id}: {str(e)}"
                )

        logger.info(f"Processed {processed_count} enrollments")
        return processed_count

    def process_enrollment(self, enrollment):
        """
        Process a single enrollment — execute the current step.
        """

        current_step = enrollment.current_step

        if not current_step:
            # No step found — mark as completed
            self._complete_enrollment(enrollment)
            return

        action = current_step.action

        # Execute action based on step type
        if action == 'send_email':
            self._handle_send_email(enrollment, current_step)

        elif action == 'wait':
            # Just wait — move to next step
            self._move_to_next_step(enrollment, current_step)

        elif action == 'condition':
            self._handle_condition(enrollment, current_step)

        elif action == 'add_tag':
            self._handle_add_tag(enrollment, current_step)

        elif action == 'remove_tag':
            self._handle_remove_tag(enrollment, current_step)

        elif action == 'end':
            self._complete_enrollment(enrollment)

    def _handle_send_email(self, enrollment, step):
        """
        Send email and then move to the next step.
        """

        # Send the email
        result = self.email_sender.send_step_email(enrollment, step)

        if result:
            self.follow_up_service.check_step_follow_up_rules(enrollment=enrollment,step=step)
            # Email sent successfully — move to next step
            self._move_to_next_step(enrollment, step)
        else:
            # Email failed — mark enrollment as failed
            enrollment.status = 'failed'
            enrollment.save()
            logger.error(
                f"Enrollment {enrollment.id} failed at step {step.step_number}"
            )

    def _handle_condition(self, enrollment, step):
        """
        Check a behavior-based condition and route to YES or NO path.
        """

        try:
            condition = step.condition
        except DripCondition.DoesNotExist:
            # No condition found — move to next step normally
            self._move_to_next_step(enrollment, step)
            return

        # Check if condition is met
        condition_met = self.condition_checker.check_condition(
            condition,
            enrollment
        )

        if condition_met:
            # YES path
            next_step = condition.yes_next_step
            logger.info(
                f"Condition MET for {enrollment.contact.email} "
                f"— taking YES path"
            )
        else:
            # NO path
            next_step = condition.no_next_step
            logger.info(
                f"Condition NOT MET for {enrollment.contact.email} "
                f"— taking NO path"
            )

        if next_step:
            # Move to the condition's chosen step
            next_send_at = self.enrollment_service._calculate_send_time(
                next_step
            )
            enrollment.current_step = next_step
            enrollment.next_send_at = next_send_at
            enrollment.save()
        else:
            # No next step — campaign complete
            self._complete_enrollment(enrollment)

    def _handle_add_tag(self, enrollment, step):
        """
        Add a tag to the contact and move to next step.
        """

        if step.tag:
            enrollment.contact.tags.add(step.tag)
            logger.info(
                f"Added tag '{step.tag.name}' to {enrollment.contact.email}"
            )
            self.follow_up_service.check_campaign_event_rules(enrollment=enrollment,event_type='tag_added',extra_data=step.tag)

        self._move_to_next_step(enrollment, step)

    def _handle_remove_tag(self, enrollment, step):
        """
        Remove a tag from the contact and move to next step.
        """

        if step.tag:
            enrollment.contact.tags.remove(step.tag)
            logger.info(
                f"Removed tag '{step.tag.name}' from {enrollment.contact.email}"
            )
            self.follow_up_service.check_campaign_event_rules(enrollment=enrollment,event_type='tag_removed',extra_data=step.tag)

        self._move_to_next_step(enrollment, step)

    def _move_to_next_step(self, enrollment, current_step):
        """
        Move the enrollment to the next step in sequence.
        If no next step exists, mark campaign as completed.
        """

        # Find the next step by step_number
        next_step = DripStep.objects.filter(
            drip_campaign=enrollment.drip_campaign,
            step_number__gt=current_step.step_number
        ).order_by('step_number').first()

        if next_step:
            # Calculate when to send next step
            next_send_at = self.enrollment_service._calculate_send_time(
                next_step
            )
            enrollment.current_step = next_step
            enrollment.next_send_at = next_send_at
            enrollment.save()

            logger.info(
                f"{enrollment.contact.email} moved to step "
                f"{next_step.step_number}"
            )
        else:
            # No more steps — campaign is complete
            self._complete_enrollment(enrollment)

    def _complete_enrollment(self, enrollment):
        """
        Mark an enrollment as completed.
        """

        enrollment.status = 'completed'
        enrollment.completed_at = timezone.now()
        enrollment.next_send_at = None
        enrollment.save()

        logger.info(
            f"Campaign '{enrollment.drip_campaign.name}' "
            f"completed for {enrollment.contact.email}"
        )


class DripTriggerService:
    """
    Handles automatic triggers that start drip campaigns.
    Called when contacts are added, tags are applied, or webhooks arrive.
    """

    def __init__(self):
        self.enrollment_service = DripEnrollmentService()
        self.follow_up_service=FollowUpService()

    def handle_contact_added(self, contact, user):
        """
        When a new contact is added, check if any campaign
        should start automatically for them.
        """

        # Find all active campaigns with trigger = contact_added
        campaigns = DripCampaign.objects.filter(
            user=user,
            status='active',
            trigger_type='contact_added'
        )

        for campaign in campaigns:
            self.enrollment_service.enroll_contact(contact, campaign)

    def handle_tag_added(self, contact, tag, user):
        """
        When a tag is added to a contact, check if any campaign
        should start for that tag.
        """

        # Find active campaigns triggered by this specific tag
        campaigns = DripCampaign.objects.filter(
            user=user,
            status='active',
            trigger_type='tag_added',
            trigger_tag=tag
        )

        for campaign in campaigns:
            self.enrollment_service.enroll_contact(contact, campaign)
            active_enrollments=DripEnrollment.objects.filter(contact=contact,status='active')
        for enrollment in active_enrollments:
            self.follow_up_service.check_campaign_event_rules(enrollment=enrollment,event_type='tag_added',extra_data=tag)
    def handle_webhook_event(self,webhook_log):
        """When a webhook event arrives,check if any campaign should start based on the event name"""
        #finf active campaigns triggered by this webhook event
        campaigns=DripCampaign.objects.filter(user=webhook_log.user,status='active',trigger_type='webhook',trigger_webhook_event=webhook_log.event_name)
        for campaign in campaigns:
            if webhook_log.contact:
                self.enrollment_service.enroll_contact(webhook_log.contact,campaign)
        if webhook_log.contact:
            active_enrollments=DripEnrollment.objects.filter(contact=webhook_log.contact,status='active')
            for enrollment in active_enrollments:
                self.follow_up_service.check_campaign_event_rules(enrollment=enrollment,event_type='webhook_event',extra_data=webhook_log.event_name)
        #Mark webhook event as processed
        webhook_log.is_processed=True
        webhook_log.processed_at=timezone.now()
        webhook_log.save()