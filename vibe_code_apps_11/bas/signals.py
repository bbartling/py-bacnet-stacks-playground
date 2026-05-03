from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from bas.models import BasRole, UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def ensure_user_profile(sender, instance, created, **kwargs) -> None:
    if kwargs.get('raw'):
        return
    UserProfile.objects.get_or_create(
        user=instance,
        defaults={
            'bas_role': BasRole.OPERATOR,
            'read_only': False,
            'must_change_password': True,
        },
    )
