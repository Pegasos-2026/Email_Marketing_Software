from django.utils import timezone
from .models import Campaign,WebhookEventLog,ABTest
from .services import CampaignService
from .drip_service import DripEngine, DripTriggerService,FollowUpService
from .ab_test_service import ABTestService
import logging

logger = logging.getLogger(__name__)


# -------------------------------------------------------
# YOUR EXISTING FUNCTION — Not touched at all
# -------------------------------------------------------
def run_scheduled_campaigns():
    """
    Sends all campaigns that are scheduled and due right now.
    This is your original function — nothing changed here.
    """
    current_time = timezone.now()
    campaigns = Campaign.objects.filter(
        status="scheduled",
        scheduled_at__lte=current_time
    )
    campaign_service = CampaignService()
    for campaign in campaigns:
        campaign.status = "sending"
        campaign.save()
        campaign_service.send_campaign(campaign.id)
        campaign.sent_at = timezone.now()
        campaign.save()


# -------------------------------------------------------
# NEW FUNCTION 1 — Drip campaign engine
# Processes all pending drip enrollments right now
# -------------------------------------------------------
def run_drip_campaigns():
    """
    Finds all active drip enrollments that are due right now
    and processes them — sends emails, checks conditions,
    moves to next step, or completes the campaign.
    """
    try:
        engine = DripEngine()
        count = engine.process_all_pending()
        logger.info(f"Drip scheduler: processed {count} enrollments")

    except Exception as e:
        logger.error(f"Drip scheduler error: {str(e)}")


# -------------------------------------------------------
# NEW FUNCTION 2 — Webhook event processor
# Processes any unhandled webhook events
# -------------------------------------------------------
def run_webhook_events():
    """
    Finds all webhook events that have not been processed yet
    and triggers the matching drip campaigns for each event.
    """
    try:
        trigger_service = DripTriggerService()

        # Find all unprocessed webhook events
        unprocessed_events = WebhookEventLog.objects.filter(
            is_processed=False
        ).select_related('contact', 'user')

        count = 0
        for webhook_log in unprocessed_events:
            try:
                trigger_service.handle_webhook_event(webhook_log)
                count += 1
            except Exception as e:
                logger.error(
                    f"Webhook event {webhook_log.id} error: {str(e)}"
                )

        logger.info(f"Webhook scheduler: processed {count} events")

    except Exception as e:
        logger.error(f"Webhook scheduler error: {str(e)}")

def run_inactive_check():
    """
    Checks all active enrollments for inactive contacts.
    If a contact has not received an email for X days
    and a CampaignEventRule exists for 'inactive_days',
    it triggers the follow-up campaign automatically.

    This runs once per day — not every minute.
    """
    try:
        follow_up_service = FollowUpService()
        follow_up_service.check_inactive_contacts()
        logger.info("Inactive check: done")

    except Exception as e:
        logger.error(f"Inactive check error: {str(e)}")
#NEW FUNCTION — A/B test winner check
# -------------------------------------------------------
def run_ab_test_checks():
    """
    Checks all running A/B tests every hour.

    For each running test:
    1. Check if test duration is complete
    2. If complete → decide winner automatically
    3. Send winner email to remaining contacts
    4. Mark test as completed

    Runs every hour — not every minute.
    """
    try:
        service = ABTestService()

        # Find all currently running A/B tests
        running_tests = ABTest.objects.filter(
            status='running'
        ).select_related('campaign', 'winner_variant')

        if not running_tests.exists():
            logger.info("A/B test check: no running tests found")
            return

        completed_count = 0
        for ab_test in running_tests:
            try:
                winner = service.check_winner(ab_test.id)
                if winner:
                    completed_count += 1
                    logger.info(
                        f"A/B test '{ab_test.name}' completed — "
                        f"winner: '{winner.name}'"
                    )

            except Exception as e:
                logger.error(
                    f"A/B test {ab_test.id} check error: {str(e)}"
                )

        logger.info(
            f"A/B test check: {completed_count} tests completed "
            f"out of {running_tests.count()} running"
        )

    except Exception as e:
        logger.error(f"A/B test scheduler error: {str(e)}")
# -------------------------------------------------------
# MASTER FUNCTION — Run everything together
# Call only this one function from cron or Celery
# -------------------------------------------------------
def run_all_schedulers():
    """
    Master function that runs all schedulers together.
    Call this one function instead of calling each separately.

    Order:
    1. run_scheduled_campaigns — your existing blast campaigns
    2. run_drip_campaigns      — drip enrollment processing
    3. run_webhook_events      — webhook trigger processing
    4.run_inactive_check       -inactive contacts followup
    5.run_ab_test_checks       -A/B test winner decision
    """

    logger.info(f"[{timezone.now()}] Running all schedulers...")

    # Step 1 — Your existing scheduled campaigns
    try:
        run_scheduled_campaigns()
        logger.info("Scheduled campaigns: done")
    except Exception as e:
        logger.error(f"Scheduled campaigns error: {str(e)}")

    # Step 2 — Drip campaign engine
    try:
        run_drip_campaigns()
        logger.info("Drip campaigns: done")
    except Exception as e:
        logger.error(f"Drip campaigns error: {str(e)}")

    # Step 3 — Webhook events
    try:
        run_webhook_events()
        logger.info("Webhook events: done")
    except Exception as e:
        logger.error(f"Webhook events error: {str(e)}")
    try:
        run_inactive_check()
        logger.info("Inactive check:done")
    except Exception as e:
        logger.error(f"Inactie check error:{str(e)}")
    try:
        run_ab_test_checks()
        logger.info("Inactive check:done")
    except Exception as e:
        logger.info(f"A/B test check error:{str(e)}")

    logger.info(f"[{timezone.now()}] All schedulers complete")


# -------------------------------------------------------
# CELERY TASK — If you use Celery
# Just add this task and update your Celery Beat schedule
# -------------------------------------------------------

"""
If you use Celery, add this to your tasks.py:

from celery import shared_task
from .scheduler import run_all_schedulers

@shared_task(name='run_all_schedulers')
def run_all_schedulers_task():
    run_all_schedulers()


Then add this to your settings.py:

CELERY_BEAT_SCHEDULE = {
    'run-all-schedulers': {
        'task': 'run_all_schedulers',
        'schedule': 60.0,       # Every 60 seconds
    },
}
"""


# -------------------------------------------------------
# CRON JOB — If you use cron instead of Celery
# -------------------------------------------------------

"""
If you use cron, add this to your crontab:

* * * * * cd /path/to/project && python manage.py shell -c "from campaigns.scheduler import run_all_schedulers; run_all_schedulers()"

This runs run_all_schedulers() every minute automatically.
"""