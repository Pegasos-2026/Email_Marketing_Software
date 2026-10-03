from django.urls import path
from .views import  SendEmailView,VerifyDomainView
urlpatterns=[
    path("send-email/",SendEmailView.as_view(),name="send-email"),
    path("verify-domain/",VerifyDomainView.as_view(),name="verify-domain"),
]