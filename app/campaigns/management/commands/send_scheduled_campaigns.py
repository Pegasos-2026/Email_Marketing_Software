from django.core.management.base import BaseCommand
from django.utils import timezone

from app.campaigns.models import Campaign
from app.campaigns.scheduler import run_all_schedulers


class Command(BaseCommand):
    help = 'Process scheduled campaigns, drip enrollments, and webhooks'

    def handle(self, *args, **options):
        current_time = timezone.now()
        pending = Campaign.objects.filter(
            status='scheduled',
            scheduled_at__lte=current_time,
        ).count()
        if pending:
            self.stdout.write(f'Processing {pending} scheduled campaign(s)...')
        run_all_schedulers()
        self.stdout.write(self.style.SUCCESS('Scheduler tasks completed.'))
        self.stdout.write(f'Checked at {current_time.strftime("%Y-%m-%d %H:%M:%S")} UTC')
