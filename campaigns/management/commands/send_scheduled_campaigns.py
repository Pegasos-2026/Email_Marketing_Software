from django.core.management.base import BaseCommand
from django.utils import timezone
from campaigns.models import Campaign
from campaigns.services import CampaignService
from datetime import timedelta


class Command(BaseCommand):
    help = 'Send campaigns that are scheduled for the current time'

    def add_arguments(self, parser):
        parser.add_argument(
            '--check-interval',
            type=int,
            default=5,
            help='Check for scheduled campaigns within N minutes (default: 5)',
        )

    def handle(self, *args, **options):
        check_interval = options['check_interval']
        current_time = timezone.now()
        past_time = current_time - timedelta(minutes=check_interval)

        # Find all campaigns that should have been sent
        campaigns = Campaign.objects.filter(
            status='scheduled',
            scheduled_at__isnull=False,
            scheduled_at__lte=current_time,
            scheduled_at__gte=past_time
        ).order_by('scheduled_at')

        if not campaigns.exists():
            self.stdout.write(self.style.SUCCESS('No scheduled campaigns to send.'))
            return

        service = CampaignService()
        sent_count = 0
        failed_count = 0

        for campaign in campaigns:
            try:
                self.stdout.write(f'Sending campaign: {campaign.name}')
                
                # Send the campaign
                result = service.send_campaign(campaign.id)
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Campaign "{campaign.name}" sent successfully. '
                        f'Total: {result["total"]}, Success: {result["success"]}, Failed: {result["failed"]}'
                    )
                )
                sent_count += 1
            except Exception as e:
                failed_count += 1
                # Mark campaign as failed status
                campaign.status = 'draft'
                campaign.save()
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Failed to send campaign "{campaign.name}": {str(e)}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nSummary: {sent_count} sent, {failed_count} failed'
            )
        )
