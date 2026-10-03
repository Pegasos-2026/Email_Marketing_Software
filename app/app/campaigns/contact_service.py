import csv
import io
import pandas as pd
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from .models import Contact,ContactList,Tag
from rest_framework import serializers
class ContactImportService:
    """Service for importing contacts from CSV
    Handles all buisness logic"""
    def __init__(self,user):
        self.user=user
    def validate_csv_file(self,file):
        """validate uploded file"""
        if not file:
            raise ValueError("No file provided")
        if not file.name.endswith('.csv'):
            raise ValueError("File must be a CSV")
        return True
    def validate_csv_headers(self,headers):
        """Validate CSV has required columns"""
        required=['email']
        missing=[h for h in required if h not in headers]
        if missing:
            raise ValueError(f"Missing required columns:{','.join(missing)}")
        return True
    def parse_csv_basic(self,file):
        """parse CSV file using standard csv library"""
        decoded_file=file.read().decode('utf-8')
        io_string=io.StringIO(decoded_file)
        reader=csv.DictReader(io_string)
        return list(reader)
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
        for idx,row in enumerate(rows,start=2):
            try:
                result=self._import_single_contact(row,contact_list)
                if result =='created':
                    created_count +=1
                elif result =='updated':
                    updated_count +=1
                else:
                    skipped_count +=1
            except Exception as e:
                skipped_count +=1
                errors.append({
                    'row':idx,
                    'email':row.get('email','unknown'),
                    'error':str(e)
                })
        return {
            'created':created_count,
            'updated':updated_count,
            'skipped':skipped_count,
            'total':created_count + updated_count + skipped_count,
            'errors':errors[:10] #first 10 errors
        }
    def _import_single_contact(self,row,contact_list=None):
        """Import single contact"""
        email=row.get('email','').strip().lower()
        #Validate email
        if not self._validate_email(email):
            raise ValueError("IOnvalid email")
        #Get fields
        first_name=row.get('first_name','').strip()
        last_name=row.get('last_name','').strip()
        phone=row.get('phone','').strip()
        company=row.get('company','').strip()
        #Create or update
        contact,created=Contact.objects.update_or_create(
            user=self.user,
            email=email,
            defaults={
                'first_name':first_name,
                'last_name':last_name,
                'phone':phone,
                'company':company,
                'is_subscribed':True,
                'source':'csv_import'
            }
        )
        if contact_list:
            contact.lists.add(contact_list)
        return 'created' if created else 'updated'
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
                'first_name':contact.first_name,
                'last_name':contact.last_name,
                'phone':contact.phone,
                'company':contact.company,
                'is_subscribed':contact.is_subscribed
            }
            for contact in contacts
        ]  
    def get_import_template(self):
        """Get CSV import template data"""
        return [
            {
                'email':'john@example.com',
                'first_name':'John',
                'last_name':'Doe',
                'phone':'1234567890',
                'company':'Acme corp'
            },
            {
                'email':'jane@example.com',
                'first_name':'jane',
                'last_name':'Smith',
                'phone':'0987654321',
                'company':'Tech Inc',
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