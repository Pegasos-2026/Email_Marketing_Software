from django.apps import AppConfig


class CampaignsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app.campaigns'
    label = 'campaigns'

    def ready(self):
        import sys

        skip_commands = ('migrate', 'makemigrations', 'test', 'check', 'collectstatic', 'shell')
        if any(cmd in sys.argv for cmd in skip_commands):
            return

        try:
            from django.db import connection

            if connection.vendor == 'sqlite':
                return

            from app.campaigns.schema_utils import create_missing_m2m_tables

            tables = set(connection.introspection.table_names())
            if 'campaigns_campaign_lists' not in tables or 'campaigns_campaign_tags' not in tables:
                create_missing_m2m_tables()
        except Exception:
            return
