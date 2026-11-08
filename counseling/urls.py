"""
counseling/urls.py
==================
URL routes for the Psychological Counseling & Student Wellbeing Module.
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Public Student Booking Portal ─────────────────────────────────────────
    path('book/', views.public_book_appointment, name='counseling_public_book'),
    path('book/success/', views.public_book_success, name='counseling_public_success'),

    # ── Staff Command Center ──────────────────────────────────────────────────
    path('', views.dashboard, name='counseling_dashboard'),
    path('dashboard/', views.dashboard, name='counseling_dashboard_alt'),

    # ── Case Directory & Dossiers ─────────────────────────────────────────────
    path('cases/', views.case_list, name='counseling_case_list'),
    path('cases/new/', views.case_create, name='counseling_case_create'),
    path('cases/<int:pk>/', views.case_detail, name='counseling_case_detail'),
    path('cases/<int:pk>/edit/', views.case_edit, name='counseling_case_edit'),
    path('cases/<int:pk>/delete/', views.case_delete, name='counseling_case_delete'),

    # ── Appointments ──────────────────────────────────────────────────────────
    path('appointments/', views.appointment_list, name='counseling_appointments'),
    path('appointments/new/', views.appointment_create, name='counseling_appointment_create'),
    path('appointments/<int:pk>/status/<str:new_status>/', views.appointment_status_update, name='counseling_appointment_status'),

    # ── Clinical SOAP Sessions ────────────────────────────────────────────────
    path('cases/<int:case_id>/session/record/', views.record_session, name='counseling_record_session'),

    # ── Psychometric Assessments (PHQ-9, GAD-7, DASS-21) ──────────────────────
    path('cases/<int:case_id>/assessment/<str:scale_type>/', views.conduct_assessment, name='counseling_assessment'),

    # ── Emergency Crisis Intervention ─────────────────────────────────────────
    path('cases/<int:case_id>/emergency/', views.emergency_escalation, name='counseling_emergency'),

    # ── Wellbeing Workshops & Campaigns ───────────────────────────────────────
    path('workshops/', views.workshop_list, name='counseling_workshops'),
    path('workshops/new/', views.workshop_create, name='counseling_workshop_create'),
    path('workshops/<int:pk>/register/', views.workshop_register, name='counseling_workshop_register'),

    # ── De-Identified Macro Analytics ─────────────────────────────────────────
    path('analytics/', views.macro_analytics, name='counseling_analytics'),

    # ── Settings & Profiles ───────────────────────────────────────────────────
    path('settings/', views.counseling_settings_view, name='counseling_settings'),
    path('profile/', views.counselor_profile_view, name='counseling_counselor_profile'),

    # ── Async APIs (JSON / HTMX) ──────────────────────────────────────────────
    path('api/student-search/', views.api_student_search, name='counseling_api_student_search'),
    path('api/available-slots/', views.api_available_slots, name='counseling_api_slots'),
    path('api/verify-student/', views.api_verify_student_id, name='counseling_api_verify_student'),
    path('api/check-status/', views.api_check_appointment_status, name='counseling_api_check_status'),
    path('api/cancel-appointment/', views.api_cancel_public_appointment, name='counseling_api_cancel_appointment'),
]
