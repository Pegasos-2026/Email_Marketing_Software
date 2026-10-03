from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile, UserRole

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        default_role = UserRole.ADMIN if not UserProfile.objects.exists() else UserRole.EDITOR
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={'role': default_role},
        )
