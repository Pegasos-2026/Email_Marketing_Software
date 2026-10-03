"""Create missing campaigns tables when migration history is ahead of the DB schema."""
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Create missing campaigns app tables and fake-apply pending migrations'

    def handle(self, *args, **options):
        existing = set(connection.introspection.table_names())
        models = list(apps.get_app_config('campaigns').get_models())
        repairs = []

        with connection.schema_editor(atomic=False) as editor:
            remaining = [m for m in models if m._meta.db_table not in existing]
            while remaining:
                progress = False
                for model in list(remaining):
                    table = model._meta.db_table
                    try:
                        editor.create_model(model)
                        existing.add(table)
                        repairs.append(f'created {table}')
                        remaining.remove(model)
                        progress = True
                    except Exception as exc:
                        if 'already exists' in str(exc).lower():
                            existing.add(table)
                            remaining.remove(model)
                            progress = True
                            repairs.append(f'skipped existing {table}')
                if not progress:
                    raise RuntimeError(
                        'Could not create tables: '
                        + ', '.join(m._meta.db_table for m in remaining)
                    )

        from app.campaigns.schema_utils import create_missing_m2m_tables

        for table in create_missing_m2m_tables(('campaigns',)):
            repairs.append(f'created {table}')

        column_repairs = [
            ('campaigns_campaign', 'filter_type', "varchar(10) NOT NULL DEFAULT 'or'"),
        ]
        with connection.cursor() as cursor:
            for table, column, col_type in column_repairs:
                if table not in existing:
                    continue
                description = connection.introspection.get_table_description(cursor, table)
                if column not in {col.name for col in description}:
                    cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}')
                    repairs.append(f'added {table}.{column}')

        from django.core.management import call_command

        for migration in (
            '0005_alter_contactlist_options_campaign_filter_type_and_more',
            '0006_event_eventregistration_eventregistrationform_and_more',
            '0007_alter_abtest_id_alter_abtestrecipient_id_and_more',
            '0008_tag_category_default',
            '0009_opentracking_drip_fields',
            '0010_contactimportlog',
            '0011_contact_unique_per_user',
        ):
            call_command('migrate', 'campaigns', migration, fake=True, verbosity=0)

        if repairs:
            self.stdout.write(self.style.SUCCESS(f'Repaired: {", ".join(repairs)}'))
        else:
            self.stdout.write('Schema already complete.')
