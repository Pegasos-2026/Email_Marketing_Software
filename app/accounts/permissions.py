from rest_framework.permissions import BasePermission

from .models import UserProfile, UserRole


def get_user_profile(user):
    if not user or not user.is_authenticated:
        return None
    profile, _created = UserProfile.objects.get_or_create(
        user=user,
        defaults={'role': UserRole.EDITOR},
    )
    return profile


class HasAppPermission(BasePermission):
    """Require a named application permission based on user role."""

    required_permission = ''

    def has_permission(self, request, view):
        profile = get_user_profile(request.user)
        if profile is None:
            return False
        permission = getattr(view, 'required_permission', None) or self.required_permission
        if not permission:
            return True
        return profile.has_permission(permission)


class IsAdminRole(HasAppPermission):
    def has_permission(self, request, view):
        profile = get_user_profile(request.user)
        return profile is not None and (
            request.user.is_superuser or profile.role == UserRole.ADMIN
        )
