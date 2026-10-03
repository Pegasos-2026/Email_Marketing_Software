from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class EmailBackend(ModelBackend):
    """Authenticate users by email address."""

    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        login_value = email or username
        if login_value is None or password is None:
            return None
        try:
            user = User.objects.get(email__iexact=login_value)
        except User.DoesNotExist:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
