from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
admin.site.unregister(User)
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display=('username','email','first_name','last_name','is_staff')
    list_filter=('is_staff','is_superuser','is_active')
    search_fields=('username','email','first_name','last_name')
    ordering=('-id',)