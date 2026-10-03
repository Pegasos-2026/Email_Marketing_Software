"""Contact management API views."""
import csv

from django.db.models import Count
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .contact_service import ContactBulkService, ContactImportService
from .drip_service import DripTriggerService
from .models import Contact, ContactList, Tag


class ContactListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        contacts = (
            Contact.objects.filter(user=request.user)
            .prefetch_related('tags')
            .order_by('-created_at')
        )
        data = []
        for contact in contacts:
            full_name = contact.name or ''
            parts = full_name.split(' ', 1)
            data.append({
                'id': contact.id,
                'email': contact.email,
                'first_name': parts[0] if parts else '',
                'last_name': parts[1] if len(parts) > 1 else '',
                'name': contact.name,
                'subscribed': contact.is_subscribed,
                'is_subscribed': contact.is_subscribed,
                'tags': [t.name for t in contact.tags.all()],
            })
        return Response(data)


class ContactDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_contact(self, request, contact_id):
        return Contact.objects.get(id=contact_id, user=request.user)

    def get(self, request, contact_id):
        try:
            contact = self._get_contact(request, contact_id)
        except Contact.DoesNotExist:
            return Response({'error': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)
        full_name = contact.name or ''
        parts = full_name.split(' ', 1)
        return Response({
            'id': contact.id,
            'email': contact.email,
            'first_name': parts[0] if parts else '',
            'last_name': parts[1] if len(parts) > 1 else '',
            'name': contact.name,
            'subscribed': contact.is_subscribed,
            'is_subscribed': contact.is_subscribed,
            'tags': [t.name for t in contact.tags.all()],
        })

    def put(self, request, contact_id):
        try:
            contact = self._get_contact(request, contact_id)
        except Contact.DoesNotExist:
            return Response({'error': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)

        email = request.data.get('email', contact.email)
        name = request.data.get('name', contact.name)
        if 'first_name' in request.data or 'last_name' in request.data:
            first = request.data.get('first_name', '')
            last = request.data.get('last_name', '')
            name = f'{first} {last}'.strip()
        is_subscribed = request.data.get(
            'is_subscribed',
            request.data.get('subscribed', contact.is_subscribed),
        )

        if email:
            contact.email = email.strip().lower()
        contact.name = name
        contact.is_subscribed = bool(is_subscribed)
        contact.save()

        list_ids = request.data.get('list_ids')
        if list_ids is not None:
            contact.lists.clear()
            for list_id in list_ids:
                try:
                    contact_list = ContactList.objects.get(id=list_id, user=request.user)
                    contact.lists.add(contact_list)
                except ContactList.DoesNotExist:
                    pass

        return Response({
            'id': contact.id,
            'email': contact.email,
            'name': contact.name,
            'is_subscribed': contact.is_subscribed,
        })

    def delete(self, request, contact_id):
        try:
            contact = self._get_contact(request, contact_id)
            contact.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Contact.DoesNotExist:
            return Response({'error': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)


class ContactCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        email = request.data.get('email')
        name = request.data.get('name', '')
        if 'first_name' in request.data or 'last_name' in request.data:
            first = request.data.get('first_name', '')
            last = request.data.get('last_name', '')
            name = f'{first} {last}'.strip()
        is_subscribed = request.data.get('is_subscribed', True)
        list_ids = request.data.get('list_ids', [])

        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

        email = email.strip().lower()
        contact = Contact.objects.filter(email=email, user=request.user).first()
        if contact is None:
            contact = Contact.objects.create(
                user=request.user,
                email=email,
                name=name,
                is_subscribed=is_subscribed,
            )
        else:
            contact.name = name
            contact.is_subscribed = is_subscribed
            contact.save()

        for list_id in list_ids:
            try:
                contact_list = ContactList.objects.get(id=list_id, user=request.user)
                contact.lists.add(contact_list)
            except ContactList.DoesNotExist:
                pass

        DripTriggerService().handle_contact_added(contact, request.user)

        return Response({
            'message': 'Contact created successfully',
            'contact': {
                'id': contact.id,
                'email': contact.email,
                'name': contact.name,
                'is_subscribed': contact.is_subscribed,
                'lists': [{'id': lst.id, 'name': lst.name} for lst in contact.lists.all()],
            },
        }, status=status.HTTP_201_CREATED)


class ContactListsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        lists = (
            ContactList.objects.filter(user=request.user)
            .annotate(contact_count=Count('contacts'))
            .order_by('name')
        )
        return Response([
            {
                'id': contact_list.id,
                'name': contact_list.name,
                'description': contact_list.description,
                'contact_count': contact_list.contact_count,
                'created_at': contact_list.created_at,
            }
            for contact_list in lists
        ])

    def post(self, request):
        name = request.data.get('name')
        description = request.data.get('description', '')
        if not name:
            return Response({'error': 'Name is required'}, status=status.HTTP_400_BAD_REQUEST)

        contact_list = ContactList.objects.create(
            user=request.user,
            name=name,
            description=description,
        )
        return Response({
            'message': 'Contact list created successfully',
            'list': {
                'id': contact_list.id,
                'name': contact_list.name,
                'description': contact_list.description,
                'contact_count': 0,
            },
        }, status=status.HTTP_201_CREATED)


class ContactListDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, list_id):
        try:
            contact_list = ContactList.objects.get(id=list_id, user=request.user)
        except ContactList.DoesNotExist:
            return Response({'error': 'Contact list not found'}, status=status.HTTP_404_NOT_FOUND)

        contacts = [
            {
                'id': contact.id,
                'email': contact.email,
                'name': contact.name,
                'is_subscribed': contact.is_subscribed,
            }
            for contact in contact_list.contacts.all()
        ]
        return Response({
            'id': contact_list.id,
            'name': contact_list.name,
            'description': contact_list.description,
            'contact_count': len(contacts),
            'contacts': contacts,
        })

    def put(self, request, list_id):
        try:
            contact_list = ContactList.objects.get(id=list_id, user=request.user)
        except ContactList.DoesNotExist:
            return Response({'error': 'Contact list not found'}, status=status.HTTP_404_NOT_FOUND)

        if 'name' in request.data:
            contact_list.name = request.data['name']
        if 'description' in request.data:
            contact_list.description = request.data['description']
        contact_list.save()
        return Response({
            'id': contact_list.id,
            'name': contact_list.name,
            'description': contact_list.description,
        })

    def delete(self, request, list_id):
        try:
            contact_list = ContactList.objects.get(id=list_id, user=request.user)
            contact_list.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ContactList.DoesNotExist:
            return Response({'error': 'Contact list not found'}, status=status.HTTP_404_NOT_FOUND)


class ContactImportCSVView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get('file')
        list_id = request.data.get('list_id')
        if not upload:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        service = ContactImportService(request.user)
        try:
            ext = service.validate_uploaded_file(upload)
            rows, file_meta = service.parse_uploaded_file(upload)
            contact_list = None
            if list_id:
                contact_list = ContactList.objects.filter(id=list_id, user=request.user).first()

            log_entry = service.create_import_log(
                filename=upload.name,
                file_type=ext.lstrip('.'),
                contact_list=contact_list,
            )
            result = service.import_contacts(
                rows,
                list_id=list_id,
                filename=upload.name,
                file_type=ext.lstrip('.'),
                log_entry=log_entry,
                file_meta=file_meta,
            )
            return Response({'success': True, 'summary': result, 'import_log_id': log_entry.id},
                            status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ContactImportPreviewView(APIView):
    """Validate import file without saving contacts."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

        service = ContactImportService(request.user)
        try:
            preview = service.preview_import(upload)
            return Response({'success': True, 'preview': preview}, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ContactImportHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get('limit', 20))
        service = ContactImportService(request.user)
        return Response({'history': service.get_import_history(limit=limit)})


class ContactExportCSVView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        list_id = request.query_params.get('list_id')
        try:
            if list_id:
                contact_list = ContactList.objects.get(id=list_id, user=request.user)
                contacts = contact_list.contacts.all()
            else:
                contacts = Contact.objects.filter(user=request.user)

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="contacts.csv"'
            writer = csv.writer(response)
            writer.writerow(['email', 'name', 'is_subscribed'])
            for contact in contacts:
                writer.writerow([contact.email, contact.name or '', contact.is_subscribed])
            return response
        except ContactList.DoesNotExist:
            return Response({'error': 'Contact list not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as exc:
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ContactImportTemplateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        service = ContactImportService(request.user)
        template_rows = service.get_import_template()
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="contact_template.csv"'
        writer = csv.writer(response)
        writer.writerow(['email', 'name', 'is_subscribed'])
        for row in template_rows:
            writer.writerow([row['email'], row['name'], row['is_subscribed']])
        return response


class ContactBulkActionsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        service = ContactBulkService(request.user)
        action = request.data.get('action')
        contact_ids = request.data.get('contact_ids', [])
        if not action or not contact_ids:
            return Response(
                {'error': 'action and contact_ids are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if action == 'subscribe':
                count = service.bulk_subscribe(contact_ids)
                message = f'{count} contact(s) subscribed'
            elif action == 'unsubscribe':
                count = service.bulk_unsubscribe(contact_ids)
                message = f'{count} contact(s) unsubscribed'
            elif action == 'add_to_list':
                list_id = request.data.get('list_id')
                if not list_id:
                    return Response(
                        {'error': 'list_id is required for add_to_list action'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                count = service.bulk_add_to_list(contact_ids, list_id)
                message = f'{count} contact(s) added to list'
            elif action == 'delete':
                count = service.bulk_delete(contact_ids)
                message = f'{count} contact(s) deleted'
            elif action == 'add_tag':
                tag_name = request.data.get('tag')
                if not tag_name:
                    return Response({'error': 'tag is required'}, status=status.HTTP_400_BAD_REQUEST)
                tag, _created = Tag.objects.get_or_create(
                    name=tag_name,
                    user=request.user,
                    defaults={'category': 'general'},
                )
                contacts = Contact.objects.filter(id__in=contact_ids, user=request.user)
                trigger_service = DripTriggerService()
                for contact in contacts:
                    contact.tags.add(tag)
                    trigger_service.handle_tag_added(contact, tag, request.user)
                count = contacts.count()
                message = f'{count} contact(s) tagged'
            else:
                return Response(
                    {'error': f'Unknown action: {action}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({'success': True, 'message': message, 'count': count})
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class BulkEmailSendView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .bulk_email_service import BulkEmailService

        contact_ids = request.data.get('contact_ids')
        list_id = request.data.get('list_id')
        subject = request.data.get('subject')
        html_content = request.data.get('html_content')
        plain_text_content = request.data.get('plain_text_content')

        if not subject or not html_content:
            return Response(
                {'error': 'subject and html_content are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not contact_ids and not list_id:
            return Response(
                {'error': 'Either contact_ids or list_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            service = BulkEmailService(request.user)
            if list_id:
                results = service.send_to_list(
                    list_id, subject, html_content, plain_text_content,
                )
            else:
                results = service.send_to_contacts(
                    contact_ids, subject, html_content, plain_text_content,
                )
            return Response({
                'message': f'Sent {results["sent"]} of {results["total"]} emails',
                'results': results,
            })
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response(
                {'error': f'Failed to send bulk email: {str(exc)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
