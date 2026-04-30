"""Bootstrap Django auth users from env (integrator = superuser, maintenance = BAS role)."""

from __future__ import annotations

import os

from django.contrib.auth import get_user_model

from bas.models import BasRole, UserProfile


def bootstrap_default_users() -> None:
    def _env_cred(key: str, default: str) -> str:
        raw = os.environ.get(key, default)
        if raw is None:
            raw = default
        cleaned = str(raw).replace('\ufeff', '').replace('\r', '').strip()
        return cleaned or default

    integrator_username = _env_cred('DIY_BAS_ADMIN_USERNAME', 'integrator')
    integrator_password = _env_cred('DIY_BAS_ADMIN_PASSWORD', 'ChangeMeNow!123')
    maintenance_username = _env_cred('DIY_BAS_MAINT_USERNAME', 'maintenance')
    maintenance_password = _env_cred('DIY_BAS_MAINT_PASSWORD', 'ChangeMeNow!123')
    refresh = os.environ.get('DIY_BAS_BOOTSTRAP_REFRESH_PASSWORDS', 'true').lower() in ('1', 'true', 'yes')

    User = get_user_model()

    def sync(
        username: str,
        password: str,
        *,
        is_superuser: bool,
        is_staff: bool,
        bas_role: str,
        read_only: bool,
    ) -> None:
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'is_active': True,
                'is_staff': is_staff,
                'is_superuser': is_superuser,
                'email': '',
            },
        )
        prev_must = True
        profile, _ = UserProfile.objects.get_or_create(user=user)
        if not created:
            prev_must = profile.must_change_password
        if created or refresh:
            user.set_password(password)
        user.is_active = True
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.save()
        profile.bas_role = bas_role
        profile.read_only = read_only
        profile.must_change_password = True if created else prev_must
        profile.save()

    sync(
        integrator_username,
        integrator_password,
        is_superuser=True,
        is_staff=True,
        bas_role=BasRole.INTEGRATOR,
        read_only=False,
    )
    sync(
        maintenance_username,
        maintenance_password,
        is_superuser=False,
        is_staff=False,
        bas_role=BasRole.MAINTENANCE,
        read_only=True,
    )
