from rest_framework import viewsets,status
from rest_framework.views import APIView
from rest_framework.decorators import api_view
from rest_framework.parsers import MultiPartParser,FormParser
from django.http import HttpResponse
import csv
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models.functions import TruncHour,ExtractHour
from django.db.models import Count, Q
from .models import Campaign,Contact,ContactList,Tag,CampaignRecipient,DripCampaign,DripStep,DripCondition,DripEmailLog,DripEnrollment,FollowUpTriggerLog,CampaignEventRule,StepFollowUpRule,EmailTemplate,EmailEvent
from .serializers import CampaignSerializer,CampaignListSerializer,ContactSerailizer,EmailTemplateSerializer,CampaignCreateWithTemplateSerializer,SaveCampaignAsTemplateSerializer,EmailTemplateListSerializer
from .analytics_service import AnalyticsService
from .contact_service import ContactImportService,ContactBulkService
from .drip_service import DripEngine,DripEnrollmentService,DripTriggerService,FollowUpService
from .drip_serializers import DripCampaignSerializer,DripCampaignListSerializer,DripStepSerializer,DripEnrollmentSerializer,DripEmailLogSerializer,DripCampaignAnalyticsSerializer,WebhookEventSerializer,ManualEnrollmentSerializer,StepFollowUpRuleSerializer,CampaignEventRuleSerializer,FollowUpTriggerLogSerializer
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .template_service import TemplateService,DefaultTemplateService
import logging
logger=logging.getLogger(__name__)
class CampaignViewSet(viewsets.ModelViewSet):
    permission_classes=[IsAuthenticated]
    def get_queryset(self):
        return Campaign.objects.filter(user=self.request.user).order_by('-created_at')
    def get_serializer_class(self):
        if self.action == 'list':
            return CampaignListSerializer
        return CampaignSerializer
    def create(self,request,*args,**kwargs):
        serializer=self.get_serializer(data=request.data,context={'request':request})
        serializer.is_valid(raise_exception=True)
        campaign=serializer.save()
        return Response({
            'message':'Campaign Created successfully',
            'data':CampaignSerializer(campaign).data 
        },status=status.HTTP_201_CREATED)
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
        instance = self.get_object()
        if instance.user != request.user:
            return Response(
                {'error': 'You do not have permission to delete this campaign'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if instance.status in ('sending', 'sent'):
            return Response(
                {'error': 'Cannot delete a sent or sending campaign'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            self.perform_destroy(instance)
        except Exception as exc:
            err = str(exc).lower()
            if 'no such table' in err or 'does not exist' in err:
                from django.db import connection

                if connection.vendor != 'sqlite':
                    from app.campaigns.schema_utils import create_missing_m2m_tables

                    create_missing_m2m_tables()
                    self.perform_destroy(instance)
                else:
                    logger.exception('Campaign delete failed for campaign %s', instance.id)
                    return Response(
                        {'error': f'Failed to delete campaign: {exc}'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
            else:
                logger.exception('Campaign delete failed for campaign %s', instance.id)
                return Response(
                    {'error': f'Failed to delete campaign: {exc}'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        return Response(status=status.HTTP_204_NO_CONTENT)
    @action(detail=True,methods=['post'])
    def send(self,request,pk=None):
        campaign=self.get_object()
        pending=campaign.recipients.filter(status__in=['pending', 'failed'])
        if campaign.status == 'sent' and not pending.exists():
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
            from .services import CampaignService
            from app.campaigns.send_worker import is_campaign_send_active, start_campaign_send_async

            service=CampaignService()
            if is_campaign_send_active(campaign.id):
                return Response(
                    {'error': 'Campaign is already sending. Open analytics to track progress.'},
                    status=status.HTTP_409_CONFLICT,
                )
            try:
                pending_count=service.assert_send_ready(campaign.id)
            except ValueError as exc:
                return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            async_mode=request.data.get('async', True)
            if async_mode in (False, 'false', '0', 0):
                result=service.send_campaign(campaign.id)
                if result.get('success', 0) == 0:
                    return Response(
                        {
                            'error': result.get('message', 'No emails were delivered'),
                            'result': result,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                message = result.get('message', 'Campaign sent successfully')
                return Response(
                    {
                        'message': message,
                        'async': False,
                        'result': result,
                    },
                    status=status.HTTP_200_OK,
                )

            if not start_campaign_send_async(campaign.id):
                return Response(
                    {'error': 'Campaign is already sending. Open analytics to track progress.'},
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(
                {
                    'message': (
                        f'Sending started to {pending_count} recipient(s). '
                        'Track live progress on the analytics page — do not click Send again.'
                    ),
                    'async': True,
                    'campaign_id': campaign.id,
                    'result': {
                        'success': 0,
                        'failed': 0,
                        'pending_remaining': pending_count,
                        'total': pending_count,
                    },
                },
                status=status.HTTP_202_ACCEPTED,
            )
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception('Campaign send failed')
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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
    @action(detail=False,methods=['post'],url_path='create-from-template')
    def create_from_template(self,request):
        serializer=CampaignCreateWithTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            from .services import CampaignService
            service=CampaignService()
            campaign=service.create_campaign_with_recipients(
                user=request.user,
                data=serializer.validated_data,
            )
            return Response({
                'message':'Campaign created from template successfully',
                'campaign':CampaignSerializer(campaign).data,
            },status=status.HTTP_201_CREATED)
        except ValueError as e:
            return Response({'error':str(e)},status=status.HTTP_400_BAD_REQUEST)
    @action(detail=False,methods=['get'])
    def stats(self,request):
        qs=Campaign.objects.filter(user=request.user)
        return Response({
            'total':qs.count(),
            'draft':qs.filter(status='draft').count(),
            'scheduled':qs.filter(status='scheduled').count(),
            'sent':qs.filter(status='sent').count(),
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
            data=service.get_campaign_stats(campaign.id)
            return Response(data)
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
            return response
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
            elif action=='add_tag':
                tag_name=request.data.get('tag')
                if not tag_name:
                    return Response({'error':'tag is required'},status=400)
                tag,created=Tag.objects.get_or_create(
                    name=tag_name,
                    user=request.user,
                    defaults={'category': 'general'},
                )
                contacts=Contact.objects.filter(id__in=contact_ids,user=request.user)
                trigger_service=DripTriggerService()
                for contact in contacts:
                    contact.tags.add(tag)
                    trigger_service.handle_tag_added(contact, tag, request.user)
                count=contacts.count()
                message=f'{count} contact(s) tagged'
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
class ContactViewSet(viewsets.ModelViewSet):
    serializer_class=ContactSerailizer
    permission_classes=[IsAuthenticated]
    def get_queryset(self):
        queryset=Contact.objects.filter(user=self.request.user)
        tag_param=self.request.query_params.get('tags')
        match_type=self.request.query_params.get('match','any')
        if tag_param:
            tag_list=[tag.strip() for tag in tag_param.split(',') if tag.strip()]
            if match_type =='all':
                #AND Logic
                queryset=queryset.filter(tags__name__in=tag_list).annotate(matched_tags=Count('tags',filter=Q(tags__name__in=tag_list))).filter(matched_tags=len(tag_list))
            else:
                queryset=queryset.filter(tags__name__in=tag_list)
        return queryset.distinct()
    def perform_create(self, serializer):
        contact = serializer.save(user=self.request.user)
        DripTriggerService().handle_contact_added(contact, self.request.user)
    def get_serializer_context(self):
        context=super().get_serializer_context()
        context.update({"request":self.request})
        return context
    @action(detail=True,methods=['post'])
    def add_tag(self,request,pk=None):
        contact=self.get_object()
        tag_name=request.data.get('tag')
        if not tag_name:
            return Response({'error':'Tag name required'},status=400)
        tag,created=Tag.objects.get_or_create(
            name=tag_name,
            user=request.user,
            defaults={'category': 'general'},
        )
        contact.tags.add(tag)
        DripTriggerService().handle_tag_added(contact, tag, request.user)
        return Response({'message':'Tag added successfully'}) 
@api_view(["POST"])
def sendgrid_webhook(request):
    events = request.data if isinstance(request.data, list) else [request.data]
    campaign_ids = set()
    for event in events:
        if not isinstance(event, dict):
            continue
        email = event.get("email")
        event_type = event.get("event")
        if not email or not event_type:
            continue

        recipient = None
        recipient_id = event.get("campaign_recipient_id")
        if recipient_id:
            recipient = CampaignRecipient.objects.filter(id=recipient_id).first()
        if not recipient:
            campaign_id = event.get("campaign_id")
            contact_qs = Contact.objects.filter(email=email)
            if contact_qs.count() != 1:
                continue
            contact = contact_qs.first()
            recipient_qs = CampaignRecipient.objects.filter(contact=contact)
            if campaign_id:
                recipient_qs = recipient_qs.filter(campaign_id=campaign_id)
            recipient = recipient_qs.order_by('-id').first()
        if not recipient:
            continue

        contact = recipient.contact

        if event_type == "bounce":
            EmailEvent.objects.create(
                campaign_recipient=recipient,
                event_type="bounced",
                event_data=event,
            )
            recipient.status='failed'
            recipient.save(update_fields=['status'])
            bounce_type = event.get('type') or event.get('bounce_type') or ''
            if str(bounce_type).lower() in ['hard', 'invalid', 'permanent', 'undeliverable']:
                contact.is_subscribed=False
                contact.save(update_fields=['is_subscribed'])
        elif event_type=="delivered":
            EmailEvent.objects.create(
                campaign_recipient=recipient,
                event_type="delivered",
                event_data=event,
            )
        elif event_type=="spamreport":
            EmailEvent.objects.create(
                campaign_recipient=recipient,
                event_type="spam",
                event_data=event,
            )
            recipient.status='failed'
            recipient.save(update_fields=['status'])
            contact.is_subscribed=False
            contact.save(update_fields=['is_subscribed'])
        elif event_type=="unsubscribe":
            EmailEvent.objects.create(
                campaign_recipient=recipient,
                event_type="unsubscribed",
                event_data=event,
            )
            recipient.status='failed'
            recipient.save(update_fields=['status'])
            contact.is_subscribed=False
            contact.save(update_fields=['is_subscribed'])
        campaign_ids.add(recipient.campaign.id)
    for campaign_id in campaign_ids:
        AnalyticsService().update_campaign_analytics(campaign_id)
    return Response({"status":"ok"})
# -------------------------------------------------------
# 1. DRIP CAMPAIGN VIEWS
# -------------------------------------------------------

class DripCampaignListCreateView(APIView):
    """
    GET  /api/drip/campaigns/        — List all drip campaigns
    POST /api/drip/campaigns/        — Create a new drip campaign
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Returns all drip campaigns belonging to the logged-in user.
        """
        campaigns = DripCampaign.objects.filter(
            user=request.user
        )
        serializer = DripCampaignListSerializer(campaigns, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Creates a new drip campaign with steps.
        Steps can be passed nested inside the campaign data.
        """
        serializer = DripCampaignSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            campaign = serializer.save()
            logger.info(
                f"Drip campaign '{campaign.name}' created "
                f"by {request.user.email}"
            )
            return Response(
                DripCampaignSerializer(campaign, context={'request': request}).data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class DripCampaignDetailView(APIView):
    """
    GET    /api/drip/campaigns/<id>/  — Get campaign details
    PUT    /api/drip/campaigns/<id>/  — Update campaign
    DELETE /api/drip/campaigns/<id>/  — Delete campaign
    """

    permission_classes = [IsAuthenticated]

    def get_object(self, campaign_id, user):
        """
        Find campaign by ID and make sure it belongs to this user.
        """
        return get_object_or_404(
            DripCampaign,
            id=campaign_id,
            user=user
        )

    def get(self, request, campaign_id):
        """
        Returns full details of a single drip campaign including steps.
        """
        campaign = self.get_object(campaign_id, request.user)
        serializer = DripCampaignSerializer(
            campaign,
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, campaign_id):
        """
        Updates a drip campaign.
        Only allowed if campaign is in draft or paused status.
        """
        campaign = self.get_object(campaign_id, request.user)

        # Cannot edit an active or archived campaign
        if campaign.status in ['active', 'archived']:
            return Response(
                {'error': 'Active or archived campaign cannot be edited. Pause it first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = DripCampaignSerializer(
            campaign,
            data=request.data,
            partial=True,
            context={'request': request}
        )

        if serializer.is_valid():
            campaign = serializer.save()
            return Response(
                DripCampaignSerializer(campaign, context={'request': request}).data,
                status=status.HTTP_200_OK
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, campaign_id):
        """
        Deletes a drip campaign.
        Also stops all active enrollments for this campaign.
        """
        campaign = self.get_object(campaign_id, request.user)

        # Stop all active enrollments before deleting
        DripEnrollment.objects.filter(
            drip_campaign=campaign,
            status='active'
        ).update(status='stopped')

        campaign_name = campaign.name
        campaign.delete()

        logger.info(
            f"Drip campaign '{campaign_name}' deleted "
            f"by {request.user.email}"
        )

        return Response(
            {'message': f"Campaign '{campaign_name}' deleted successfully."},
            status=status.HTTP_200_OK
        )


# -------------------------------------------------------
# 2. CAMPAIGN STATUS CONTROL VIEWS
# -------------------------------------------------------

class DripCampaignActivateView(APIView):
    """
    POST /api/drip/campaigns/<id>/activate/  — Activate a campaign
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, campaign_id):
        """
        Activates a draft or paused campaign.
        Once active, it will start enrolling contacts automatically.
        """
        campaign = get_object_or_404(
            DripCampaign,
            id=campaign_id,
            user=request.user
        )

        # Campaign must have at least one step to activate
        if not campaign.steps.exists():
            return Response(
                {'error': 'Campaign must have at least one step before activating.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Only draft or paused campaigns can be activated
        if campaign.status not in ['draft', 'paused']:
            return Response(
                {'error': f"Campaign is already {campaign.status}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        campaign.status = 'active'
        campaign.save()

        enrollment_service = DripEnrollmentService()
        enrolled_count = 0
        if campaign.trigger_type == 'tag_added' and campaign.trigger_tag_id:
            enrolled_count = enrollment_service.enroll_by_tag(
                campaign.trigger_tag, campaign
            )
        elif campaign.trigger_type == 'contact_added':
            for contact_list in campaign.lists.all():
                enrolled_count += enrollment_service.enroll_list(
                    contact_list, campaign
                )

        logger.info(f"Campaign '{campaign.name}' activated")

        return Response(
            {
                'message': f"Campaign '{campaign.name}' is now active.",
                'enrolled_count': enrolled_count,
            },
            status=status.HTTP_200_OK
        )


class DripCampaignPauseView(APIView):
    """
    POST /api/drip/campaigns/<id>/pause/  — Pause a campaign
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, campaign_id):
        """
        Pauses an active campaign.
        Existing enrollments will be paused too.
        """
        campaign = get_object_or_404(
            DripCampaign,
            id=campaign_id,
            user=request.user
        )

        if campaign.status != 'active':
            return Response(
                {'error': 'Only active campaigns can be paused.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        campaign.status = 'paused'
        campaign.save()

        logger.info(f"Campaign '{campaign.name}' paused")

        return Response(
            {'message': f"Campaign '{campaign.name}' has been paused."},
            status=status.HTTP_200_OK
        )


# -------------------------------------------------------
# 3. DRIP STEP VIEWS
# -------------------------------------------------------

class DripStepListCreateView(APIView):
    """
    GET  /api/drip/campaigns/<id>/steps/  — List all steps
    POST /api/drip/campaigns/<id>/steps/  — Add a new step
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, campaign_id):
        """
        Returns all steps of a drip campaign in order.
        """
        campaign = get_object_or_404(
            DripCampaign,
            id=campaign_id,
            user=request.user
        )

        steps = DripStep.objects.filter(
            drip_campaign=campaign
        ).order_by('step_number')

        serializer = DripStepSerializer(steps, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, campaign_id):
        """
        Adds a new step to an existing drip campaign.
        """
        campaign = get_object_or_404(
            DripCampaign,
            id=campaign_id,
            user=request.user
        )

        # Cannot add steps to active campaign
        if campaign.status == 'active':
            return Response(
                {'error': 'Cannot add steps to an active campaign. Pause it first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = DripStepSerializer(data=request.data)

        if serializer.is_valid():
            step = serializer.save(drip_campaign=campaign)
            return Response(
                DripStepSerializer(step).data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class DripStepDetailView(APIView):
    """
    GET    /api/drip/campaigns/<id>/steps/<step_id>/  — Get step
    PUT    /api/drip/campaigns/<id>/steps/<step_id>/  — Update step
    DELETE /api/drip/campaigns/<id>/steps/<step_id>/  — Delete step
    """

    permission_classes = [IsAuthenticated]

    def get_objects(self, campaign_id, step_id, user):
        """
        Find campaign and step — make sure both belong to this user.
        """
        campaign = get_object_or_404(
            DripCampaign,
            id=campaign_id,
            user=user
        )
        step = get_object_or_404(
            DripStep,
            id=step_id,
            drip_campaign=campaign
        )
        return campaign, step

    def get(self, request, campaign_id, step_id):
        """
        Returns details of a single step.
        """
        campaign, step = self.get_objects(campaign_id, step_id, request.user)
        serializer = DripStepSerializer(step)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, campaign_id, step_id):
        """
        Updates an existing step.
        """
        campaign, step = self.get_objects(campaign_id, step_id, request.user)

        if campaign.status == 'active':
            return Response(
                {'error': 'Cannot edit steps of an active campaign. Pause it first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = DripStepSerializer(
            step,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            step = serializer.save()
            return Response(
                DripStepSerializer(step).data,
                status=status.HTTP_200_OK
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, campaign_id, step_id):
        """
        Deletes a step from a campaign.
        """
        campaign, step = self.get_objects(campaign_id, step_id, request.user)

        if campaign.status == 'active':
            return Response(
                {'error': 'Cannot delete steps of an active campaign. Pause it first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        step_number = step.step_number
        step.delete()

        return Response(
            {'message': f"Step {step_number} deleted successfully."},
            status=status.HTTP_200_OK
        )


# -------------------------------------------------------
# 4. ENROLLMENT VIEWS
# -------------------------------------------------------

class DripEnrollmentListView(APIView):
    """
    GET /api/drip/campaigns/<id>/enrollments/  — List all enrollments
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, campaign_id):
        """
        Returns all contacts enrolled in a campaign.
        Can filter by status: ?status=active / completed / stopped
        """
        campaign = get_object_or_404(
            DripCampaign,
            id=campaign_id,
            user=request.user
        )

        enrollments = DripEnrollment.objects.filter(
            drip_campaign=campaign
        ).select_related('contact', 'current_step')

        # Filter by status if provided
        status_filter = request.query_params.get('status')
        if status_filter:
            enrollments = enrollments.filter(status=status_filter)

        serializer = DripEnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DripManualEnrollView(APIView):
    """
    POST /api/drip/campaigns/<id>/enroll/  — Manually enroll contacts
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, campaign_id):
        """
        Manually enroll one contact, multiple contacts, or a full list.

        Options:
        - contact_id: 1              → Enroll single contact
        - contact_ids: [1, 2, 3]     → Enroll multiple contacts
        - list_id: 1                 → Enroll entire contact list
        """
        campaign = get_object_or_404(
            DripCampaign,
            id=campaign_id,
            user=request.user
        )

        # Campaign must be active to enroll
        if campaign.status != 'active':
            return Response(
                {'error': 'Campaign must be active to enroll contacts.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ManualEnrollmentSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        enrollment_service = DripEnrollmentService()
        enrolled_count = 0

        def enroll_by_email(email_value):
            nonlocal enrolled_count
            email_value = email_value.strip().lower()
            contact = Contact.objects.filter(email=email_value, user=request.user).first()
            if contact is None:
                contact = Contact.objects.create(
                    user=request.user,
                    email=email_value,
                    is_subscribed=True,
                )
            result = enrollment_service.enroll_contact(contact, campaign)
            if result:
                enrolled_count += 1

        # Single contact
        if serializer.validated_data.get('contact_id'):
            contact = get_object_or_404(
                Contact,
                id=serializer.validated_data['contact_id'],
                user=request.user
            )
            result = enrollment_service.enroll_contact(contact, campaign)
            if result:
                enrolled_count = 1

        # Multiple contacts
        elif serializer.validated_data.get('contact_ids'):
            contacts = Contact.objects.filter(
                id__in=serializer.validated_data['contact_ids'],
                user=request.user
            )
            for contact in contacts:
                result = enrollment_service.enroll_contact(contact, campaign)
                if result:
                    enrolled_count += 1

        # Entire list
        elif serializer.validated_data.get('list_id'):
            contact_list = get_object_or_404(
                ContactList,
                id=serializer.validated_data['list_id'],
                user=request.user
            )
            enrolled_count = enrollment_service.enroll_list(
                contact_list,
                campaign
            )

        elif serializer.validated_data.get('email'):
            enroll_by_email(serializer.validated_data['email'])

        elif serializer.validated_data.get('emails'):
            for email_value in serializer.validated_data['emails']:
                enroll_by_email(email_value)

        return Response(
            {
                'message': f"{enrolled_count} contacts enrolled successfully.",
                'enrolled_count': enrolled_count,
            },
            status=status.HTTP_200_OK
        )


class DripEnrollmentStopView(APIView):
    """
    POST /api/drip/enrollments/<id>/stop/  — Stop a single enrollment
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, enrollment_id):
        """
        Stops a single contact's drip campaign enrollment.
        Contact will not receive any more emails from this campaign.
        """
        enrollment = get_object_or_404(
            DripEnrollment,
            id=enrollment_id,
            drip_campaign__user=request.user
        )

        if enrollment.status != 'active':
            return Response(
                {'error': f"Enrollment is already {enrollment.status}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        enrollment.status = 'stopped'
        enrollment.save()

        return Response(
            {
                'message': f"Enrollment stopped for {enrollment.contact.email}."
            },
            status=status.HTTP_200_OK
        )


# -------------------------------------------------------
# 5. ANALYTICS VIEW
# -------------------------------------------------------

class DripCampaignAnalyticsView(APIView):
    """
    GET /api/drip/campaigns/<id>/analytics/  — Get campaign analytics
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, campaign_id):
        """
        Returns full analytics for a drip campaign:
        - Total enrolled
        - Active / completed / stopped counts
        - Total emails sent and opened
        """
        campaign = get_object_or_404(
            DripCampaign,
            id=campaign_id,
            user=request.user
        )

        serializer = DripCampaignAnalyticsSerializer(campaign)
        return Response(serializer.data, status=status.HTTP_200_OK)


# -------------------------------------------------------
# 6. WEBHOOK VIEW
# -------------------------------------------------------

class WebhookEventView(APIView):
    """
    POST /api/drip/webhook/  — Receive webhook events from external systems
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Receives a webhook event from an external system.
        Automatically triggers matching drip campaigns.

        Expected data:
        {
            "contact_email": "neha@gmail.com",
            "event_name": "member_checkin",
            "event_data": { "any": "extra data" }
        }
        """
        serializer = WebhookEventSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            webhook_log = serializer.save()

            # Immediately trigger matching campaigns
            trigger_service = DripTriggerService()
            trigger_service.handle_webhook_event(webhook_log)

            logger.info(
                f"Webhook received: {webhook_log.event_name} "
                f"for {webhook_log.contact.email}"
            )

            return Response(
                {
                    'message': 'Webhook event received and processed.',
                    'event_name': webhook_log.event_name,
                },
                status=status.HTTP_200_OK
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


# -------------------------------------------------------
# 7. EMAIL LOG VIEW
# -------------------------------------------------------

class DripEmailLogView(APIView):
    """
    GET /api/drip/campaigns/<id>/logs/  — Get all email logs for a campaign
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, campaign_id):
        """
        Returns all emails sent for a campaign with their status.
        Shows which contacts opened the emails.
        """
        campaign = get_object_or_404(
            DripCampaign,
            id=campaign_id,
            user=request.user
        )

        logs = DripEmailLog.objects.filter(
            enrollment__drip_campaign=campaign
        ).select_related(
            'contact',
            'step',
            'open_tracking'
        ).order_by('-sent_at')

        serializer = DripEmailLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
#    IF email_opened on Step 2
#    THEN start "Offer Follow-up" campaign
# -------------------------------------------------------

class StepFollowUpRuleListCreateView(APIView):
    """
    GET  /api/drip/campaigns/<id>/steps/<step_id>/follow-up-rules/
         — List all follow-up rules for a step

    POST /api/drip/campaigns/<id>/steps/<step_id>/follow-up-rules/
         — Add new follow-up rule to a step
    """
    permission_classes = [IsAuthenticated]

    def get_step(self, campaign_id, step_id, user):
        campaign = get_object_or_404(DripCampaign, id=campaign_id, user=user)
        step = get_object_or_404(DripStep, id=step_id, drip_campaign=campaign)
        return campaign, step

    def get(self, request, campaign_id, step_id):
        """
        Returns all follow-up rules attached to a step.
        """
        campaign, step = self.get_step(campaign_id, step_id, request.user)

        rules = StepFollowUpRule.objects.filter(step=step)
        serializer = StepFollowUpRuleSerializer(rules, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, campaign_id, step_id):
        """
        Add a new IF/THEN follow-up rule to a step.

        Example request:
        {
            "trigger": "email_opened",
            "follow_up_campaign": 5,
            "stop_main_campaign": false
        }
        """
        campaign, step = self.get_step(campaign_id, step_id, request.user)

        if campaign.status == 'active':
            return Response(
                {'error': 'Cannot add rules to active campaign. Pause it first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = StepFollowUpRuleSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            rule = serializer.save(step=step)
            logger.info(
                f"Step follow-up rule created: "
                f"IF {rule.trigger} on Step {step.step_number} "
                f"THEN '{rule.follow_up_campaign.name}'"
            )
            return Response(
                StepFollowUpRuleSerializer(rule).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StepFollowUpRuleDetailView(APIView):
    """
    GET    /api/drip/follow-up-rules/step/<rule_id>/  — Get rule
    PUT    /api/drip/follow-up-rules/step/<rule_id>/  — Update rule
    DELETE /api/drip/follow-up-rules/step/<rule_id>/  — Delete rule
    """
    permission_classes = [IsAuthenticated]

    def get_rule(self, rule_id, user):
        return get_object_or_404(
            StepFollowUpRule,
            id=rule_id,
            step__drip_campaign__user=user,
        )

    def get(self, request, rule_id):
        rule = self.get_rule(rule_id, request.user)
        return Response(
            StepFollowUpRuleSerializer(rule).data,
            status=status.HTTP_200_OK
        )

    def put(self, request, rule_id):
        rule = self.get_rule(rule_id, request.user)
        serializer = StepFollowUpRuleSerializer(
            rule,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            rule = serializer.save()
            return Response(
                StepFollowUpRuleSerializer(rule).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, rule_id):
        rule = self.get_rule(rule_id, request.user)
        rule.delete()
        return Response(
            {'message': 'Step follow-up rule deleted successfully.'},
            status=status.HTTP_200_OK
        )


# -------------------------------------------------------
# 5. NEW — CAMPAIGN LEVEL EVENT RULE VIEWS
#    IF webhook = "purchase_done" during campaign
#    THEN start "Thank You" campaign
# -------------------------------------------------------

class CampaignEventRuleListCreateView(APIView):
    """
    GET  /api/drip/campaigns/<id>/event-rules/  — List all event rules
    POST /api/drip/campaigns/<id>/event-rules/  — Add new event rule
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, campaign_id):
        """
        Returns all campaign-level event rules.
        """
        campaign = get_object_or_404(
            DripCampaign, id=campaign_id, user=request.user
        )
        rules = CampaignEventRule.objects.filter(campaign=campaign)
        serializer = CampaignEventRuleSerializer(rules, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, campaign_id):
        """
        Add a campaign-level IF/THEN event rule.

        Example request:
        {
            "trigger": "webhook_event",
            "webhook_event_name": "purchase_done",
            "follow_up_campaign": 6,
            "stop_current_campaign": true
        }
        """
        campaign = get_object_or_404(
            DripCampaign, id=campaign_id, user=request.user
        )

        if campaign.status == 'active':
            return Response(
                {'error': 'Cannot add rules to active campaign. Pause it first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = CampaignEventRuleSerializer(
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            rule = serializer.save(campaign=campaign)
            logger.info(
                f"Campaign event rule created: "
                f"IF {rule.trigger} in '{campaign.name}' "
                f"THEN '{rule.follow_up_campaign.name}'"
            )
            return Response(
                CampaignEventRuleSerializer(rule).data,
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CampaignEventRuleDetailView(APIView):
    """
    GET    /api/drip/event-rules/<rule_id>/  — Get rule
    PUT    /api/drip/event-rules/<rule_id>/  — Update rule
    DELETE /api/drip/event-rules/<rule_id>/  — Delete rule
    """
    permission_classes = [IsAuthenticated]

    def get_rule(self, rule_id, user):
        return get_object_or_404(
            CampaignEventRule,
            id=rule_id,
            campaign__user=user
        )

    def get(self, request, rule_id):
        rule = self.get_rule(rule_id, request.user)
        return Response(
            CampaignEventRuleSerializer(rule).data,
            status=status.HTTP_200_OK
        )

    def put(self, request, rule_id):
        rule = self.get_rule(rule_id, request.user)
        serializer = CampaignEventRuleSerializer(
            rule,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            rule = serializer.save()
            return Response(
                CampaignEventRuleSerializer(rule).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, rule_id):
        rule = self.get_rule(rule_id, request.user)
        rule.delete()
        return Response(
            {'message': 'Campaign event rule deleted successfully.'},
            status=status.HTTP_200_OK
        )


# -------------------------------------------------------
# 6. NEW — FOLLOW-UP TRIGGER LOG VIEW
#    Dekhne ke liye ki kaun sa follow-up
#    kab trigger hua
# -------------------------------------------------------

class FollowUpTriggerLogView(APIView):
    """
    GET /api/drip/campaigns/<id>/follow-up-logs/
    — See all follow-ups that were triggered for a campaign
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, campaign_id):
        """
        Returns all follow-up triggers for a campaign.
        Shows which contact triggered which follow-up and when.
        """
        campaign = get_object_or_404(
            DripCampaign, id=campaign_id, user=request.user
        )

        logs = FollowUpTriggerLog.objects.filter(
            enrollment__drip_campaign=campaign
        ).select_related(
            'enrollment__contact',
            'follow_up_campaign',
            'step_rule',
            'campaign_rule',
        ).order_by('-triggered_at')

        serializer = FollowUpTriggerLogSerializer(logs, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
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
    def get(self, request, template_id):
        service = TemplateService(request.user)
        try:
            template = service.get_template(template_id)
        except EmailTemplate.DoesNotExist:
            return Response(
                {'error': 'Template not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = EmailTemplateSerializer(template)
        return Response(serializer.data)
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
    permission_classes = [IsAuthenticated]

    def put(self, request, template_id):
        service = TemplateService(request.user)
        try:
            template = service.update_template(template_id, request.data)
        except EmailTemplate.DoesNotExist:
            return Response(
                {'error': 'Template not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = EmailTemplateSerializer(template)
        return Response(serializer.data, status=status.HTTP_200_OK)
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
            return Response(status=status.HTTP_204_NO_CONTENT)
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
    permission_classes = [IsAuthenticated]

    def post(self, request):
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
    