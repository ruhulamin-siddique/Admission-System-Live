"""
CoE Module — URL Configuration

All URL patterns under the /coe/ prefix.
Public views (submit, track) require no login.
Staff views use the require_access() decorator.
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── Staff Dashboard & List ───────────────────────────────────────────────
    path('', views.dashboard, name='coe_dashboard'),
    path('applications/', views.application_list, name='coe_application_list'),
    path('applications/<int:pk>/', views.application_detail, name='coe_application_detail'),

    # ── Public Portal ────────────────────────────────────────────────────────
    path('submit/', views.submit_application, name='coe_submit'),
    path('submit/step/<int:step>/', views.submit_step, name='coe_submit_step'),
    path('submit/success/', views.submit_success, name='coe_submit_success'),
    path('track/', views.track_application, name='coe_track'),
    path('verify/<str:tracking_number>/', views.verify_document_public, name='coe_verify_public'),
    path('reupload/', views.student_reupload_portal, name='coe_reupload_portal'),

    # ── HoD Interface ───────────────────────────────────────────────────────
    path('hod/', views.hod_dashboard, name='coe_hod_dashboard'),
    path('hod/<int:pk>/review/', views.hod_review, name='coe_hod_review'),
    path('hod/bulk-action/', views.hod_bulk_action, name='coe_hod_bulk'),

    # ── CoE Kanban / Assignment ──────────────────────────────────────────────
    path('kanban/', views.kanban_board, name='coe_kanban'),
    path('kanban/<int:pk>/assign/', views.assign_officer, name='coe_assign_officer'),

    # ── Processing Workstation ───────────────────────────────────────────────
    path('process/<int:pk>/', views.processing_workstation, name='coe_process'),
    path('process/<int:pk>/fetch-admission/', views.fetch_admission_api, name='coe_fetch_admission'),
    path('process/<int:pk>/fetch-board/', views.fetch_board_api, name='coe_fetch_board'),
    path('process/<int:pk>/request-reupload/', views.request_reupload, name='coe_request_reupload'),
    path('process/<int:pk>/ready/', views.mark_ready, name='coe_mark_ready'),

    # ── Delivery Desk ────────────────────────────────────────────────────────
    path('delivery/', views.delivery_dashboard, name='coe_delivery_dashboard'),
    path('delivery/<int:pk>/verify-otp/', views.verify_otp, name='coe_verify_otp'),
    path('delivery/<int:pk>/deliver/', views.mark_delivered, name='coe_mark_delivered'),
    path('delivery/handover-register/', views.delivery_handover_register, name='coe_handover_register'),

    # ── Export, PDF & Settings ───────────────────────────────────────────────
    path('export/', views.export_excel, name='coe_export'),
    path('settings/', views.coe_settings_view, name='coe_settings'),
    path('applications/<int:pk>/receipt-pdf/', views.download_receipt_pdf, name='coe_receipt_pdf'),
    path('applications/<int:pk>/routing-slip/', views.download_routing_slip_pdf, name='coe_routing_slip_pdf'),

    # ── AJAX Helpers ─────────────────────────────────────────────────────────
    path('ajax/<int:pk>/attachments/', views.ajax_attachments, name='coe_ajax_attachments'),
    path('ajax/type-fields/', views.ajax_type_fields, name='coe_ajax_type_fields'),
]
