from django.conf import settings
from rest_framework import serializers

from .deliverability import is_public_site_url
from .models import EmailSetting


class EmailSettingSerializer(serializers.ModelSerializer):
    smtp_password_configured = serializers.SerializerMethodField()
    api_key_configured = serializers.SerializerMethodField()
    site_url = serializers.SerializerMethodField()
    site_url_public = serializers.SerializerMethodField()

    class Meta:
        model = EmailSetting
        fields = [
            "provider",
            "api_key",
            "smtp_host",
            "smtp_port",
            "smtp_user",
            "smtp_password",
            "from_name",
            "from_email",
            "sending_domain",
            "domain_verified",
            "smtp_password_configured",
            "api_key_configured",
            "site_url",
            "site_url_public",
        ]
        read_only_fields = [
            "domain_verified",
            "smtp_password_configured",
            "api_key_configured",
            "site_url",
            "site_url_public",
        ]
        extra_kwargs = {
            "api_key": {"write_only": True, "required": False},
            "smtp_password": {"write_only": True, "required": False},
        }

    def get_smtp_password_configured(self, obj):
        return bool(obj.smtp_password)

    def get_api_key_configured(self, obj):
        return bool(obj.api_key)

    def get_site_url(self, obj):
        return settings.SITE_URL

    def get_site_url_public(self, obj):
        return is_public_site_url(settings.SITE_URL)

    def update(self, instance, validated_data):
        if not validated_data.get("api_key"):
            validated_data.pop("api_key", None)
        if not validated_data.get("smtp_password"):
            validated_data.pop("smtp_password", None)
        return super().update(instance, validated_data)
