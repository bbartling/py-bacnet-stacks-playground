from django.contrib import admin
from django.urls import path

from bas import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('bas/manage/', views.bas_manage_users, name='bas_manage_users'),
    path('api/health', views.api_health),
    path('api/auth/login', views.api_auth_login),
    path('api/auth/logout', views.api_auth_logout),
    path('api/auth/me', views.api_auth_me),
    path('api/auth/token', views.api_auth_token),
    path('api/devices', views.api_devices),
    path('api/points', views.api_points),
    path('api/alarm-rules', views.api_alarm_rules),
    path('api/device-notes', views.api_device_notes),
    path('api/dashboard-layouts', views.api_dashboard_layouts),
    path('api/audit/logs', views.api_audit_logs),
    path('favicon.ico', views.favicon),
    path('', views.index),
    path('<path:filename>', views.static_file),
]
