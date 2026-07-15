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
    
    # Registration & Approvals (Managed at Root Level)
    path('security/user/approve/<int:user_id>/', views.user_approve, name='user_approve'),
    path('security/user/disapprove/<int:user_id>/', views.user_disapprove, name='user_disapprove'),
    path('security/user/delete/<int:user_id>/', views.user_delete, name='user_delete'),

    path('security/settings/', views.system_settings, name='system_settings'),
    path('security/audit-logs/', views.audit_logs, name='audit_logs'),
    path('security/audit-logs/export/', views.export_audit_logs, name='export_audit_logs'),
    path('security/toggle-theme/', views.toggle_theme, name='toggle_theme'),
    path('security/toggle-navbar-pin/', views.toggle_navbar_pin, name='toggle_navbar_pin'),
    path('security/backup/download/', views.download_db_backup, name='download_db_backup'),
    path('security/set-language/', views.set_user_language, name='set_user_language'),

    # ── Developer Portfolio (Public — no login required) ──────────────────────
    path('portfolio/', views.developer_portfolio, name='developer_portfolio'),

    # Superuser-only AJAX APIs (403 returned to non-superusers internally)
    path('portfolio/api/save-profile/', views.portfolio_api_save_profile, name='portfolio_api_save_profile'),
    path('portfolio/api/save/<str:section>/', views.portfolio_api_save, name='portfolio_api_save'),
    path('portfolio/api/delete/<str:section>/<int:pk>/', views.portfolio_api_delete, name='portfolio_api_delete'),
    path('portfolio/api/reorder/<str:section>/', views.portfolio_api_reorder, name='portfolio_api_reorder'),
]
