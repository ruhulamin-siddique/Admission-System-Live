from django.urls import path

from . import views

urlpatterns = [
    path('manage/', views.api_client_management, name='api_client_management'),
    path('manage/logs/', views.api_request_logs, name='api_request_logs'),
    path('manage/client/<int:client_id>/toggle/', views.api_client_toggle, name='api_client_toggle'),
    path('manage/client/<int:client_id>/rotate/', views.api_client_rotate, name='api_client_rotate'),
    path('manage/client/<int:client_id>/delete/', views.api_client_delete, name='api_client_delete'),
    path('v1/health/', views.api_health, name='external_api_health'),
    path('v1/students/', views.api_students, name='external_api_students'),
    path('v1/students/<str:student_id>/', views.api_student_detail, name='external_api_student_detail'),
    path('v1/reports/summary/', views.api_report_summary, name='external_api_report_summary'),
]
