from django.urls import path
from . import views

urlpatterns = [
    # User Profile
    path('profile/', views.user_profile, name='user_profile'),

    # Security Management
    path('security/roles/', views.role_management, name='role_management'),
    path('security/users/', views.user_management, name='user_management'),
    
    # User Actions (CRUD)
    path('security/user/create/', views.user_create, name='user_create'),
    path('security/user/toggle/<int:user_id>/', views.user_toggle_status, name='user_toggle_status'),
    path('security/user/reset-password/<int:user_id>/', views.user_reset_password, name='user_reset_password'),
    path('security/settings/', views.system_settings, name='system_settings'),
    path('security/audit-logs/', views.audit_logs, name='audit_logs'),
    path('security/toggle-theme/', views.toggle_theme, name='toggle_theme'),
]
