from django.db import models
from django.contrib.auth.models import User
from .utils import encrypt_value, decrypt_value


class EmailSetting(models.Model):
    PROVIDER_CHOICES = [
        ("SendGrid", "SendGrid"),
        ("SMTP", "SMTP"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, default="SMTP")
    api_key = models.TextField(blank=True, null=True)
    smtp_host = models.CharField(max_length=255, blank=True, null=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_user = models.CharField(max_length=255, blank=True, null=True)
    smtp_password = models.TextField(blank=True, null=True)
    from_email = models.EmailField(blank=True, null=True)
    from_name = models.CharField(max_length=100, blank=True, null=True)
    sending_domain = models.CharField(max_length=255, null=True, blank=True)
    domain_verified = models.BooleanField(default=False)
    domain_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.api_key and not self._looks_encrypted(self.api_key):
            self.api_key = encrypt_value(self.api_key)
        if self.smtp_password and not self._looks_encrypted(self.smtp_password):
            self.smtp_password = encrypt_value(self.smtp_password)
        super().save(*args, **kwargs)

    @staticmethod
    def _looks_encrypted(value):
        return isinstance(value, str) and value.startswith("gAAAA")

    def get_api_key(self):
        return decrypt_value(self.api_key) if self.api_key else None

    def get_smtp_password(self):
        return decrypt_value(self.smtp_password) if self.smtp_password else None

    def __str__(self):
        return f"{self.user.username} - {self.provider}"

