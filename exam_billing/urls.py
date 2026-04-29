from django.urls import path

from . import views


urlpatterns = [
    path('', views.dashboard, name='billing_dashboard'),
    path('settings/rates/', views.rate_templates, name='billing_rate_templates'),
    path('exams/', views.exam_list, name='billing_exam_list'),
    path('exams/create/', views.exam_create, name='billing_exam_create'),
    path('exams/<int:pk>/', views.exam_detail, name='billing_exam_detail'),
    path('exams/<int:pk>/edit/', views.exam_edit, name='billing_exam_edit'),
    path('faculty/', views.faculty_directory, name='billing_faculty_directory'),
    path('faculty/<int:pk>/delete/', views.faculty_delete, name='billing_faculty_delete'),
    path('programs/<int:pk>/', views.program_workspace, name='billing_program_workspace'),
    path('programs/<int:pk>/copy-faculty/', views.copy_faculty_to_exam, name='billing_copy_faculty'),
    path('programs/<int:pk>/submit/', views.program_submit, name='billing_program_submit'),
    path('programs/<int:pk>/status/<str:action>/', views.program_status, name='billing_program_status'),
    path('programs/<int:pk>/summary.csv', views.summary_csv, name='billing_summary_csv'),
    path('programs/<int:pk>/sheets/<str:sheet>/', views.program_sheet, name='billing_program_sheet'),
    path('programs/<int:pk>/sheets/<str:sheet>/<int:row_id>/delete/', views.program_sheet_delete, name='billing_program_sheet_delete'),
    path('programs/<int:pk>/individual/<int:faculty_id>/', views.individual_bill, name='billing_individual_bill'),
]
