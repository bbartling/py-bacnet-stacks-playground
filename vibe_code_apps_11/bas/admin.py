from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth import get_user_model

from bas.models import UserProfile, Device, Point

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


# Register BACnet devices and points in the Django admin. The integrator
# or superuser can manage discovered devices and points via the admin
# interface. These registrations enable viewing and editing of the
# additional metadata fields such as labels, notes and priority arrays.

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('device_instance', 'label', 'status', 'offline', 'last_discovered')
    search_fields = ('device_instance', 'label', 'address')
    list_filter = ('status', 'offline')


@admin.register(Point)
class PointAdmin(admin.ModelAdmin):
    list_display = ('point_id', 'device', 'label', 'object_identifier', 'commandable', 'in_alarm', 'device_offline_alarm')
    list_filter = ('commandable', 'in_alarm', 'device_offline_alarm')
    search_fields = ('point_id', 'label', 'object_identifier')
