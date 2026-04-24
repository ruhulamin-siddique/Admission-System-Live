from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('students/', views.student_list, name='student_list'),
    path('students/migrate/', views.migration_center, name='migration_center'),
    path('students/cancel-hub/', views.cancellation_hub, name='cancellation_hub'),
    path('students/cancel-list-modal/', views.cancellation_list_modal, name='cancellation_list_modal'),
    path('students/cancel-action/<str:student_id>/', views.cancel_admission, name='cancel_admission'),
    path('api/bulk-cancel/', views.api_bulk_cancel_admission, name='api_bulk_cancel_admission'),
    path('students/profile/<str:student_id>/', views.student_profile, name='student_profile'),
    path('students/edit/<str:student_id>/', views.edit_student, name='edit_student'),
    path('students/short-info/<str:student_id>/', views.student_short_info, name='student_short_info'),
    path('students/delete/<str:student_id>/', views.delete_student, name='delete_student'),
    path('reports/academic-intake/', views.academic_intake_report, name='academic_intake_report'),
    path('students/import/', views.import_students, name='import_students'),
    path('students/import/preview/', views.import_preview, name='import_preview'),
    path('students/import/template/', views.download_import_template, name='download_import_template'),
    path('students/change-program/<str:student_id>/', views.change_program, name='change_program'),
    path('students/add/', views.add_student, name='add_student'),
    path('students/export/', views.export_students, name='export_students'),
    path('students/export/all/', views.export_students_all, name='export_students_all'),
    path('api/preview-id/', views.api_preview_id, name='api_preview_id'),
    
    # Reports & Dynamic Exports
    path('reports/center/', views.reports_center, name='reports_center'),
    path('reports/analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('reports/master-sheet/<str:student_id>/', views.download_master_sheet, name='download_master_sheet'),
    path('reports/export-center/', views.export_center, name='export_center'),
    path('reports/export/students/', views.export_students_dynamic, name='export_students_dynamic'),
    path('reports/export/migrations/', views.export_migrations_dynamic, name='export_migrations_dynamic'),
    path('reports/export/cancellations/', views.export_cancellations_dynamic, name='export_cancellations_dynamic'),
]
