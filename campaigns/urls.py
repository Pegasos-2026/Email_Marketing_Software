from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .view.analytics_stream_views import DashboardAnalyticsStreamView,CampaignAnalyticsStreamView
from .views import (CampaignViewSet,DashboardAnalyticsView,CampaignAnalyticsView,RefreshAnalyticsView,TemplateListView,TemplateDetailView,
                    TemplateCreateView,TemplateUpdateView,TemplateDeleteView,TemplateDuplicateView,TemplatePreviewView,
                    CreateDefaultTemplatesView,PopularTemplateView,ContactListView,ContactDeleteView,ContactCreateView,
                    ContactListsView,ContactListDetailView,ContactImportCSVView,ContactExportCSVView,ContactImportTemplateView,
                    BulkEmailSendView,DripCampaignListCreateView,DripCampaignDetailView,DripCampaignActivateView,
                    DripCampaignPauseView,DripCampaignAnalyticsView,DripStepListCreateView,DripStepDetailView)
from .view.tracking_views import track_open,track_click
from .view.unsubscribe_views import track_unsubscribe
from .views import sendgrid_webhook
router=DefaultRouter()
router.register(r'campaigns',CampaignViewSet,basename='campaign')
urlpatterns=[
    path('',include(router.urls)),
    #tracking endpoints(public-no auth required)
    path('analytics/dashboard/',DashboardAnalyticsView.as_view()),
    path('analytics/dashboard/stream/',DashboardAnalyticsStreamView.as_view()),
    path('analytics/campaign/<int:campaign_id>/',CampaignAnalyticsView.as_view()),
    path('analytics/campaign/<int:campaign_id>/stream/',CampaignAnalyticsStreamView.as_view()),
    path('analytics/campaign/<int:campaign_id>/refresh/',RefreshAnalyticsView.as_view()),
    path('track/open/<uuid:tracking_id>/',track_open,name='track_open'),
    path('track/click/<str:short_code>/<int:recipient_id>/',track_click,name='track_click'),
    path('sendgrid/webhook/', sendgrid_webhook, name='sendgrid-webhook'),
    path('unsubscribe/<int:recipient_id>/',track_unsubscribe,name='track_unsubscribe'),
    #template endpoints
    path('templates/',TemplateListView.as_view(),name='template-list'),
    path('templates/popular',PopularTemplateView.as_view(),name='template-popular'),
    path('template/create-defaults/',CreateDefaultTemplatesView.as_view(),name='template-create-defaults'),
    path('templates/<int:template_id>/',TemplateDetailView.as_view(),name='template-detail'),
    path('templates/create/',TemplateCreateView.as_view(),name='template-create'),
    path('templates/<int:template_id>/update',TemplateUpdateView.as_view(),name='template-update'),
    path('templates/<int:template_id>/delete',TemplateDeleteView.as_view(),name='template-delete'),
    path('templates/<int:template_id>/duplicate/',TemplateDuplicateView.as_view(),name='template-duplicate'),
    path('templates/<int:template_id>/preview/',TemplatePreviewView.as_view(),name='template-preview'),
    # contacts endpoints
    path('contacts/', ContactListView.as_view(), name='contact-list'),
    path('contacts/<int:contact_id>/', ContactDeleteView.as_view(), name='contact-delete'),
    path('contacts/create/', ContactCreateView.as_view(), name='contact-create'),
    path('contacts/import/', ContactImportCSVView.as_view(), name='contact-import'),
    path('contacts/export/', ContactExportCSVView.as_view(), name='contact-export'),
    path('contacts/import-template/', ContactImportTemplateView.as_view(), name='contact-import-template'),
    path('contact-lists/', ContactListsView.as_view(), name='contact-lists'),
    path('contact-lists/<int:list_id>/', ContactListDetailView.as_view(), name='contact-list-detail'),
    # bulk email endpoint
    path('bulk-send/', BulkEmailSendView.as_view(), name='bulk-send'),

    # drip campaign endpoints
    path('drip/campaigns/', DripCampaignListCreateView.as_view(), name='drip-campaign-list-create'),
    path('drip/campaigns/<int:campaign_id>/', DripCampaignDetailView.as_view(), name='drip-campaign-detail'),
    path('drip/campaigns/<int:campaign_id>/activate/', DripCampaignActivateView.as_view(), name='drip-campaign-activate'),
    path('drip/campaigns/<int:campaign_id>/pause/', DripCampaignPauseView.as_view(), name='drip-campaign-pause'),
    path('drip/campaigns/<int:campaign_id>/analytics/', DripCampaignAnalyticsView.as_view(), name='drip-campaign-analytics'),
]