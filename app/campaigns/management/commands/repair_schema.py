"""Add missing DB columns and M2M tables when migration history is out of sync with the schema."""
import sqlite3

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from app.campaigns.schema_utils import create_missing_m2m_tables


class Command(BaseCommand):
    help = 'Repair SQLite schema for known missing columns and M2M tables'

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        if db['ENGINE'] != 'django.db.backends.sqlite3':
            self.stdout.write(self.style.WARNING('repair_schema only supports SQLite.'))
            return

        repairs = create_missing_m2m_tables()

        conn = sqlite3.connect(str(db['NAME']))
        cur = conn.cursor()

        def has_column(table, column):
            cur.execute(f'PRAGMA table_info({table})')
            return column in [row[1] for row in cur.fetchall()]

        if not has_column('campaigns_campaign', 'filter_type'):
            cur.execute(
                "ALTER TABLE campaigns_campaign ADD COLUMN filter_type varchar(10) NOT NULL DEFAULT 'or'",
            )
            repairs.append('campaigns_campaign.filter_type')

        email_repairs = [
            ('domain_id', 'ALTER TABLE emails_emailsetting ADD COLUMN domain_id varchar(100)'),
            ('smtp_host', 'ALTER TABLE emails_emailsetting ADD COLUMN smtp_host varchar(255)'),
            ('smtp_port', 'ALTER TABLE emails_emailsetting ADD COLUMN smtp_port integer NOT NULL DEFAULT 587'),
            ('smtp_user', 'ALTER TABLE emails_emailsetting ADD COLUMN smtp_user varchar(255)'),
            ('smtp_password', 'ALTER TABLE emails_emailsetting ADD COLUMN smtp_password text'),
        ]
        for col, ddl in email_repairs:
            if not has_column('emails_emailsetting', col):
                cur.execute(ddl)
                repairs.append(f'emails_emailsetting.{col}')

        # SQLite keeps old NOT NULL constraints from early migrations; rebuild when needed.
        cur.execute('PRAGMA table_info(emails_emailsetting)')
        api_key_col = next((row for row in cur.fetchall() if row[1] == 'api_key'), None)
        if api_key_col and api_key_col[3] == 1:
            cur.execute(
                '''
                CREATE TABLE emails_emailsetting_new (
                    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
                    provider varchar(50) NOT NULL DEFAULT 'SMTP',
                    api_key text,
                    from_email varchar(254),
                    from_name varchar(100),
                    sending_domain varchar(255),
                    domain_verified bool NOT NULL DEFAULT 0,
                    created_at datetime NOT NULL,
                    user_id integer NOT NULL UNIQUE REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED,
                    smtp_host varchar(255),
                    smtp_port integer NOT NULL DEFAULT 587,
                    smtp_user varchar(255),
                    smtp_password text,
                    domain_id varchar(100)
                )
                '''
            )
            cur.execute(
                '''
                INSERT INTO emails_emailsetting_new (
                    id, provider, api_key, from_email, from_name, sending_domain,
                    domain_verified, created_at, user_id, smtp_host, smtp_port,
                    smtp_user, smtp_password, domain_id
                )
                SELECT
                    id, provider, api_key, from_email, from_name, sending_domain,
                    domain_verified, created_at, user_id, smtp_host, smtp_port,
                    smtp_user, smtp_password, domain_id
                FROM emails_emailsetting
                '''
            )
            cur.execute('DROP TABLE emails_emailsetting')
            cur.execute('ALTER TABLE emails_emailsetting_new RENAME TO emails_emailsetting')
            repairs.append('emails_emailsetting (rebuilt nullable columns)')

        conn.commit()
        conn.close()

        if repairs:
            self.stdout.write(self.style.SUCCESS(f'Repaired: {", ".join(repairs)}'))
        else:
            self.stdout.write('Schema already up to date.')
