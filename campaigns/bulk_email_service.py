"""Service for bulk email sending to multiple contacts"""
from django.db import transaction
from django.utils import timezone
from .models import Contact, EmailLog
from emails.services import send_email


class BulkEmailService:
    """Handle bulk email sending to multiple contacts"""
    
    def __init__(self, user):
        self.user = user
    
    @transaction.atomic
    def send_to_contacts(self, contact_ids, subject, html_content, plain_text_content=None):
        """
        Send email to multiple contacts
        
        Args:
            contact_ids: List of contact IDs
            subject: Email subject
            html_content: HTML email content
            plain_text_content: Plain text alternative
            
        Returns:
            dict with sending results
        """
        contacts = Contact.objects.filter(
            user=self.user,
            id__in=contact_ids,
            is_subscribed=True
        )
        
        if not contacts.exists():
            raise ValueError("No active contacts found to send to")
        
        results = {
            'total': contacts.count(),
            'sent': 0,
            'failed': 0,
            'errors': []
        }
        
        for contact in contacts:
            try:
                result = send_email(
                    user=self.user,
                    to_email=contact.email,
                    subject=subject,
                    html_content=html_content,
                )
                
                if result.get('success'):
                    results['sent'] += 1
                    # Log successful send
                    self._log_email(contact, subject, 'sent')
                else:
                    results['failed'] += 1
                    error_msg = result.get('error', 'Unknown error')
                    results['errors'].append({
                        'email': contact.email,
                        'error': error_msg
                    })
                    self._log_email(contact, subject, 'failed', error_msg)
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'email': contact.email,
                    'error': str(e)
                })
                self._log_email(contact, subject, 'failed', str(e))
        
        return results
    
    @transaction.atomic
    def send_to_list(self, list_id, subject, html_content, plain_text_content=None):
        """
        Send email to all contacts in a list
        
        Args:
            list_id: Contact list ID
            subject: Email subject
            html_content: HTML email content
            plain_text_content: Plain text alternative
            
        Returns:
            dict with sending results
        """
        from .models import ContactList
        
        try:
            contact_list = ContactList.objects.get(id=list_id, user=self.user)
        except ContactList.DoesNotExist:
            raise ValueError(f"Contact list {list_id} not found")
        
        contact_ids = contact_list.contacts.filter(
            is_subscribed=True
        ).values_list('id', flat=True)
        
        return self.send_to_contacts(
            list(contact_ids),
            subject,
            html_content,
            plain_text_content
        )
    
    def _log_email(self, contact, subject, status, error_msg=None):
        """Log email sending for analytics"""
        try:
            if hasattr(contact, 'email_logs'):
                EmailLog.objects.create(
                    contact=contact,
                    subject=subject,
                    status=status,
                    error_message=error_msg,
                    sent_at=timezone.now()
                )
        except Exception:
            # Don't fail bulk send if logging fails
            pass
