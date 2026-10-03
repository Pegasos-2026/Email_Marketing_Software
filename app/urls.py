"""
URL configuration for app project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)
from app.campaigns.view.tracking_views import track_open, track_click
from app.campaigns.views import sendgrid_webhook

urlpatterns = [
    path('admin/', admin.site.urls),
    #JWT TOKEN ENDPOINTS
    path('api/token/',TokenObtainPairView.as_view(),name='token_obtain_pair'),
    path('api/token/refresh/',TokenRefreshView.as_view(),name='token_refresh'),
    path('api/token/verify/',TokenVerifyView.as_view(),name='token_verify'),

    #auth endpoints
    path('api/auth/', include('app.accounts.urls')),
    path('api/emails/', include('app.emails.urls')),
    path('api/campaigns/', include('app.campaigns.urls')),
    path('sendgrid/webhook/', sendgrid_webhook, name='sendgrid-webhook'),
    # Legacy tracking URLs (emails sent before path fix)
    path('track/open/<uuid:tracking_id>/', track_open, name='legacy_track_open'),
    path('track/click/<str:short_code>/<int:recipient_id>/', track_click, name='legacy_track_click'),
]
