import csv
import io
import os
import re

import pandas as pd
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .drip_service import DripTriggerService
from .email_validation import normalize_email, validate_contact_email, validate_email_batch
from .models import Contact, ContactImportLog, ContactList, Tag

SUPPORTED_IMPORT_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.txt'}
EMAIL_HEADER_ALIASES = {'email', 'email_address', 'e_mail', 'emailaddress', 'mail', 'e-mail'}
BATCH_SIZE = 500


class ContactImportService:
    """Import contacts from CSV, Excel, or TXT with validation and audit logging."""

    def __init__(self, user):
        self.user = user

    def validate_uploaded_file(self, file):
        if not file:
            raise ValueError('No file provided')
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in SUPPORTED_IMPORT_EXTENSIONS:
            raise ValueError(
                'Unsupported file type. Upload CSV, Excel (.xlsx/.xls), or TXT (.txt).'
            )
        return ext

    def _normalize_header(self, header):
        if header is None:
            return ''
        return str(header).strip().lower().replace(' ', '_').replace('-', '_')

    def parse_uploaded_file(self, file):
        if hasattr(file, 'seek'):
            file.seek(0)
        ext = self.validate_uploaded_file(file)
        if ext == '.txt':
            return self._parse_txt(file), {}
        if ext in {'.xlsx', '.xls'}:
            return self._parse_excel(file)
        return self._parse_csv(file), {}

    def _parse_csv(self, file):
        decoded = file.read().decode('utf-8-sig')
        io_string = io.StringIO(decoded)
        reader = csv.DictReader(io_string)
        if reader.fieldnames:
            reader.fieldnames = [self._normalize_header(fn) for fn in reader.fieldnames]
        rows = []
        for row in reader:
            normalized = {
                self._normalize_header(k): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items()
                if k is not None
            }
            rows.append(self._map_contact_fields(normalized))
        return rows

    def _normalize_excel_cell(self, value):
        if value is None:
            return ''
        text = str(value).strip()
        if text.lower() in ('nan', 'none', ''):
            return ''
        if re.match(r'^\d+\.0+$', text):
            return text.split('.')[0]
        return text

    def _excel_sheet_row_count(self, file, ext):
        """Return total physical rows in the first worksheet (including header)."""
        if hasattr(file, 'seek'):
            file.seek(0)
        try:
            if ext == '.xlsx':
                import openpyxl
                workbook = openpyxl.load_workbook(file, read_only=True, data_only=True)
                sheet = workbook.active
                count = sheet.max_row or 0
                workbook.close()
                return count
            if ext == '.xls':
                import xlrd
                workbook = xlrd.open_workbook(file_contents=file.read())
                return workbook.sheet_by_index(0).nrows
        except Exception:
            return None
        finally:
            if hasattr(file, 'seek'):
                file.seek(0)
        return None

    def _parse_excel(self, file):
        ext = os.path.splitext(file.name)[1].lower()
        if hasattr(file, 'seek'):
            file.seek(0)

        sheet_rows = self._excel_sheet_row_count(file, ext)
        engine = 'openpyxl' if ext == '.xlsx' else 'xlrd'
        try:
            df = pd.read_excel(file, dtype=str, engine=engine, keep_default_na=False)
        except ImportError as exc:
            missing = 'openpyxl' if ext == '.xlsx' else 'xlrd'
            raise ValueError(
                f'Excel import requires {missing}. Install dependencies: pip install pandas openpyxl xlrd'
            ) from exc
        except Exception as exc:
            raise ValueError(f'Could not read Excel file: {exc}') from exc

        if df.empty:
            return [], {'sheet_rows': sheet_rows or 0, 'parsed_rows': 0}

        df.columns = [self._normalize_header(c) for c in df.columns]
        email_col = next((col for col in df.columns if col in EMAIL_HEADER_ALIASES), None)

        rows = []
        for index, record in enumerate(df.to_dict('records'), start=2):
            cleaned = {
                self._normalize_header(key): self._normalize_excel_cell(value)
                for key, value in record.items()
                if key is not None
            }
            if email_col and email_col in cleaned:
                cleaned[email_col] = self._normalize_excel_cell(cleaned.get(email_col))
            mapped = self._map_contact_fields(cleaned)
            if not mapped.get('_row'):
                mapped['_row'] = index
            rows.append(mapped)

        meta = {
            'sheet_rows': sheet_rows or (len(rows) + 1),
            'parsed_rows': len(rows),
        }
        return rows, meta

    def _parse_txt(self, file):
        decoded = file.read().decode('utf-8-sig')
        rows = []
        for idx, line in enumerate(decoded.splitlines(), start=1):
            email = line.strip()
            if not email or email.startswith('#'):
                continue
            rows.append({'email': email, 'name': '', 'is_subscribed': True, '_row': idx})
        return rows

    def _map_contact_fields(self, row):
        email = self._extract_field(row, list(EMAIL_HEADER_ALIASES))
        name = self._extract_field(row, ['name', 'full_name', 'full name'])
        is_subscribed = self._extract_field(row, ['is_subscribed', 'subscribed', 'subscription_status'])
        return {
            'email': email,
            'name': name,
            'is_subscribed': is_subscribed if is_subscribed != '' else True,
            '_row': row.get('_row'),
        }

    def _extract_field(self, row, keys):
        for key in keys:
            if key in row and row[key] is not None:
                return row[key]
        return ''

    def preview_import(self, file):
        rows, file_meta = self.parse_uploaded_file(file)
        if not rows:
            raise ValueError('No email addresses found in the file')
        self._ensure_email_column(rows)
        summary = validate_email_batch(rows)
        summary.update(self._build_file_row_summary(file_meta, summary))
        return {
            'filename': file.name,
            'file_type': os.path.splitext(file.name)[1].lower().lstrip('.'),
            **summary,
        }

    def _build_file_row_summary(self, file_meta, validation):
        sheet_rows = int(file_meta.get('sheet_rows') or 0)
        parsed_rows = int(file_meta.get('parsed_rows') or validation.get('total_rows') or 0)
        data_rows_in_sheet = max(0, sheet_rows - 1) if sheet_rows else parsed_rows
        invalid_count = validation.get('invalid_count', 0)
        duplicate_count = validation.get('duplicate_count', 0)
        valid_count = validation.get('valid_count', 0)
        not_imported = invalid_count + duplicate_count
        blank_rows_in_sheet = max(0, data_rows_in_sheet - parsed_rows)

        return {
            'sheet_rows': sheet_rows,
            'parsed_rows': parsed_rows,
            'data_rows_in_sheet': data_rows_in_sheet,
            'blank_rows_in_sheet': blank_rows_in_sheet,
            'not_imported': not_imported,
            'imported_count': valid_count,
        }

    def _ensure_email_column(self, rows):
        if not any((row.get('email') or '').strip() for row in rows):
            raise ValueError('Missing required column: email')

    @transaction.atomic
    def import_contacts(
        self,
        rows,
        list_id=None,
        filename='import.csv',
        file_type='csv',
        log_entry=None,
        file_meta=None,
    ):
        file_meta = file_meta or {}
        if not rows:
            raise ValueError('No rows to import')

        contact_list = None
        if list_id:
            try:
                contact_list = ContactList.objects.get(id=list_id, user=self.user)
            except ContactList.DoesNotExist:
                raise ValueError(f'Contact list {list_id} not found')

        validation = validate_email_batch(rows)
        valid_rows = validation['valid_records']

        if not valid_rows:
            if log_entry:
                self._finalize_log(log_entry, validation, 0, 0, 0, validation['errors'], 'failed')
            return {
                'created': 0,
                'updated': 0,
                'skipped': validation['total_rows'],
                'total': validation['total_rows'],
                'rows_in_file': validation['total_rows'],
                'valid_count': 0,
                'invalid_count': validation['invalid_count'],
                'duplicate_count': validation['duplicate_count'],
                'imported_count': 0,
                'contact_ids': [],
                'errors': validation['errors'][:50],
                **self._build_file_row_summary(file_meta, validation),
            }

        created_count = 0
        updated_count = 0
        skipped_count = validation['invalid_count'] + validation['duplicate_count']
        errors = list(validation['errors'])
        imported_ids = []
        trigger_service = DripTriggerService()

        emails = [r['email'] for r in valid_rows]
        existing_qs = Contact.objects.filter(user=self.user, email__in=emails)
        existing_by_email = {c.email: c for c in existing_qs}

        for record in valid_rows:
            try:
                result, contact = self._import_single_contact(record, contact_list, existing_by_email)
                if result == 'created':
                    created_count += 1
                    trigger_service.handle_contact_added(contact, self.user)
                elif result == 'updated':
                    updated_count += 1
                else:
                    skipped_count += 1

                if contact is not None:
                    imported_ids.append(contact.id)
            except Exception as exc:
                skipped_count += 1
                errors.append({
                    'row': record.get('row', '?'),
                    'email': record.get('email', 'unknown'),
                    'error': str(exc),
                })

        result = {
            'created': created_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'total': validation['total_rows'],
            'rows_in_file': validation['total_rows'],
            'valid_count': len(valid_rows),
            'invalid_count': validation['invalid_count'],
            'duplicate_count': validation['duplicate_count'],
            'imported_count': len(imported_ids),
            'contact_ids': imported_ids,
            'errors': errors[:50],
        }
        result.update(self._build_file_row_summary(file_meta, validation))
        result['imported_count'] = len(imported_ids)

        if log_entry:
            status = 'failed' if created_count + updated_count == 0 and skipped_count > 0 else 'completed'
            self._finalize_log(
                log_entry, validation, created_count, updated_count, skipped_count, errors, status
            )

        return result

    def _import_single_contact(self, record, contact_list=None, existing_by_email=None):
        email = normalize_email(record.get('email', ''))
        check = validate_contact_email(email)
        if not check['is_valid']:
            raise ValueError(check['error'] or 'Invalid email')

        email = check['normalized_email']
        name = (record.get('name') or '').strip()
        is_subscribed = record.get('is_subscribed', True)
        if isinstance(is_subscribed, str):
            is_subscribed = is_subscribed.lower() not in ['false', '0', 'no', 'off', '']

        existing = (existing_by_email or {}).get(email)
        if existing is None:
            existing = Contact.objects.filter(user=self.user, email=email).first()

        contact, created = Contact.objects.update_or_create(
            user=self.user,
            email=email,
            defaults={
                'name': name,
                'is_subscribed': bool(is_subscribed),
            },
        )

        if existing_by_email is not None:
            existing_by_email[email] = contact

        if contact_list:
            contact.lists.add(contact_list)

        return ('created' if created else 'updated'), contact

    def create_import_log(self, filename, file_type, contact_list=None):
        return ContactImportLog.objects.create(
            user=self.user,
            filename=filename,
            file_type=file_type,
            status='preview',
            contact_list=contact_list,
        )

    def _finalize_log(self, log_entry, validation, created, updated, skipped, errors, status):
        log_entry.total_rows = validation['total_rows']
        log_entry.valid_count = validation['valid_count']
        log_entry.invalid_count = validation['invalid_count']
        log_entry.duplicate_count = validation['duplicate_count']
        log_entry.created_count = created
        log_entry.updated_count = updated
        log_entry.skipped_count = skipped
        log_entry.errors = errors[:100]
        log_entry.status = status
        log_entry.completed_at = timezone.now()
        log_entry.save()

    def get_import_history(self, limit=20):
        logs = ContactImportLog.objects.filter(user=self.user).select_related('contact_list')[:limit]
        return [
            {
                'id': log.id,
                'filename': log.filename,
                'file_type': log.file_type,
                'status': log.status,
                'total_rows': log.total_rows,
                'valid_count': log.valid_count,
                'invalid_count': log.invalid_count,
                'duplicate_count': log.duplicate_count,
                'created_count': log.created_count,
                'updated_count': log.updated_count,
                'skipped_count': log.skipped_count,
                'contact_list': log.contact_list.name if log.contact_list else None,
                'started_at': log.started_at,
                'completed_at': log.completed_at,
                'error_count': len(log.errors or []),
            }
            for log in logs
        ]

    def export_contacts(self, list_id=None):
        contacts = Contact.objects.filter(user=self.user)
        if list_id:
            contacts = contacts.filter(lists__id=list_id)
        contacts = contacts.distinct()
        return [
            {
                'email': contact.email,
                'name': contact.name,
                'is_subscribed': contact.is_subscribed,
            }
            for contact in contacts
        ]

    def get_import_template(self):
        return [
            {'email': 'john@yahoo.com', 'name': 'John Doe', 'is_subscribed': True},
            {'email': 'jane@outlook.com', 'name': 'Jane Smith', 'is_subscribed': True},
            {'email': 'contact@company.co.in', 'name': 'India Contact', 'is_subscribed': True},
            {'email': 'user@protonmail.com', 'name': 'Proton User', 'is_subscribed': True},
        ]


class ContactBulkService:
    """Service for bulk contact operations"""

    def __init__(self, user):
        self.user = user

    @transaction.atomic
    def bulk_subscribe(self, contact_ids):
        count = Contact.objects.filter(
            user=self.user,
            id__in=contact_ids
        ).update(is_subscribed=True)
        return count

    @transaction.atomic
    def bulk_unsubscribe(self, contact_ids):
        count = Contact.objects.filter(user=self.user, id__in=contact_ids).update(
            is_subscribed=False
        )
        return count

    @transaction.atomic
    def bulk_add_to_list(self, contact_ids, list_id):
        try:
            contact_list = ContactList.objects.get(id=list_id, user=self.user)
            contacts = Contact.objects.filter(user=self.user, id__in=contact_ids)
            for contact in contacts:
                contact.lists.add(contact_list)
            return contacts.count()
        except ContactList.DoesNotExist:
            raise ValueError(f'Contact list {list_id} not found')

    @transaction.atomic
    def bulk_delete(self, contact_ids):
        count = Contact.objects.filter(user=self.user, id__in=contact_ids).delete()
        return count[0]
