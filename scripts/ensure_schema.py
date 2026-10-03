"""Create missing campaigns app tables and columns, then fake-apply pending migrations."""
import os
import sys

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.apps import apps
from django.core.management import call_command
from django.db import connection


def _has_column(table, column):
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table)
    return column in {col.name for col in description}


def ensure_schema():
    existing = set(connection.introspection.table_names())
    app_config = apps.get_app_config('campaigns')
    models = list(app_config.get_models())
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
                    for m2m in model._meta.many_to_many:
                        through = m2m.remote_field.through
                        if through._meta.auto_created:
                            existing.add(through._meta.db_table)
                except Exception as exc:
                    err = str(exc).lower()
                    if 'already exists' in err:
                        existing.add(table)
                        remaining.remove(model)
                        progress = True
                        repairs.append(f'skipped existing {table}')
                    else:
                        continue
            if not progress:
                raise RuntimeError(
                    'Could not create tables: '
                    + ', '.join(m._meta.db_table for m in remaining)
                )

    column_repairs = [
        ('campaigns_campaign', 'filter_type', "varchar(10) NOT NULL DEFAULT 'or'"),
    ]
    with connection.cursor() as cursor:
        for table, column, col_type in column_repairs:
            if table in existing and not _has_column(table, column):
                cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {col_type}')
                repairs.append(f'added {table}.{column}')

    for migration in (
        '0005_alter_contactlist_options_campaign_filter_type_and_more',
        '0006_event_eventregistration_eventregistrationform_and_more',
        '0007_alter_abtest_id_alter_abtestrecipient_id_and_more',
    ):
        call_command('migrate', 'campaigns', migration, fake=True, verbosity=0)

    return repairs


if __name__ == '__main__':
    result = ensure_schema()
    if result:
        print('Repairs:', ', '.join(result))
    else:
        print('Schema already complete.')
