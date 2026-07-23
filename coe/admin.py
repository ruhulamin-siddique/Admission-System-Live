"""
CoE Module — Django Admin Registrations
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import (
    DocumentApplication, ApplicationAttachment,
    ApplicationStatusLog, ProcessingVerification, CoeSettings,
    CoeAssignmentRule
)


class ApplicationAttachmentInline(admin.TabularInline):
    model = ApplicationAttachment
    extra = 0
    readonly_fields = ('sha256_hash', 'file_size_kb', 'original_filename', 'uploaded_at', 'is_purged')
    fields = ('attachment_type', 'file', 'original_filename', 'file_size_kb', 'sha256_hash', 'is_purged', 'uploaded_at')


class ApplicationStatusLogInline(admin.TabularInline):
    model = ApplicationStatusLog
    extra = 0
    readonly_fields = ('old_status', 'new_status', 'changed_by', 'note', 'sms_sent', 'changed_at')
    can_delete = False


@admin.register(DocumentApplication)
class DocumentApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'application_number', 'student_name', 'student_id',
        'application_type', 'status', 'department', 'submitted_at', 'is_deleted'
    )
    list_filter = ('status', 'application_type', 'is_deleted', 'department')
    search_fields = ('application_number', 'student_name', 'student_id', 'mobile_number')
    readonly_fields = ('application_number', 'tracking_pin', 'submitted_at', 'updated_at')
    inlines = [ApplicationAttachmentInline, ApplicationStatusLogInline]
    list_per_page = 25
    ordering = ['-submitted_at']

    fieldsets = (
        (_('Identification'), {
            'fields': ('application_number', 'tracking_pin', 'application_type', 'status')
        }),
        (_('Student Information'), {
            'fields': ('student_name', 'student_id', 'mobile_number', 'email')
        }),
        (_('Academic Information'), {
            'fields': ('session', 'department', 'admission_batch', 'father_name', 'mother_name',
                       'dob', 'passing_semester', 'cgpa', 'result_date')
        }),
        (_('Type-Specific Fields'), {
            'fields': ('corrected_name', 'corrected_parent_name', 'purpose_destination',
                       'level_term', 'missing_doc_type'),
            'classes': ('collapse',)
        }),
        (_('Staff Notes'), {
            'fields': ('dept_head_note', 'processing_note', 'rejection_reason')
        }),
        (_('Delivery'), {
            'fields': ('delivery_otp', 'delivery_otp_verified', 'delivered_at', 'delivered_by')
        }),
        (_('Assignment'), {
            'fields': ('submitted_by', 'assigned_to')
        }),
        (_('Flags'), {
            'fields': ('is_deleted', 'submitted_at', 'updated_at')
        }),
    )


@admin.register(ProcessingVerification)
class ProcessingVerificationAdmin(admin.ModelAdmin):
    list_display = ('application', 'admission_api_fetched', 'board_api_fetched', 'verified_by', 'verified_at')
    list_filter = ('admission_api_fetched', 'board_api_fetched')
    search_fields = ('application__application_number', 'application__student_name')


@admin.register(CoeSettings)
class CoeSettingsAdmin(admin.ModelAdmin):
    list_display = ('tracking_id_prefix', 'attachment_max_mb', 'rejected_purge_days', 'delivered_purge_days')

    def has_add_permission(self, request):
        # Singleton — only one settings object allowed
        return not CoeSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CoeAssignmentRule)
class CoeAssignmentRuleAdmin(admin.ModelAdmin):
    list_display = ('application_type', 'officer')
    list_filter = ('application_type',)
    search_fields = ('officer__username', 'officer__first_name', 'officer__last_name')

