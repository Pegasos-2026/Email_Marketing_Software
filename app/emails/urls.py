from django.urls import path
from .views import  SendEmailView,VerifyDomainView,CheckDomainStatusView,EmailSettingView
urlpatterns=[
    path("settings/",EmailSettingView.as_view()),
    path("send-email/",SendEmailView.as_view(),name="send-email"),
    path("verify-domain/",VerifyDomainView.as_view(),name="verify-domain"),
    path("check-domain-status/",CheckDomainStatusView.as_view(),name="check-domain-status"),
]