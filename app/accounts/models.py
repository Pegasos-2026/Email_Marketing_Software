from django.conf import settings
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = 'admin', 'Administrator'
    MANAGER = 'manager', 'Manager'
    EDITOR = 'editor', 'Editor'
    VIEWER = 'viewer', 'Viewer'


ROLE_PERMISSIONS = {
    UserRole.ADMIN: {'campaigns', 'contacts', 'templates', 'drip', 'analytics', 'settings', 'users'},
    UserRole.MANAGER: {'campaigns', 'contacts', 'templates', 'drip', 'analytics', 'settings'},
    UserRole.EDITOR: {'campaigns', 'contacts', 'templates', 'drip'},
    UserRole.VIEWER: {'analytics'},
}


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.EDITOR,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.email} ({self.role})'

    def has_permission(self, permission: str) -> bool:
        if self.user.is_superuser:
            return True
        return permission in ROLE_PERMISSIONS.get(self.role, set())
