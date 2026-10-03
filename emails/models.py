from django.db import models
from django.contrib.auth.models import User
from .utils import encrypt_value,decrypt_value
class EmailSetting(models.Model):
    PROVIDER_CHOICES=[
        ("SendGrid","sendgrid")
    ]
    user=models.OneToOneField(User,on_delete=models.CASCADE)
    provider=models.CharField(max_length=50,choices=PROVIDER_CHOICES)
    api_key=models.TextField()
    from_email=models.EmailField()
    from_name=models.CharField(max_length=100)
    sending_domain=models.CharField(max_length=255,null=True,blank=True)
    domain_verified=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)
    def save(self,*args,**kwargs):
        if self.api_key and not str(self.api_key).startswith("_BYxt"):
            self.api_key = encrypt_value(self.api_key)
        super().save(*args, **kwargs)
    def get_api_key(self):
        return decrypt_value(self.api_key)
    def __str__(self):
        return f"{self.user.username} - {self.provider}"

