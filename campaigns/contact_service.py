import csv
import io
import pandas as pd
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from .models import Contact,ContactList
class ContactImportService:
    """Service for importing contacts from CSV
    Handles all buisness logic"""
    def __init__(self,user):
        self.user=user
    def validate_csv_file(self,file):
        """Validate uploaded contact import file"""
        if not file:
            raise ValueError("No file provided")

        file_name = file.name.lower()
        if not (file_name.endswith('.csv') or file_name.endswith('.xlsx') or file_name.endswith('.xls')):
            raise ValueError("File must be CSV or Excel (.xlsx/.xls)")
        return True

    def _normalize_header(self, header):
        if not header:
            return ''
        return header.strip().lower().replace(' ', '_')

    def validate_csv_headers(self,headers):
        """Validate CSV has required columns"""
        normalized_headers = [self._normalize_header(h) for h in headers if h is not None]
        email_fields = {'email', 'email_address', 'e_mail', 'emailaddress', 'mail'}

        if not any(field in normalized_headers for field in email_fields):
            raise ValueError("Missing required column: email")

        return True

    def parse_csv_basic(self,file):
        """Parse an uploaded CSV or Excel file into normalized contact rows."""
        file_name = file.name.lower()
        if file_name.endswith(('.xlsx', '.xls')):
            return self.parse_excel(file)

        decoded_file = file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        if reader.fieldnames:
            reader.fieldnames = [self._normalize_header(fn) for fn in reader.fieldnames]

        rows = []
        for row in reader:
            normalized_row = {
                self._normalize_header(k): (v.strip() if isinstance(v, str) else v)
                for k, v in row.items()
                if k is not None
            }
            rows.append(self._map_contact_fields(normalized_row))

        return rows

    def parse_excel(self, file):
        """Parse Excel files into normalized contact rows."""
        try:
            file.seek(0)
        except Exception:
            pass

        try:
            df = pd.read_excel(file)
        except Exception as e:
            raise ValueError(f"Unable to parse Excel file: {e}")

        df.columns = [self._normalize_header(str(col)) for col in df.columns]
        df = df.fillna('')

        rows = []
        for _, row in df.iterrows():
            normalized_row = {
                self._normalize_header(k): (str(v).strip() if pd.notna(v) else '')
                for k, v in row.items()
                if k is not None
            }
            rows.append(self._map_contact_fields(normalized_row))

        return rows

    def _map_contact_fields(self, row):
        """Map CSV row field names to canonical contact fields."""
        email = self._extract_field(row, ['email', 'email_address', 'e_mail', 'mail', 'emailaddress'])
        name = self._extract_field(row, ['name', 'full_name', 'full name', 'first_name', 'firstname'])
        raw_is_subscribed = self._extract_field(row, ['is_subscribed', 'subscribed', 'subscription_status'])

        if raw_is_subscribed == '':
            is_subscribed = True
        elif isinstance(raw_is_subscribed, str):
            is_subscribed = raw_is_subscribed.lower() not in ['false', '0', 'no', 'off']
        else:
            is_subscribed = bool(raw_is_subscribed)

        mapped = {
            'email': email,
            'name': name,
            'is_subscribed': is_subscribed,
        }

        return {k: v for k, v in mapped.items() if v is not None}

    def _extract_field(self, row, keys):
        for key in keys:
            if key in row and row[key] is not None:
                return row[key]
        return ''
    def parse_csv_pandas(self,file):
        """Parse CSV file using pandas (better for large files)"""
        df=pd.read_csv(file)
        df.columns=df.columns.str.strip().str.lower()
        df=df.fillna('')
        return df.to_dict('records')
    @transaction.atomic
    def import_contacts(self,rows,list_id=None):
        """Import contacts from parse CSV data
        Args:
        rows:list of dicts with contact data
        list_id:optional contact list ID to add contacts to
        Returns:
        dict with results
        """
        created_count=0
        updated_count=0
        skipped_count=0
        errors=[]
        #Get contact list if provided 
        contact_list=None
        if list_id:
            try:
                contact_list=ContactList.objects.get(id=list_id,user=self.user)
            except ContactList.DoesNotExist:
                raise ValueError(f"Contact list {list_id} not found")
        imported_ids = []
        for idx, row in enumerate(rows, start=2):
            try:
                result, contact = self._import_single_contact(row, contact_list)
                if result == 'created':
                    created_count += 1
                elif result == 'updated':
                    updated_count += 1
                else:
                    skipped_count += 1

                if contact is not None:
                    imported_ids.append(contact.id)
            except Exception as e:
                skipped_count += 1
                errors.append({
                    'row': idx,
                    'email': row.get('email', 'unknown'),
                    'error': str(e)
                })
        return {
            'created': created_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'total': created_count + updated_count + skipped_count,
            'contact_ids': imported_ids,
            'errors': errors[:10]  # first 10 errors
        }

    def _import_single_contact(self,row,contact_list=None):
        """Import single contact"""
        email = row.get('email','').strip().lower()
        # Validate email
        if not self._validate_email(email):
            raise ValueError("Invalid email")

        name = row.get('name','').strip()
        is_subscribed = row.get('is_subscribed', '')
        if isinstance(is_subscribed, str):
            is_subscribed = is_subscribed.lower() not in ['false', '0', 'no', 'off', '']

        contact = Contact.objects.filter(email=email, user=self.user).first()
        if contact is None:
            contact = Contact.objects.create(
                user=self.user,
                email=email,
                name=name,
                is_subscribed=bool(is_subscribed),
            )
            result = 'created'
        else:
            contact.name = name
            contact.is_subscribed = bool(is_subscribed)
            contact.save()
            result = 'updated'

        if contact_list:
            contact.lists.add(contact_list)
        return (result, contact)
    def _validate_email(self,email):
        """Validate email format using Django validators"""
        if not email:
            return False
        try:
            validate_email(email)
            return True
        except ValidationError:
            return False
    def export_contacts(self,list_id=None):
        """Export contacts to CSV format"""
        contacts=Contact.objects.filter(user=self.user)
        if list_id:
            contacts=contacts.filter(lists__id=list_id)
        contacts=contacts.distinct()
        return [
            {
                'email':contact.email,
                'name':contact.name,
                'is_subscribed':contact.is_subscribed
            }
            for contact in contacts
        ]  
    def get_import_template(self):
        """Get CSV import template data"""
        return [
            {
                'email':'john@example.com',
                'name':'John Doe',
                'is_subscribed': True
            },
            {
                'email':'jane@example.com',
                'name':'Jane Smith',
                'is_subscribed': True
            }
        ]
class ContactBulkService:
    """Service for bulk contact operations"""
    def __init__(self,user):
        self.user=user
    @transaction.atomic
    def bulk_subscribe(self,contact_ids):
        """Subscribe multiple contacts"""
        count=Contact.objects.filter(
            user=self.user,
            id__in=contact_ids
        ).update(is_subscribed=True,unsubscribed_data=None)
        return count
    @transaction.atomic
    def bulk_unsubscribe(self,contact_ids):
        from django.utils import timezone
        count=Contact.objects.filter(user=self.user,id__in=contact_ids).update(is_subscribed=False,unsubscribed_data=timezone.now())
        return count
    @transaction.atomic
    def bulk_add_to_list(self,contact_ids,list_id):
        """Add multiple contacts to a list"""
        try:
            contact_list=ContactList.objects.get(id=list_id,user=self.user)
            contacts=Contact.objects.filter(user=self.user,id__in=contact_ids)
            for contact in contacts:
                contact.lists.add(contact_list)
            return contacts.count()
        except ContactList.DoesNotExist:
            raise ValueError(f"Contact list {list_id} not found")
    @transaction.atomic
    def bulk_delete(self,contact_ids):
        """Delete multiple contact"""
        count=Contact.objects.filter(user=self.user,id__in=contact_ids).delete()
        return count[0] #returns (count,{model:count})
    