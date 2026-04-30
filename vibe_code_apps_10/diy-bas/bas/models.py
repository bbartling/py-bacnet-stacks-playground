from django.conf import settings
from django.db import models

from app.roles import ROLE_INTEGRATOR, ROLE_OPERATOR


class BasRole(models.TextChoices):
    """BAS-style roles stored on the profile (Django User holds credentials)."""

    INTEGRATOR = ROLE_INTEGRATOR, 'System integrator'
    MAINTENANCE = 'maintenance', 'Maintenance'
    OPERATOR = ROLE_OPERATOR, 'Building operator'


class UserProfile(models.Model):
    """Per-user BAS flags; integrator from env is also is_superuser on User."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bas_profile')
    bas_role = models.CharField(max_length=64, choices=BasRole.choices, default=BasRole.OPERATOR)
    read_only = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=True)

    class Meta:
        db_table = 'bas_userprofile'

    def __str__(self) -> str:
        return f'{self.user.username} ({self.bas_role})'


class AuditLog(models.Model):
    """Read-only mirror of legacy SQLite audit table (trend DB)."""

    ts = models.BigIntegerField()
    username = models.CharField(max_length=255)
    role = models.CharField(max_length=64)
    action = models.CharField(max_length=255)
    success = models.IntegerField(default=1)
    details_json = models.TextField(default='{}')

    class Meta:
        db_table = 'audit_logs'
        managed = False
