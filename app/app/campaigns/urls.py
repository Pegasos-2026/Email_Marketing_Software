from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import (CampaignViewSet,DashboardAnalyticsView,CampaignAnalyticsView,RefreshAnalyticsView,sendgrid_webhook,DripCampaignListCreateView,DripCampaignDetailView,DripCampaignActivateView,DripCampaignPauseView,DripStepListCreateView,DripStepDetailView,DripEnrollmentListView,DripManualEnrollView,DripEnrollmentStopView,DripCampaignAnalyticsView,WebhookEventView,DripEmailLogView,StepFollowUpRuleListCreateView,StepFollowUpRuleDetailView,CampaignEventRuleListCreateView,CampaignEventRuleDetailView,FollowUpTriggerLogView,ABTestListCreateView,ABTestDetailView,ABTestRunView,ABTestResultsView,ABTestSetWinnerView,ABTestCancelView,CampaignABTestView,TemplateListView,TemplateDetailView,
                    TemplateCreateView,TemplateUpdateView,TemplateDeleteView,TemplateDuplicateView,TemplatePreviewView,
                    CreateDefaultTemplatesView,PopularTemplateView)
from campaigns.view.tracking_views import track_open,track_click
router=DefaultRouter()
router.register(r'campaigns',CampaignViewSet,basename='campaign')
urlpatterns=[
    path('',include(router.urls)),
    #tracking endpoints(public-no auth required)
    path('analytics/dashboard/',DashboardAnalyticsView.as_view()),
    path('analytics/campaign/<int:campaign_id>/',CampaignAnalyticsView.as_view()),
    path('analytics/campaign/<int:campaign_id>/refresh/',RefreshAnalyticsView.as_view()),
    path('track/open/<uuid:tracking_id>/',track_open,name='track_open'),
    path('track/click/<str:short_code>/<int:recipient_id>/',track_click,name='track_click'),
    path("sendgrid/webhook/",sendgrid_webhook,name="sendgrid-webhook"),
    path(
        'campaigns/',
        DripCampaignListCreateView.as_view(),
        name='drip-campaign-list-create'
    ),

    # Get + Update + Delete single campaign
    path(
        'campaigns/<int:campaign_id>/',
        DripCampaignDetailView.as_view(),
        name='drip-campaign-detail'
    ),

    # Activate a campaign
    path(
        'campaigns/<int:campaign_id>/activate/',
        DripCampaignActivateView.as_view(),
        name='drip-campaign-activate'
    ),

    # Pause a campaign
    path(
        'campaigns/<int:campaign_id>/pause/',
        DripCampaignPauseView.as_view(),
        name='drip-campaign-pause'
    ),

    # -------------------------------------------------------
    # STEP URLs
    # -------------------------------------------------------

    # List all steps + Add new step
    path(
        'campaigns/<int:campaign_id>/steps/',
        DripStepListCreateView.as_view(),
        name='drip-step-list-create'
    ),

    # Get + Update + Delete single step
    path(
        'campaigns/<int:campaign_id>/steps/<int:step_id>/',
        DripStepDetailView.as_view(),
        name='drip-step-detail'
    ),

    # -------------------------------------------------------
    # ENROLLMENT URLs
    # -------------------------------------------------------

    # List all enrollments for a campaign
    path(
        'campaigns/<int:campaign_id>/enrollments/',
        DripEnrollmentListView.as_view(),
        name='drip-enrollment-list'
    ),

    # Manually enroll contacts into a campaign
    path(
        'campaigns/<int:campaign_id>/enroll/',
        DripManualEnrollView.as_view(),
        name='drip-manual-enroll'
    ),

    # Stop a single enrollment
    path(
        'enrollments/<int:enrollment_id>/stop/',
        DripEnrollmentStopView.as_view(),
        name='drip-enrollment-stop'
    ),

    # -------------------------------------------------------
    # ANALYTICS + LOGS URLs
    # -------------------------------------------------------

    # Campaign analytics
    path(
        'campaigns/<int:campaign_id>/analytics/',
        DripCampaignAnalyticsView.as_view(),
        name='drip-campaign-analytics'
    ),

    # Email logs for a campaign
    path(
        'campaigns/<int:campaign_id>/logs/',
        DripEmailLogView.as_view(),
        name='drip-email-logs'
    ),

    # -------------------------------------------------------
    # WEBHOOK URL
    # -------------------------------------------------------

    # Receive webhook events from external systems
    path(
        'webhook/',
        WebhookEventView.as_view(),
        name='drip-webhook'
    ),
    path(
        'campaigns/<int:campaign_id>/steps/<int:step_id>/follow-up-rules/',
        StepFollowUpRuleListCreateView.as_view(),
        name='step-follow-up-rule-list-create'
    ),
    path(
        'follow-up-rules/step/<int:rule_id>/',
        StepFollowUpRuleDetailView.as_view(),
        name='step-follow-up-rule-detail'
    ),

    # -------------------------------------------------------
    # NEW — CAMPAIGN LEVEL EVENT RULE URLs
    # -------------------------------------------------------
    path(
        'campaigns/<int:campaign_id>/event-rules/',
        CampaignEventRuleListCreateView.as_view(),
        name='campaign-event-rule-list-create'
    ),
    path(
        'event-rules/<int:rule_id>/',
        CampaignEventRuleDetailView.as_view(),
        name='campaign-event-rule-detail'
    ),

    # -------------------------------------------------------
    # NEW — FOLLOW-UP TRIGGER LOG URLs
    # -------------------------------------------------------
    path(
        'campaigns/<int:campaign_id>/follow-up-logs/',
        FollowUpTriggerLogView.as_view(),
        name='follow-up-trigger-logs'
    ),
    path(
        'ab-test/',
        ABTestListCreateView.as_view(),
        name='ab-test-list-create'
    ),

    # Get + Update + Delete single test
    path(
        'ab-test/<int:test_id>/',
        ABTestDetailView.as_view(),
        name='ab-test-detail'
    ),

    # Start the test
    path(
        'ab-test/<int:test_id>/run/',
        ABTestRunView.as_view(),
        name='ab-test-run'
    ),

    # Get current results
    path(
        'ab-test/<int:test_id>/results/',
        ABTestResultsView.as_view(),
        name='ab-test-results'
    ),

    # Manually set winner
    path(
        'ab-test/<int:test_id>/set-winner/',
        ABTestSetWinnerView.as_view(),
        name='ab-test-set-winner'
    ),

    # Cancel test
    path(
        'ab-test/<int:test_id>/cancel/',
        ABTestCancelView.as_view(),
        name='ab-test-cancel'
    ),

    # -------------------------------------------------------
    # CAMPAIGN SPECIFIC URL
    # -------------------------------------------------------

    # Get A/B test for a specific campaign
    path(
        'campaigns/<int:campaign_id>/ab-test/',
        CampaignABTestView.as_view(),
        name='campaign-ab-test'
    ),
    #template endpoints
    path('templates/',TemplateListView.as_view(),name='template-list'),
    path('templates/popular',PopularTemplateView.as_view(),name='template-popular'),
    path('template/create-defaults/',CreateDefaultTemplatesView.as_view(),name='template-create-defaults'),
    path('templates/<int:template_id>/',TemplateDetailView.as_view(),name='template-detail'),
    path('templates/create/',TemplateCreateView.as_view(),name='template-create'),
    path('templates/<int:template_id>/update',TemplateUpdateView.as_view(),name='template-update'),
    path('templates/<int:template_id>/delete',TemplateDeleteView.as_view(),name='template-delete'),
    path('templates/<int:template_id/duplicate/',TemplateDuplicateView.as_view(),name='template-duplicate'),
    path('templates/<int:template_id>/preview/',TemplatePreviewView.as_view(),name='template-preview'),
]
# -------------------------------------------------------
# HOW TO INCLUDE THESE URLs IN YOUR MAIN urls.py
# -------------------------------------------------------

"""
In your main project urls.py add this:

from django.urls import path, include

urlpatterns = [
    ...
    path('api/drip/', include('campaigns.drip_urls')),
    ...
]


Final URLs will look like this:

METHOD   URL                                          ACTION
------   ---                                          ------
GET      /api/drip/campaigns/                         List all campaigns
POST     /api/drip/campaigns/                         Create campaign

GET      /api/drip/campaigns/1/                       Get campaign details
PUT      /api/drip/campaigns/1/                       Update campaign
DELETE   /api/drip/campaigns/1/                       Delete campaign

POST     /api/drip/campaigns/1/activate/              Activate campaign
POST     /api/drip/campaigns/1/pause/                 Pause campaign

GET      /api/drip/campaigns/1/steps/                 List all steps
POST     /api/drip/campaigns/1/steps/                 Add new step

GET      /api/drip/campaigns/1/steps/2/               Get step details
PUT      /api/drip/campaigns/1/steps/2/               Update step
DELETE   /api/drip/campaigns/1/steps/2/               Delete step

GET      /api/drip/campaigns/1/enrollments/           List enrollments
GET      /api/drip/campaigns/1/enrollments/?status=active   Filter by status
POST     /api/drip/campaigns/1/enroll/                Manually enroll

POST     /api/drip/enrollments/5/stop/                Stop enrollment

GET      /api/drip/campaigns/1/analytics/             Campaign analytics
GET      /api/drip/campaigns/1/logs/                  Email logs

POST     /api/drip/webhook/                           Receive webhook event
"""