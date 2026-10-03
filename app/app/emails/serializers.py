from rest_framework import serializers
from .models import EmailSetting
class EmailSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model=EmailSetting
        fields=[
            "provider",
            "api_key",
            "from_name",
            "from_email",
            "sending_domain",
            "domain_verified"
        ]
        read_only_fields=["domain_verified"]
    