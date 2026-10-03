from django.apps import apps
from django.db import connection


def create_missing_m2m_tables(app_labels=('campaigns',)):
    """Create auto-generated many-to-many through tables that migrations skipped."""
    existing = set(connection.introspection.table_names())
    repairs = []

    def _create_tables():
        with connection.schema_editor(atomic=False) as editor:
            for app_label in app_labels:
                app_config = apps.get_app_config(app_label)
                for model in app_config.get_models():
                    for m2m in model._meta.many_to_many:
                        through = m2m.remote_field.through
                        if not through._meta.auto_created:
                            continue
                        table = through._meta.db_table
                        if table in existing:
                            continue
                        try:
                            editor.create_model(through)
                            existing.add(table)
                            repairs.append(table)
                        except Exception as exc:
                            if 'already exists' in str(exc).lower():
                                existing.add(table)
                                repairs.append(f'skipped existing {table}')
                            else:
                                raise

    if connection.vendor == 'sqlite':
        with connection.constraint_checks_disabled():
            _create_tables()
    else:
        _create_tables()

    return repairs
