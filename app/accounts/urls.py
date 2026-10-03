from django.urls import path
from .views import RegisterView,UserProfileView,LogoutView,LoginView
urlpatterns=[
    path('register/',RegisterView.as_view(),name='auth_register'),
    path('login/',LoginView.as_view(),name="login"),
    path('profile/',UserProfileView.as_view(),name='auth_profile'),
    path('logout/',LogoutView.as_view(),name='auth_logout'),
]