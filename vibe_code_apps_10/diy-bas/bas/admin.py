from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth import get_user_model

from bas.models import UserProfile

User = get_user_model()


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    fk_name = 'user'
    fields = ('bas_role', 'read_only', 'must_change_password')


class UserAdmin(DjangoUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'is_staff', 'is_superuser', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active')


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
