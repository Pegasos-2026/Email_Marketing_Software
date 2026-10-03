from rest_framework import viewsets,status
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser,FormParser
from django.http import HttpResponse
from django.db import IntegrityError
import csv
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models.functions import TruncHour,ExtractHour
from django.db.models import Count
from .models import Campaign,EmailTemplate,Contact,ContactList,Tag,CampaignRecipient,EmailEvent
from .serializers import CampaignSerializer,CampaignListSerializer,EmailTemplateSerializer,CampaignCreateWithTemplateSerializer,SaveCampaignAsTemplateSerializer
from .analytics_service import AnalyticsService
from .contact_service import ContactImportService,ContactBulkService
from campaigns.template_service import TemplateService,DefaultTemplateService
from .services import CampaignService
class CampaignViewSet(viewsets.ModelViewSet):
    permission_classes=[IsAuthenticated]
    serializer_class=CampaignSerializer
    def get_queryset(self):
        return Campaign.objects.filter(user=self.request.user).select_related('template','analytics').order_by('-created_at')
    def get_serializer_class(self):
        # CampaignListSerializer has schema issues in current backend;
        # keep API stable by using full serializer for list too.
        if self.action == 'list':
            return CampaignSerializer
        return CampaignSerializer
    def create(self,request,*args,**kwargs):
        serializer=self.get_serializer(data=request.data,context={'request':request})
        serializer.is_valid(raise_exception=True)
        campaign=serializer.save()
        return Response({
            'message':'Campaign Created successfully',
            'data':CampaignSerializer(campaign).data 
        },status=status.HTTP_201_CREATED)
    @action(detail=False,methods=['post'],url_path='create-from-template')
    def create_from_template(self,request):
        """
        POST /api/campaigns/create-from-template/
        Simplified campaign creation from template
        """
        serializer=CampaignCreateWithTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            service=CampaignService()
            campaign=service.create_campaign_with_recipients(user=request.user,data=serializer.validated_data)
            return Response({
                'message':'Campaign created from template successfully',
                'campaign':CampaignSerializer(campaign).data
            },status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({
                'error':str(e)
            },status=status.HTTP_400_BAD_REQUEST)
    @action(detail=True,methods=['post'],url_path='apply-template')
    def apply_template(self,request,pk=None):
        """POST /api/camapigns/{id}/apply-template/
        Apply template to existing draft campaign
        Body:{"template_id":1}
        """
        campaign=self.get_object()
        template_id=request.data.get('template_id')
        if not template_id:
            return Response({
                'error':'template_id is required'
            },status=status.HTTP_400_BAD_REQUEST)
        try:
            service=CampaignService()
            updated_campaign=service.update_campaign_from_template(campaign_id=campaign.id,template_id=template_id)
            return Response({
                'message':'Template applied successfully',
                'campaign':CampaignSerializer(updated_campaign).data
            })
        except ValueError as e:
            return Response({
                'error':str(e)
            },status=status.HTTP_400_BAD_REQUEST)
    @action(detail=True,methods=['post'],url_path='preview')
    def preview(self,request,pk=None):
        """POST /api/campaigns/{id}/preview/
        Preview campaign with sample data
        Body:{
        "sample_data":{
        "name":"John Doe",
        "email":"john@example.com"}
        }"""
        campaign=self.get_object()
        sample_data=request.data.get('sample_data')
        try:
            service=CampaignService()
            preview=service.preview_campaign_with_template(
                campaign_id=campaign.id,
                sample_data=sample_data
            )
            return Response(preview)
        except Exception as e:
            return Response({
                'error':str(e)
            },status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    @action(detail=True,methods=['get'],url_path='template-info')
    def template_info(self,request,pk=None):
        """GET /api/campaigns/{id}/template-info/
        Get template information for campaign
        """
        campaign=self.get_object()
        service=CampaignService()
        template_info=service.get_campaign_template_info(campaign.id)
        if not template_info:
            return Response({
                'message':'Campaign was not created from a template'
            })
        return Response(template_info)
    @action(detail=True,methods=['post'],url_path='save-as-template')
    def save_as_template(self,request,pk=None):
        """POST /api/campaigns/{id}/save-as-template/
        Save campaign as reusable template
        Body:{
        "name":"My Template",
        "category":"promotional",
        "description":"...",
        "is_public":false
        }
        """
        campaign=self.get_object()
        serializer=SaveCampaignAsTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            service=CampaignService()
            template=service.save_campaign_as_template(
                campaign_id=campaign.id,
                template_data=serializer.validated_data
            )
            from campaigns.serializers import EmailTemplateSerializer
            return Response({
                'message':'Campaign saved as template successfully',
                'template':EmailTemplateSerializer(template).data
            },status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'error':str(e)
            },status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    def update(self,request,*args,**kwargs):
        instance=self.get_object()
        if instance.user != request.user:
            return Response({
                'error':'you do not have permission to edit this campaign'
            },status=status.HTTP_403_FORBIDDEN)
        if instance.status =='sent':
            return Response({
                'error':'Cannot edit a sent Campaign'
            },status=status.HTTP_400_BAD_REQUEST)
        serializer=self.get_serializer(instance,data=request.data,partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response({
            'message':'Campaign updated successfully',
            'data':serializer.data
        })
    def destroy(self, request, *args, **kwargs):
        instance=self.get_object()
        if instance.status in['sending','sent']:
            return Response({
                'error':'Cannot delete a sent or seing campaign'
            },status=status.HTTP_400_BAD_REQUEST)
        self.perform_destroy(instance)
        return Response({
            'error':'Campaign deleted successfully'
        },status=status.HTTP_204_NO_CONTENT)
    @action(detail=True,methods=['post'])
    def send(self,request,pk=None):
        campaign=self.get_object()
        if campaign.status=='sent':
            return Response({
                'error':'Campaign already sent'
            },status=status.HTTP_400_BAD_REQUEST)
        if not campaign.recipients.exists():
            return Response({
                'error':'No recipient added to campaign'
            },status=status.HTTP_400_BAD_REQUEST)
        try:
            if not hasattr(campaign,'content'):
                return Response({
                    'error':'Campaign Content not found'
                },status=status.HTTP_400_BAD_REQUEST)
            service=CampaignService()
            result=service.send_campaign(campaign.id)
            return Response({
                'message':'Campaign sent successfully',
                'result':result
            },status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({
                'error':str(e)
            },status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error':str(e)
            },status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    @action(detail=True,methods=['post'])
    def schedule(self,request,pk=None):
        campaign=self.get_object()
        scheduled_at=request.data.get('scheduled_at')
        if not scheduled_at:
            return Response({
                'error':'scheduled_at s required'
            },status=status.HTTP_400_BAD_REQUEST)
        campaign.scheduled_at=scheduled_at
        campaign.status='scheduled'
        campaign.save()
        return Response({
            'message':'Campaign Scheduled successfully',
            'data':CampaignSerializer(campaign).data
        })
    @action(detail=False,methods=['get'])
    def stats(self,request):
        qs=Campaign.objects.filter(user=request.user)
        total=qs.count()
        draft=qs.filter(status='draft').count()
        scheduled=qs.filter(status='scheduled').count()
        sent=qs.filter(status='sent').count()
        return Response({
            'total':total,
            'draft':draft,
            'scheduled':scheduled,
            'sent':sent
        })
class DashboardAnalyticsView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request):
        service=AnalyticsService()
        data=service.get_dashboard_overview(request.user)
        return Response(data)
class CampaignAnalyticsView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self,request,campaign_id):
        try:
            campaign=Campaign.objects.get(id=campaign_id,user=request.user)
            service=AnalyticsService()
            data=service.get_campaign_stats(campaign.id)
            return Response(data)
        except Campaign.DoesNotExist:
            return Response({'error':'Not found'},status=404)
class RefreshAnalyticsView(APIView):
    permission_classes=[IsAuthenticated]
    def post(self,request,campaign_id):
        try:
            campaign=Campaign.objects.get(id=campaign_id,user=request.user)
            service=AnalyticsService()
            analytics=service.update_campaign_analytics(campaign.id)
            return Response({
                'message':'Refreshed',
                'open_rate':analytics.open_rate,
                'click_rate':analytics.click_rate
            })
        except Campaign.DoesNotExist:
            return Response({'error':'Not found'},status=404)
class ContactImportView(APIView):
    """POST /api/contacts/inport/
    Upload CSV to import contacts"""
    permission_classes=[IsAuthenticated]
    parser_classes=[MultiPartParser,FormParser]
    def post(self,request):
        service=ContactImportService(request.user)
        try:
            #Validate file
            csv_file=request.FILES.get('file')
            service.validate_csv_file(csv_file)
            #Parse CSV
            rows=service.parse_csv_basic(csv_file)
            if rows:
                service.validate_csv_headers(rows[0].keys())
            list_id=request.data.get('list_id')
            result=service.import_contacts(rows,list_id)
            return Response({
                'success':True,
                'summary':result
            },status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'error':f'Unexpected error:{str(e)}'
            },status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class ContactExportView(APIView):
    """GET/api/contacts/export"""
    permission_classes=[IsAuthenticated]
    def get(self,request):
        service=ContactImportService(request.user)
        list_id=request.query_params.get('list_id')
        try:
            contacts=service.export_contacts(list_id)
            response=HttpResponse(content_type='text/csv')
            response['Content-Disposition']='attachment;filename="contacts.csv"'
            if contacts:
                writer=csv.DictWriter(response,fieldnames=contacts[0].keys())
                writer.writeheader()
                writer.writerows(contacts)
            return Response
        except Exception as e:
            return Response({
                'error':str(e)
            },status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class ContactImportTemplateView(APIView):
    """GET /api/contacts/import-template/
    Download CSV template"""
    permission_classes=[IsAuthenticated]
    def get(self,request):
        service=ContactImportService(request.user)
        template_data=service.get_import_template()
        response=HttpResponse(content_type='text/csv')
        response['Content-Disposition']='attachment; filename="contact_template.csv"'
        writer=csv.DictWriter(response,fieldnames=template_data[0].keys())
        writer.writeheader()
        writer.writerows(template_data)
        return response
class ContactBulkActionsView(APIView):
    """POST /api/contacts/bulk-actions
    perform bulk ctions on contacts"""
    permission_classes=[IsAuthenticated]
    def post(self,request):
        service=ContactBulkService(request.user)
        action=request.data.get('action')
        contact_ids=request.data.get('contact_ids',[])
        if not action or not contact_ids:
            return Response({
                'error':'action and contact_ids are required'
            },status=status.HTTP_400_BAD_REQUEST)
        try:
            if action=='subscribe':
                count=service.bulk_subscribe(contact_ids)
                message=f'{count} contact(s) subscribed'
            elif action=='unsubscribe':
                count=service.bulk_unsubscribe(contact_ids)
                message=f'{count} contact(s) unsubscribed'
            elif action=='add_to_list':
                list_id=request.data.get('list_id')
                if not list_id:
                    return Response({
                        'error':'list_id is required for add_to_list_action'
                    },status=status.HTTP_400_BAD_REQUEST)
                count=service.bulk_add_to_list(contact_ids,list_id)
                message=f'{count} contact(s) added to list'
            elif action =='delete':
                count=service.bulk_delete(contact_ids)
                message=f'{count} contact(s) deleted'
            else:
                return Response({
                    'error':f'Unknown action:{action}'
                },status=status.HTTP_400_BAD_REQUEST)
            return Response({
                'success':True,
                'message':message,
                'count':count
            })
        except ValueError as e:
            return Response({
                'error':str(e)
            },status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error':f'Unexpected error:{str(e)}'
            },status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class BulkEmailSendView(APIView):
    """POST /api/campaigns/bulk-send/
    Send email to multiple contacts or a contact list
    Body:
    {
        "contact_ids": [1, 2, 3],  # OR
        "list_id": 5,              # Contact list ID
        "subject": "Email Subject",
        "html_content": "<html>...</html>",
        "plain_text_content": "Plain text..."  # Optional
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        from .bulk_email_service import BulkEmailService
        
        contact_ids = request.data.get('contact_ids')
        list_id = request.data.get('list_id')
        subject = request.data.get('subject')
        html_content = request.data.get('html_content')
        plain_text_content = request.data.get('plain_text_content')
        
        if not subject or not html_content:
            return Response({
                'error': 'subject and html_content are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not contact_ids and not list_id:
            return Response({
                'error': 'Either contact_ids or list_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            service = BulkEmailService(request.user)
            
            if list_id:
                results = service.send_to_list(
                    list_id,
                    subject,
                    html_content,
                    plain_text_content
                )
            else:
                results = service.send_to_contacts(
                    contact_ids,
                    subject,
                    html_content,
                    plain_text_content
                )
            
            return Response({
                'message': f'Sent {results["sent"]} of {results["total"]} emails',
                'results': results
            }, status=status.HTTP_200_OK)
            
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': f'Failed to send bulk email: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
def sendgrid_webhook(request):
    events = request.data
    for event in events:
        email = event.get('email')
        event_type = event.get('event')
        if not email or not event_type:
            continue

        contact_qs = Contact.objects.filter(email=email)
        if contact_qs.count() != 1:
            continue
        contact = contact_qs.first()

        recipient = CampaignRecipient.objects.filter(contact=contact).last()
        if not recipient:
            continue

        if event_type == 'bounce':
            EmailEvent.objects.create(campaign_recipient=recipient, event_type='bounced', event_data=event)
            contact.is_subscribed = False
            contact.save()
        elif event_type == 'spamreport':
            EmailEvent.objects.create(campaign_recipient=recipient, event_type='spam', event_data=event)
            contact.is_subscribed = False
            contact.save()
        elif event_type == 'unsubscribe':
            EmailEvent.objects.create(campaign_recipient=recipient, event_type='unsubscribed', event_data=event)
            contact.is_subscribed = False
            contact.save()

    return Response({'status': 'ok'})


class TemplateListView(APIView):
    """GET /api/templates/
    List all available templates
    """
    permission_classes=[IsAuthenticated]
    def get(self,request):
        service=TemplateService(request.user)
        category=request.query_params.get('category')
        templates=service.get_available_templates(category)
        serializer=EmailTemplateSerializer(templates,many=True)
        return Response({
            'templates':serializer.data,
            'categories':dict(service.get_categories())
        })
class TemplateDetailView(APIView):
    """
    GET /api/templates/{id}/
    Get specific templates
    """
    permission_classes=[IsAuthenticated]
    def get(self,request,template_id):
        try:
            service=TemplateService(request.user)
            template=service.get_template(template_id)
            serializer=EmailTemplateSerializer(template)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error':'Template not found'},
                status=status.HTTP_404_NOT_FOUND
            )
class TemplateCreateView(APIView):
    """
    POST /api/templates/
    create new template
    """
    permission_classes=[IsAuthenticated]
    def post(self,request):
        try:
            service=TemplateService(request.user)
            template=service.create_template(request.data)
            serializer=EmailTemplateSerializer(template)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'error':str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
class TemplateUpdateView(APIView):
    """
    PUT /api/templates/{id}/
    Update template
    """
    permission_classes=[IsAuthenticated]
    def put(self,request,template_id):
        try:
            service=TemplateService(request.user)
            template=service.update_template(template_id,request.data)
            serializer=EmailTemplateSerializer(template)
            return Response(serializer.data)
        except EmailTemplate.DoesNotExist:
            return Response(
                {'error':'Template not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error':str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
class TemplateDeleteView(APIView):
    """
    DELETE /api/templates/{id}/
    Delete template
    """
    permission_classes=[IsAuthenticated]
    def delete(self,request,template_id):
        try:
            service=TemplateService(request.user)
            service.delete_template(template_id)
            return Response(
                {'message':'Template deleted'},
                status=status.HTTP_204_NO_CONTENT
            )
        except EmailTemplate.DoesNotExist:
            return Response(
                {'error':'template not found'},
                status=status.HTTP_404_NOT_FOUND
            )
class TemplateDuplicateView(APIView):
    """
    POST /api/templates/{id}/duplicate/
    Duplicate template
    """
    permission_classes=[IsAuthenticated]
    def post(self,request,template_id):
        try:
            service=TemplateService(request.user)
            duplicate=service.duplicate_template(template_id)
            serializer=EmailTemplateSerializer(duplicate)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'error':'template not found'},
                status=status.HTTP_404_NOT_FOUND
            )
class TemplatePreviewView(APIView):
    """POST /api/templates/{id}/preview/
    preview template with sample data"""
    permission_classes=[IsAuthenticated]
    def post(self,request,template_id):
        try:
            service=TemplateService(request.user)
            #Get context from rrquest or user
            context=request.data.get('context',{
                'name':'John Doe',
                'email':'john@example.com',
                'company':'Acme Corp',
                'unsubscribe_url':'https://example.com/unsubscribe'
            })
            rendered=service.render_template(template_id,context)
            return Response(rendered)
        except EmailTemplate.DoesNotExist:
            return Response(
                {'error':'Template not found'},
                status=status.HTTP_404_NOT_FOUND
            )
class CreateDefaultTemplatesView(APIView):
    """
     POST /api/templates/create-defaults/
     Create default starter templates
     """
    def post(self,request):
        templates=DefaultTemplateService.create_default_template(request.user)
        serializer=EmailTemplateSerializer(templates,many=True)
        return Response({
            'message':f'{len(templates)} default templates created',
            'templates':serializer.data
        },status=status.HTTP_201_CREATED)
class PopularTemplateView(APIView):
    """
    GET /api/templates/popular/
    Get most used templates
    """
    permission_classes=[IsAuthenticated]
    def get(self,request):
        service=TemplateService(request.user)
        limit=int(request.query_params.get('limit',10))
        templates=service.get_popular_templates(limit)
        serializer=EmailTemplateSerializer(templates,many=True)
        return Response({'templates':serializer.data})


class ContactListView(APIView):
    permission_classes=[IsAuthenticated]

    def get(self, request):
        contacts = Contact.objects.filter(user=request.user).prefetch_related('tags').order_by('-created_at')
        data = []
        for contact in contacts:
            full_name = contact.name or ''
            parts = full_name.split(' ', 1)
            first_name = parts[0] if parts else ''
            last_name = parts[1] if len(parts) > 1 else ''
            data.append({
                'id': contact.id,
                'email': contact.email,
                'first_name': first_name,
                'last_name': last_name,
                'subscribed': contact.is_subscribed,
                'tags': [t.name for t in contact.tags.all()],
            })
        return Response(data)


class ContactDeleteView(APIView):
    permission_classes=[IsAuthenticated]

    def delete(self, request, contact_id):
        try:
            contact = Contact.objects.get(id=contact_id, user=request.user)
            contact.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Contact.DoesNotExist:
            return Response({'error': 'Contact not found'}, status=status.HTTP_404_NOT_FOUND)


class ContactCreateView(APIView):
    """POST /api/campaigns/contacts/create/
    Create a new contact"""
    permission_classes=[IsAuthenticated]

    def post(self, request):
        try:
            email = request.data.get('email')
            name = request.data.get('name', '')
            is_subscribed = request.data.get('is_subscribed', True)
            list_ids = request.data.get('list_ids', [])

            if not email:
                return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

            email = email.strip().lower()
            # Reuse an existing contact with this email for the current user only.
            contact = Contact.objects.filter(email=email, user=request.user).first()
            if contact is None:
                contact = Contact.objects.create(
                    user=request.user,
                    email=email,
                    name=name,
                    is_subscribed=is_subscribed,
                )
            else:
                # Keep the existing contact record for this user, but ensure the latest name/subscription values are saved.
                contact.name = name
                contact.is_subscribed = is_subscribed
                contact.save()

            # Add to contact lists for current user.
            for list_id in list_ids:
                try:
                    contact_list = ContactList.objects.get(id=list_id, user=request.user)
                    contact.lists.add(contact_list)
                except ContactList.DoesNotExist:
                    pass

            return Response({
                'message': 'Contact created successfully',
                'contact': {
                    'id': contact.id,
                    'email': contact.email,
                    'name': contact.name,
                    'is_subscribed': contact.is_subscribed,
                    'lists': [{'id': l.id, 'name': l.name} for l in contact.lists.all()]
                }
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ContactListsView(APIView):
    """GET/POST /api/campaigns/contact-lists/
    List all contact lists or create new one"""
    permission_classes=[IsAuthenticated]

    def get(self, request):
        """Get all contact lists for user"""
        lists = ContactList.objects.filter(user=request.user).annotate(
            contact_count=Count('contacts')
        ).order_by('name')
        
        data = []
        for contact_list in lists:
            data.append({
                'id': contact_list.id,
                'name': contact_list.name,
                'description': contact_list.description,
                'contact_count': contact_list.contact_count,
                'created_at': contact_list.created_at
            })
        return Response(data)

    def post(self, request):
        """Create a new contact list"""
        try:
            name = request.data.get('name')
            description = request.data.get('description', '')

            if not name:
                return Response({'error': 'Name is required'}, status=status.HTTP_400_BAD_REQUEST)

            contact_list = ContactList.objects.create(
                user=request.user,
                name=name,
                description=description
            )

            return Response({
                'message': 'Contact list created successfully',
                'list': {
                    'id': contact_list.id,
                    'name': contact_list.name,
                    'description': contact_list.description,
                    'contact_count': 0
                }
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ContactListDetailView(APIView):
    """GET/DELETE /api/campaigns/contact-lists/{id}/
    Get or delete a contact list"""
    permission_classes=[IsAuthenticated]

    def get(self, request, list_id):
        """Get contact list with all contacts"""
        try:
            contact_list = ContactList.objects.get(id=list_id, user=request.user)
            contacts = []
            for contact in contact_list.contacts.all():
                contacts.append({
                    'id': contact.id,
                    'email': contact.email,
                    'name': contact.name,
                    'is_subscribed': contact.is_subscribed
                })

            return Response({
                'id': contact_list.id,
                'name': contact_list.name,
                'description': contact_list.description,
                'contact_count': len(contacts),
                'contacts': contacts
            })
        except ContactList.DoesNotExist:
            return Response({'error': 'Contact list not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, list_id):
        """Delete a contact list"""
        try:
            contact_list = ContactList.objects.get(id=list_id, user=request.user)
            contact_list.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ContactList.DoesNotExist:
            return Response({'error': 'Contact list not found'}, status=status.HTTP_404_NOT_FOUND)


class ContactImportCSVView(APIView):
    """POST /api/campaigns/contacts/import/
    Upload CSV file to import contacts"""
    permission_classes=[IsAuthenticated]
    parser_classes=[MultiPartParser, FormParser]

    def post(self, request):
        try:
            csv_file = request.FILES.get('file')
            list_id = request.data.get('list_id')

            if not csv_file:
                return Response({'error': 'No file provided'}, status=status.HTTP_400_BAD_REQUEST)

            service = ContactImportService(request.user)
            service.validate_csv_file(csv_file)
            rows = service.parse_csv_basic(csv_file)

            if rows:
                service.validate_csv_headers(rows[0].keys())

            result = service.import_contacts(rows, list_id)

            return Response({
                'success': True,
                'summary': result
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ContactExportCSVView(APIView):
    """GET /api/campaigns/contacts/export/
    Export contacts as CSV"""
    permission_classes=[IsAuthenticated]

    def get(self, request):
        try:
            list_id = request.query_params.get('list_id')
            
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
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ContactImportTemplateView(APIView):
    """GET /api/campaigns/contacts/import-template/
    Download CSV template"""
    permission_classes=[IsAuthenticated]

    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="contact_template.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['email', 'name', 'is_subscribed'])
        writer.writerow(['john@example.com', 'John Doe', 'true'])
        writer.writerow(['jane@example.com', 'Jane Smith', 'true'])
        
        return response
    